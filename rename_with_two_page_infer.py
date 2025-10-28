#!/usr/bin/env python3
"""
Lightweight renamer that builds on your existing policy but enforces:
- Author normalization to "Lastname, Firstname" (swap if given as "Firstname Lastname").
- Use up to the first TWO pages of a PDF when inferring title/author text (cover pages present).
- Dry-run by default; writes a CSV plan and supports --apply to perform renames + atomic metadata writes.

Usage:
  python rename_with_two_page_infer.py /path/to/corpus --csv out.csv [--apply]

This script is intentionally conservative: it prefers existing PDF metadata (Author/Title) if present,
otherwise it scans up to page 2 for likely title/author lines.
"""
import argparse
import csv
import os
import re
import tempfile
import shutil
from datetime import datetime

try:
    import fitz
except Exception as e:
    print("PyMuPDF (fitz) is required. Install in your venv: pip install pymupdf")
    raise

CSV_HEADERS = [
    'original_path', 'proposed_path', 'original_filename', 'proposed_filename',
    'meta_author', 'meta_title', 'reason'
]

YEAR_RE = re.compile(r"(19|20)\d{2}")


def kebab(s: str, max_len=200):
    if not s:
        return 'untitled'
    # lowercase, replace non-alnum with hyphen, collapse hyphens
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", '-', s)
    s = re.sub(r"-+", '-', s).strip('-')
    if len(s) > max_len:
        s = s[:max_len].rstrip('-')
    return s or 'untitled'


def safe_target_filename(prefix: str, lastname: str, firstname: str, year: str, title: str, max_total=200):
    """Builds a filename and truncates the title portion if needed so the total basename
    (without directory) doesn't exceed max_total characters. Appends an 8-char hash when
    truncation occurs to avoid collisions.
    """
    import hashlib
    # base pattern: {prefix}{initial}-{year}-{kebab(title)}.pdf
    initial = (firstname[0].upper() if firstname else 'X')
    base_name = f"{prefix}{initial}-{year}-"
    # reserve room for extension and possible hash: keep some headroom
    max_title_len = max_total - len(base_name) - len('.pdf')
    k = kebab(title or '', max_len=max_title_len)
    if len(k) > max_title_len:
        # truncate and append short hash
        short = k[: max(0, max_title_len - 9)].rstrip('-')
        h = hashlib.sha1((lastname or '') + (firstname or '') + (title or '')).hexdigest()[:8]
        k = f"{short}-{h}"
    # ensure final length
    final = f"{base_name}{k}.pdf"
    if len(final) > max_total:
        # as a last resort, hard truncate the title part
        excess = len(final) - max_total
        k = k[:-excess]
        final = f"{base_name}{k}.pdf"
    return final


def normalize_author_str(author: str):
    """Return (lastname, firstname, human_readable)
    Accepts forms like 'Firstname Lastname', 'Lastname, Firstname', 'Firstname M Lastname', etc.
    If ambiguous, returns (None, None, original)
    """
    if not author:
        return (None, None, '')
    a = author.strip()
    # If it's already 'Lastname, Firstname' -> preserve
    if ',' in a:
        parts = [p.strip() for p in a.split(',') if p.strip()]
        if len(parts) >= 2:
            lastname = parts[0]
            firstname = parts[1].split()[0]
            human = f"{lastname}, {firstname}"
            return (lastname, firstname, human)
    # If it's two words like 'Firstname Lastname' -> swap
    tokens = a.split()
    if len(tokens) >= 2:
        # assume last token is lastname
        firstname = tokens[0]
        lastname = tokens[-1]
        human = f"{lastname}, {firstname}"
        return (lastname, firstname, human)
    # fallback single token
    return (a, '', f"{a}")


def read_text_from_pdf(path, max_pages=2):
    try:
        doc = fitz.open(path)
    except Exception:
        return ''
    txt = []
    for p in range(min(max_pages, doc.page_count)):
        try:
            txt.append(doc[p].get_text('text'))
        except Exception:
            pass
    try:
        doc.close()
    except Exception:
        pass
    return '\n'.join(txt)


def infer_from_text(text):
    # Heuristic: first non-empty line is likely title, next lines may include author or year.
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = ''
    author = ''
    year = None
    if lines:
        title = lines[0]
    # Try to find a line that looks like an author (contains a space and letters)
    for ln in lines[1:6]:
        if re.search(r"[A-Za-z] ", ln):
            # avoid lines with 'abstract' or 'introduction'
            if re.search(r"abstract|introduction|keywords|doi|©|copyright", ln, re.I):
                continue
            author = ln
            break
    # try to find year anywhere
    m = YEAR_RE.search(text)
    if m:
        year = m.group(0)
    return (author, title, year)


def build_target_filename(lastname, firstname, year, title):
    if not lastname:
        lastname = 'unknown'
    last = re.sub(r"[^a-z]", '', lastname.lower())
    prefix = last
    y = year if year else '0000'
    # Use safe_target_filename to cap the total basename length
    return safe_target_filename(prefix, lastname, firstname, y, title, max_total=220)


