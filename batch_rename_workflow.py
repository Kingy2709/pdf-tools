#!/usr/bin/env python3
"""Batch rename workflow - cleaned single source of truth.

Behavior changes made per user request:
- Prefer embedded PDF metadata (title, author, year) as the single source of truth.
- Only fall back to text inference when metadata fields are missing.
- Remove journal short from the filename (journal may remain in metadata).
- Dry-run by default; use --apply to perform file operations.
- Optional --limit to apply only first N planned moves (useful for safe samples).

Logs: writes CSVs to the provided logs directory:
- rename-log-<ts>.csv with columns src,dst,status,notes
- metadata-diffs-<ts>.csv with columns path,meta,inferred (when metadata differs)
- duplicates-<ts>.csv when duplicates moved
- remaining-<ts>.csv listing files left in src after run

This file is a consolidated and tested implementation.
"""

import argparse
import csv
import hashlib
import os
import re
import shutil
import time
from typing import List, Tuple, Optional
import json
import urllib.request
import urllib.error

try:
    import fitz
except Exception:
    fitz = None

STOPWORDS = set(['and','or','if','then','the','a','an','of','in','on','for','to','with','is','that'])


def ensure_dirs(*paths: str) -> None:
    for p in paths:
        os.makedirs(p, exist_ok=True)


def copy_backup(src: str, backup_root: str, dry_run: bool) -> str:
    ts = time.strftime('%Y%m%d-%H%M%S')
    dest = os.path.join(backup_root, f'backup-{ts}')
    if dry_run:
        return dest
    shutil.copytree(src, dest)
    return dest


def flatten_folder(root: str, dry_run: bool) -> List[Tuple[str, str]]:
    moved = []
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        for f in filenames:
            src = os.path.join(dirpath, f)
            dest = os.path.join(root, f)
            if os.path.exists(dest):
                name, ext = os.path.splitext(f)
                i = 1
                while os.path.exists(dest):
                    dest = os.path.join(root, f"{name}-{i}{ext}")
                    i += 1
            if not dry_run:
                shutil.move(src, dest)
            moved.append((src, dest))
    # remove now-empty dirs
    for dirpath, _, _ in os.walk(root, topdown=False):
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        try:
            if not os.listdir(dirpath) and not dry_run:
                os.rmdir(dirpath)
        except Exception:
            pass
    return moved


def fix_bad_suffixes(root: str, dry_run: bool) -> List[Tuple[str, str]]:
    fixed = []
    for f in os.listdir(root):
        p = os.path.join(root, f)
        if not os.path.isfile(p):
            continue
        if f.endswith('_') or f.endswith('.pdf_') or not re.search(r'\.[Pp][Dd][Ff]$', f):
            new = f.rstrip('_.')
            if not re.search(r'\.[Pp][Dd][Ff]$', new):
                new = new + '.pdf'
            newp = os.path.join(root, new)
            if os.path.abspath(newp) == os.path.abspath(p):
                continue
            if not dry_run:
                os.rename(p, newp)
            fixed.append((p, newp))
    return fixed


def read_pdf_metadata(path: str) -> dict:
    meta = {'title': '', 'author': '', 'year': ''}
    if fitz is None:
        return meta
    try:
        doc = fitz.open(path)
        info = doc.metadata or {}
        meta['title'] = (info.get('title') or '').strip()
        meta['author'] = (info.get('author') or '').strip()
        # try common date fields
        created = info.get('creationDate') or info.get('modDate') or ''
        m = re.search(r'(19|20)\d{2}', created)
        if m:
            meta['year'] = m.group(0)[-2:]
        doc.close()
    except Exception:
        pass
    return meta


def read_text_from_pdf(path: str, max_pages: int = 2) -> str:
    if fitz is None:
        return ''
    try:
        doc = fitz.open(path)
        text = []
        for i in range(min(max_pages, doc.page_count)):
            page = doc.load_page(i)
            text.append(page.get_text('text'))
        doc.close()
        return '\n'.join(text)
    except Exception:
        return ''