def atomic_write_metadata(path, title, author):
    # write metadata into a temp file then move over
    try:
        doc = fitz.open(path)
    except Exception as e:
        return False, str(e)
    md = doc.metadata
    if title:
        md['title'] = title
    if author:
        md['author'] = author
    doc.set_metadata(md)
    # Attempt incremental save first
    try:
        doc.saveIncr()
        doc.close()
        return True, 'incr'
    except Exception:
        pass
    # fallback save to temp and replace
    try:
        tmpfd, tmppath = tempfile.mkstemp(suffix='.pdf', prefix='tmp-renamer-')
        os.close(tmpfd)
        doc.save(tmppath)
        doc.close()
        shutil.copystat(path, tmppath)
        os.replace(tmppath, path)
        return True, 'atomic'
    except Exception as e:
        try:
            doc.close()
        except Exception:
            pass
        return False, str(e)


def process_folder(folder, out_csv, apply=False):
    rows = []
    for entry in sorted(os.listdir(folder)):
        if not entry.lower().endswith('.pdf'):
            continue
        full = os.path.join(folder, entry)
        # read existing metadata
        try:
            doc = fitz.open(full)
            md = doc.metadata
            doc.close()
        except Exception:
            md = {}
        meta_author = md.get('author', '') if isinstance(md.get('author', ''), str) else ''
        meta_title = md.get('title', '') if isinstance(md.get('title', ''), str) else ''
        year = None
        # try year from metadata
        if md.get('modDate'):
            m = YEAR_RE.search(md.get('modDate'))
            if m:
                year = m.group(0)
        # fallback year from filename
        ymatch = YEAR_RE.search(entry)
        if ymatch and not year:
            year = ymatch.group(0)
        # prefer metadata; otherwise inspect first two pages
        author_guess = meta_author
        title_guess = meta_title
        reason = ''
        if not meta_author or not meta_title:
            txt = read_text_from_pdf(full, max_pages=2)
            a2, t2, y2 = infer_from_text(txt)
            if a2 and (not meta_author):
                author_guess = a2
                reason += 'inferred_author;'
            if t2 and (not meta_title):
                title_guess = t2
                reason += 'inferred_title;'
            if y2 and not year:
                year = y2
        # normalize author to Lastname, Firstname
        lastname, firstname, human = normalize_author_str(author_guess)
        # if normalization produced empty firstname but author_guess like 'matthewK' try split camel-case
        if not firstname and lastname:
            # try to split lowercase name + CapitalInitial e.g., matthewK
            m = re.match(r"^([a-z]+)([A-Z])$", lastname)
            if m:
                firstname = m.group(1)
                lastname = m.group(2)
                human = f"{lastname}, {firstname}"
        # Build target
        proposed_filename = build_target_filename(lastname, firstname, year, title_guess or entry)
        proposed_path = os.path.join(folder, proposed_filename)
        # ensure uniqueness
        base, ext = os.path.splitext(proposed_path)
        i = 1
        while os.path.exists(proposed_path) and os.path.realpath(proposed_path) != os.path.realpath(full):
            proposed_path = f"{base}-{i}{ext}"
            i += 1
        if os.path.realpath(full) == os.path.realpath(proposed_path):
            reason = reason or 'noop'
        else:
            reason = reason or 'rename'
        rows.append({
            'original_path': full,
            'proposed_path': proposed_path,
            'original_filename': entry,
            'proposed_filename': os.path.basename(proposed_path),
            'meta_author': human,
            'meta_title': title_guess,
            'reason': reason,
        })
    # write CSV
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    # if apply, perform renames and metadata writes
    if apply:
        for r in rows:
            if r['reason'] == 'noop':
                continue
            src = r['original_path']
            dst = r['proposed_path']
            if os.path.exists(dst) and os.path.realpath(dst) != os.path.realpath(src):
                print(f"SKIP - target exists: {dst}")
                continue
            try:
                os.rename(src, dst)
                print(f"APPLY {src} -> {dst}")
            except Exception as e:
                print(f"FAIL rename {src} -> {dst}: {e}")
            # write metadata author/title
            ok, msg = atomic_write_metadata(dst, r.get('meta_title'), r.get('meta_author'))
            if ok:
                print(f"OK {dst}")
            else:
                print(f"WARN metadata {dst}: {msg}")
    else:
        # summary
        planned = [r for r in rows if r['reason'] != 'noop']
        print(f"Planned items: {len(planned)}. CSV: {out_csv}")


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('folder')
    p.add_argument('--csv', default=None)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()
    folder = args.folder
    if not args.csv:
        ts = datetime.now().strftime('%Y%m%d-%H%M%S')
        args.csv = os.path.join(folder, f'metadata-rename-plan-{ts}.csv')
    process_folder(folder, args.csv, apply=args.apply)