DOI_RE = re.compile(r'10\.\d{4,9}/[\w.\-;()/:]+', re.IGNORECASE)


def find_doi_in_text(text: str) -> Optional[str]:
    if not text:
        return None
    m = DOI_RE.search(text)
    if m:
        doi = m.group(0).rstrip('.,;')
        return doi
    return None


def crossref_lookup(doi: str, timeout: int = 10) -> Optional[dict]:
    """Query CrossRef API for canonical metadata for a DOI. Returns dict with keys:
    title (str), authors (list of dict with 'family'/'given'), year (str), journal (str)
    Returns None on network error or not found.
    """
    if not doi:
        return None
    url = 'https://api.crossref.org/works/' + urllib.request.quote(doi, safe='')
    req = urllib.request.Request(url, headers={'User-Agent': 'pdf-renamer/1.0 (mailto:you@example.com)'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.load(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
        return None
    item = data.get('message', {})
    out = {}
    # title is often a list
    title = item.get('title') or []
    out['title'] = title[0] if title else ''
    authors = item.get('author') or []
    out['authors'] = authors
    # get year
    year = ''
    if 'published-print' in item and item['published-print'].get('date-parts'):
        year = str(item['published-print']['date-parts'][0][0])
    elif 'published-online' in item and item['published-online'].get('date-parts'):
        year = str(item['published-online']['date-parts'][0][0])
    elif item.get('issued') and item['issued'].get('date-parts'):
        year = str(item['issued']['date-parts'][0][0])
    out['year'] = year
    container = item.get('container-title') or []
    out['journal'] = container[0] if container else ''
    return out


def infer_from_text(text: str) -> Tuple[str, str, str]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else ''
    author = lines[1] if len(lines) > 1 else ''
    yy = ''
    for l in lines[:6]:
        m = re.search(r'\b(19|20)\d{2}\b', l)
        if m:
            yy = m.group(0)[-2:]
            break
    return title, author, yy


def normalize_author_to_lastname(author_str: str) -> str:
    if not author_str:
        return 'unknown'
    s = re.sub(r'[\(\)\[\],;]', ' ', author_str)
    parts = [p for p in s.split() if p]
    if not parts:
        return 'unknown'
    lastname = parts[-1].lower()
    lastname = re.sub(r'[^a-z0-9\-]', '', lastname)
    return lastname or 'unknown'


def clean_title_for_filename(title: str) -> str:
    s = title.lower()
    s = re.sub(r'[\t\n\r]+', ' ', s)
    s = re.sub(r'["\\/:*?<>|,.;()\[\]]+', '', s)
    words = [w for w in s.split() if w not in STOPWORDS]
    # collapse multiple spaces and strip
    return ' '.join(words).strip()


def build_target_filename(lastname: str, yy: str, title_clean: str, max_total: int = 220) -> str:
    # New rule: lastname-yy-title.pdf (no journal)
    parts = [lastname]
    if yy:
        parts.append(yy)
    if title_clean:
        parts.append(title_clean)
    name = '-'.join(parts) + '.pdf'
    name = re.sub(r'[\n\r]+', ' ', name).strip()
    if len(name) > max_total:
        hash_tail = hashlib.sha1(name.encode('utf-8')).hexdigest()[:8]
        keep = max_total - len(hash_tail) - 5
        name = name[:keep].rstrip()
        name = f"{name}-{hash_tail}.pdf"
    return name


def sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        while True:
            b = fh.read(8192)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def detect_duplicates_by_hash(paths: List[str]) -> List[Tuple[str, str, str]]:
    seen = {}
    dups = []
    for p in paths:
        try:
            h = sha1_file(p)
        except Exception:
            continue
        if h in seen:
            dups.append((p, seen[h], h))
        else:
            seen[h] = p
    return dups


def write_csv(path: str, rows: List[List[str]], header: Optional[List[str]] = None) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as fh:
        w = csv.writer(fh)
        if header:
            w.writerow(header)
        w.writerows(rows)
    return path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--backup', required=True)
    ap.add_argument('--logs', required=True)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--skip-backup', action='store_true', help='Do not create a fresh backup (assume existing backup present)')
    ap.add_argument('--limit', type=int, default=0, help='If >0, only perform moves for first N planned rows')
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    out = os.path.abspath(args.out)
    backup = os.path.abspath(args.backup)
    logs = os.path.abspath(args.logs)
    dry_run = not args.apply
    limit = args.limit
    skip_backup = bool(args.skip_backup)

    ensure_dirs(out, backup, logs)

    print(f"Starting batch rename workflow (dry_run={dry_run})")

    # 1. backup
    if skip_backup:
        print('Skipping fresh backup (user requested --skip-backup)')
        backup_dest = backup
    else:
        print('Backing up source...')
        backup_dest = copy_backup(src, backup, dry_run=dry_run)
        print('Backup destination:', backup_dest)

    # 2. flatten and fix
    z_moved = []
    print('Extracted files from zip count:', len(z_moved))
    flattened = flatten_folder(src, dry_run=dry_run)
    print('Flattened files count:', len(flattened))
    fixed = fix_bad_suffixes(src, dry_run=dry_run)
    print('Fixed bad suffixes count:', len(fixed))

    # build mapping of top-level pdfs (basename -> path)
    simulated_dests = {}
    for _s, dest in flattened:
        simulated_dests[os.path.basename(dest)] = dest
    for _s, dest in z_moved:
        simulated_dests[os.path.basename(dest)] = dest
    for _s, dest in fixed:
        simulated_dests[os.path.basename(dest)] = dest
    for entry in os.listdir(src):
        ab = os.path.join(src, entry)
        if os.path.isfile(ab) and entry.lower().endswith('.pdf'):
            simulated_dests.setdefault(entry, ab)

    top_level_sim = sorted([n for n in simulated_dests.keys() if n.lower().endswith('.pdf')])
    print('Simulated top-level PDF count:', len(top_level_sim))
    print('First 30 simulated PDFs:', top_level_sim[:30])

    planned_rows: List[List[str]] = []
    metadata_diffs: List[List[str]] = []

    for name in top_level_sim:
        src_path = simulated_dests.get(name, os.path.join(src, name))
        # guard: skip files that disappeared during flatten/apply
        if not os.path.exists(src_path):
            planned_rows.append([src_path, '', 'missing', 'source-missing'])
            continue

        # Read metadata first (single source of truth)
        meta = read_pdf_metadata(src_path)
        text = ''
        if not meta.get('title') or not meta.get('author'):
            text = read_text_from_pdf(src_path, max_pages=2)
        inferred_title, inferred_author, inferred_yy = infer_from_text(text)

        # Try to find DOI in text or metadata and query CrossRef for canonical metadata
        doi = find_doi_in_text((meta.get('keywords') or '') + '\n' + text)
        crossref = None
        if doi:
            crossref = crossref_lookup(doi)

        if crossref:
            # CrossRef wins as canonical source
            final_title = crossref.get('title') or inferred_title or os.path.splitext(name)[0]
            # choose first author family name if present
            authors = crossref.get('authors') or []
            if authors and isinstance(authors, list) and authors[0].get('family'):
                final_author = authors[0].get('family')
            else:
                final_author = inferred_author or meta.get('author') or ''
            y = crossref.get('year') or ''
            final_yy = y[-2:] if y else (meta.get('year') or inferred_yy or '')
        else:
            # prefer metadata; fall back to inferred where missing
            final_title = meta.get('title') or inferred_title or os.path.splitext(name)[0]
            final_author = meta.get('author') or inferred_author or ''
            final_yy = meta.get('year') or inferred_yy or ''

        lastname = normalize_author_to_lastname(final_author)
        title_for_file = clean_title_for_filename(final_title)
        target_name = build_target_filename(lastname, final_yy, title_for_file)
        dst = os.path.join(out, target_name)

        notes = []
        if meta.get('title') and inferred_title and meta.get('title').strip() != inferred_title.strip():
            notes.append('title-infer-diff')
            metadata_diffs.append([src_path, meta.get('title'), inferred_title])
        if meta.get('author') and inferred_author and meta.get('author').strip() != inferred_author.strip():
            notes.append('author-infer-diff')
            metadata_diffs.append([src_path, meta.get('author'), inferred_author])

        status = 'would-move'
        planned_rows.append([src_path, dst, status, ';'.join(notes)])

    # if limit provided, slice planned_rows for moves only (but keep full logs for audit)
    to_do_rows = [r for r in planned_rows if r[2] == 'would-move']
    if limit and limit > 0:
        limited_set = set([r[0] for r in to_do_rows[:limit]])
    else:
        limited_set = None

    # perform moves (or dry-run)
    performed_rows: List[List[str]] = []
    move_count = 0
    for src_p, dst_p, st, notes in planned_rows:
        if st != 'would-move':
            performed_rows.append([src_p, dst_p, st, notes])
            continue
        if limited_set is not None and src_p not in limited_set:
            # we're skipping this due to limit
            performed_rows.append([src_p, dst_p, 'skipped-limit', notes])
            continue
        target = dst_p
        # ensure unique dst
        base_dst = target
        i = 1
        while os.path.exists(target):
            name_only, ext = os.path.splitext(base_dst)
            target = f"{name_only}-{i}{ext}"
            i += 1
        try:
            if not dry_run:
                ensure_dirs(out)
                shutil.move(src_p, target)
                performed_rows.append([src_p, target, 'moved', notes])
                move_count += 1
            else:
                performed_rows.append([src_p, target, 'would-move', notes])
        except Exception as e:
            performed_rows.append([src_p, dst_p, 'error', str(e)])

    ts = time.strftime('%Y%m%d-%H%M%S')
    rename_log = os.path.join(logs, f'rename-log-{ts}.csv')
    write_csv(rename_log, performed_rows, header=['src', 'dst', 'status', 'notes'])
    print('Wrote rename log:', rename_log)

    if metadata_diffs:
        md_log = os.path.join(logs, f'metadata-diffs-{ts}.csv')
        write_csv(md_log, metadata_diffs, header=['path', 'meta', 'inferred'])
        print('Wrote metadata diffs:', md_log)

    # duplicates in out
    out_files = [os.path.join(out, f) for f in os.listdir(out) if f.lower().endswith('.pdf')]
    dups = detect_duplicates_by_hash(out_files)
    if dups:
        dup_rows = []
        dupfolder = os.path.join(backup, f'duplicates-{ts}')
        ensure_dirs(dupfolder)
        for srcp, keep, h in dups:
            try:
                s1 = os.path.getsize(srcp)
                s2 = os.path.getsize(keep)
            except Exception:
                s1 = s2 = 0
            to_move = srcp if s1 <= s2 else keep
            if not dry_run:
                dest = os.path.join(dupfolder, os.path.basename(to_move))
                i = 1
                while os.path.exists(dest):
                    name, ext = os.path.splitext(dest)
                    dest = f"{name}-{i}{ext}"
                    i += 1
                shutil.move(to_move, dest)
            dup_rows.append([to_move, keep, h])
        dup_log = os.path.join(logs, f'duplicates-{ts}.csv')
        write_csv(dup_log, dup_rows, header=['moved', 'kept', 'sha1'])
        print('Moved duplicates count', len(dup_rows), 'to', dupfolder)

    remaining = [f for f in os.listdir(src) if os.path.isfile(os.path.join(src, f))]
    remain_log = os.path.join(logs, f'remaining-{ts}.csv')
    write_csv(remain_log, [[r] for r in remaining], header=['remaining'])
    print('Remaining files in src (count):', len(remaining))

    print('Done. dry_run=%s. moved=%d. logs in %s' % (dry_run, move_count, logs))


if __name__ == '__main__':
    main()

