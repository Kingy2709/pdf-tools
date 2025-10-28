#!/usr/bin/env python3
"""Update PDF metadata (Title, Author, Keywords) and rename files.

Behavior:
- Scans a target directory for PDFs (case-insensitive).
- For each PDF, reads metadata via PyMuPDF (fitz). If missing, falls back to extracting the first page text and heuristically finding title/author/year.
- Computes a target filename using the pattern: [firstname][firstletterofsurname]-[yyyy]-[kebab-title].pdf
  e.g. kingm-2008-addisons-diagnostic-manual.pdf
- Optionally adds tags/keywords (CSV or list) to the metadata Keywords field.
- Defaults to dry-run; use --apply to perform metadata writes and renames. Writes a CSV plan/log for auditing and undo.

Requirements: PyMuPDF (pip install pymupdf)

"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as e:
    print("Missing dependency: pymupdf (fitz). Install with: pip install pymupdf", file=sys.stderr)
    raise


@dataclass
class PlanRow:
    original_path: str
    proposed_path: str
    original_author: str
    proposed_author: str
    original_title: str
    proposed_title: str
    original_keywords: str
    proposed_keywords: str
    action: str


def kebab(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s[:240]


def infer_from_first_page(pdf_path: Path) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Try to extract title, author, year from the first page text heuristically."""
    try:
        doc = fitz.open(pdf_path)
        if doc.page_count == 0:
            return None, None, None
        text = doc.load_page(0).get_text("text")
        doc.close()
    except Exception:
        return None, None, None

    # Heuristics: find year (4-digit between 1900 and 2050)
    year_match = re.search(r"\b(19\d{2}|20[0-4]\d|2050)\b", text)
    year = year_match.group(0) if year_match else None

    # Title: take first non-empty line of at least 5 chars
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = None
    if lines:
        # prefer first 1-3 lines joined if short
        candidate = lines[0]
        if len(candidate) < 30 and len(lines) > 1:
            candidate = candidate + " " + lines[1]
        title = re.sub(r"\s+", " ", candidate).strip()
        if len(title) < 5:
            title = None

    # Author: look for lines containing 'by ' or 'author'
    author = None
    for ln in lines[:20]:
        m = re.search(r"^by\s+(.+)$", ln, re.I)
        if m:
            author = m.group(1).strip()
            break
    if not author:
        for ln in lines[:20]:
            if 'author' in ln.lower():
                # take trailing words
                parts = ln.split(':')
                if len(parts) > 1:
                    author = parts[1].strip()
                    break

    return title, author, year


def normalize_author(author_raw: Optional[str]) -> Tuple[str, str, str]:
    """Return (lastname, surname_initial, human_readable) for a given raw author string.

    - human_readable will be 'Lastname, Firstname' (sorting-friendly) when possible.
    - lastname is cleaned and trimmed for filenames (alphabetic only, lowercased by caller where needed).
    - initial is the first letter of the firstname (used as capital initial in filenames).

    Handles inputs like 'First Last', 'Last, First', 'Last, F.', multi-author strings (keeps first),
    and removes 'et al.' or trailing 'and ...'. Falls back to Unknown values when parsing fails.
    """
    if not author_raw:
        return "unknown", "u", "Unknown, Unknown"

    s = author_raw.strip()
    # remove common noise
    s = re.sub(r"et\s+al\.?", "", s, flags=re.I)
    s = re.sub(r"\band\b.*$", "", s, flags=re.I)
    s = s.replace(';', ',')

    # split on common separators and prefer the first element as the primary author
    parts = [p.strip() for p in re.split(r"[\n/\\|]", s) if p.strip()]
    if not parts:
        return "unknown", "u", "Unknown, Unknown"

    primary = parts[0]

    # If primary contains a comma it's likely 'Last, First' or 'Last, F.'
    firstname = None
    lastname = None
    if ',' in primary:
        left, right = [p.strip() for p in primary.split(',', 1)]
        # left is likely surname, right contains given names/initials
        lastname = left
        # take first token from right as firstname candidate
        firstname = re.sub(r"\.|,", "", right).split()[0] if right else None
    else:
        # normalize hyphens/underscores to spaces then split tokens
        clean = re.sub(r"[-_]+", " ", primary)
        tokens = [t for t in clean.split() if t]
        if len(tokens) == 0:
            return "unknown", "u", "Unknown, Unknown"
        if len(tokens) == 1:
            # single token - could be surname or given name; treat as surname fallback
            lastname = tokens[0]
            firstname = tokens[0]
        else:
            # prefer first token as firstname and last token as surname
            firstname = tokens[0]
            lastname = tokens[-1]

    # ensure values are strings before regex ops
    firstname = firstname or "Unknown"
    lastname = lastname or "Unknown"
    # sanitize
    firstname = (re.sub(r"[^A-Za-z]", "", firstname) or "Unknown").strip()
    lastname = (re.sub(r"[^A-Za-z]", "", lastname) or "Unknown").strip()

    # human-readable metadata: 'Lastname, Firstname'
    human = f"{lastname.title()}, {firstname.title()}"

    # initial is first letter of firstname (uppercase when used)
    initial = (firstname[0] if firstname else 'U')

    # limit lastname length for filenames
    if len(lastname) > 30:
        lastname = lastname[:30]

    return lastname, initial, human


def build_target_filename(firstname: str, initial: str, year: Optional[str], title: str, max_len: int = 200) -> str:
    """Build a safe filename ensuring total length (bytes) is under max_len.

    Strategy: reserve space for prefix (firstname+initial-year-) and suffix '.pdf', then truncate kebab(title) to fit.
    """
    y = year if year else '0000'
    # 'firstname' parameter is used as the lastname token here (caller passes lastname)
    # enforce lowercase lastname in filename for consistency (e.g., 'kingM-0000-...')
    lastname = firstname.lower()
    prefix = f"{lastname}{initial.upper()}-{y}-"
    suffix = ".pdf"
    # allowed bytes for title (approx chars since ascii) - be conservative
    allowed = max_len - len(prefix) - len(suffix)
    if allowed < 10:
        # fallback to very short firstname to allow some title
        firstname = firstname[:1]
        prefix = f"{firstname}{initial}-{y}-"
        allowed = max_len - len(prefix) - len(suffix)
        if allowed < 6:
            # give up and use a fixed short name
            return f"{firstname}{initial}-{y}-doc.pdf"

    safe_title = kebab(title)[:allowed]
    # ensure no leading/trailing hyphen issues
    safe_title = safe_title.strip('-') or 'doc'
    return f"{prefix}{safe_title}{suffix}"


def read_pdf_metadata(path: Path) -> Tuple[str, str, str]:
    try:
        doc = fitz.open(path)
        meta = doc.metadata
        doc.close()
        author = meta.get('author') or ''
        title = meta.get('title') or ''
        keywords = meta.get('keywords') or ''
        return title.strip(), author.strip(), keywords.strip()
    except Exception:
        return '', '', ''


def write_pdf_metadata(path: Path, title: str, author: str, keywords: str) -> None:
    doc = fitz.open(path)
    meta = doc.metadata
    meta['title'] = title
    meta['author'] = author
    meta['keywords'] = keywords
    doc.set_metadata(meta)
    # save in place
    doc.save(path, garbage=4, deflate=True)
    doc.close()


def unique_path(p: Path) -> Path:
    if not p.exists():
        return p
    stem = p.stem
    parent = p.parent
    i = 2
    while True:
        candidate = parent / f"{stem}-{i}{p.suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def process_folder(root: Path, tags: List[str], apply: bool = False) -> List[PlanRow]:
    rows: List[PlanRow] = []
    now = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if p.suffix.lower() != '.pdf':
            continue

        title_meta, author_meta, keywords_meta = read_pdf_metadata(p)
        title = title_meta or None
        author = author_meta or None
        year = None

        if not title or not author:
            t2, a2, y2 = infer_from_first_page(p)
            title = title or t2
            author = author or a2
            year = year or y2

        # fallback to filename parsing for title/year
        if not title:
            # strip suffixes like -draft etc
            title = re.sub(r"[-_]+(draft|v\d+|final)$", "", p.stem, flags=re.I)
            title = title.replace('-', ' ')

        # try to extract year from filename if still missing
        if not year:
            m = re.search(r"(19\d{2}|20\d{2})", p.stem)
            if m:
                year = m.group(0)

        # normalize author
        lastname, initial, human = normalize_author(author)

        # requested format filename: lastname + capitalized first initial
        proposed_name = build_target_filename(lastname, initial, year, title)
        proposed_path = p.parent / proposed_name
        if proposed_path.exists() and proposed_path.samefile(p):
            action = 'noop'
        else:
            if proposed_path.exists():
                proposed_path = unique_path(proposed_path)
            action = 'rename'

        # tags -> keywords concat
        existing_keywords = keywords_meta or ''
        extra = ','.join(tags) if tags else ''
        proposed_keywords = ','.join([kw for kw in [existing_keywords, extra] if kw])

        row = PlanRow(
            original_path=str(p),
            proposed_path=str(proposed_path),
            original_author=author_meta or '',
            proposed_author=human,
            original_title=title_meta or '',
            proposed_title=title or '',
            original_keywords=existing_keywords,
            proposed_keywords=proposed_keywords,
            action=action,
        )
        rows.append(row)

        if apply and action == 'rename':
            # write metadata then rename
            try:
                write_pdf_metadata(p, row.proposed_title, row.proposed_author, row.proposed_keywords)
            except Exception as e:
                print(f"Warning: failed to write metadata for {p}: {e}", file=sys.stderr)
            try:
                p.rename(Path(row.proposed_path))
            except Exception as e:
                print(f"Warning: failed to rename {p} -> {row.proposed_path}: {e}", file=sys.stderr)

    return rows


def write_csv_log(rows: List[PlanRow], root: Path) -> Path:
    now = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = root / f"metadata-rename-plan-{now}.csv"
    with out.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['original_path', 'proposed_path', 'original_author', 'proposed_author', 'original_title', 'proposed_title', 'original_keywords', 'proposed_keywords', 'action'])
        for r in rows:
            w.writerow([r.original_path, r.proposed_path, r.original_author, r.proposed_author, r.original_title, r.proposed_title, r.original_keywords, r.proposed_keywords, r.action])
    return out


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description='Update PDF metadata and rename to firstname+initial-year-title')
    p.add_argument('root', nargs='?', default=str(Path.home() / 'Documents' / 'clinic' / 'research-articles' / 'flat-20250919-210028'))
    p.add_argument('--tags', '-t', nargs='*', default=[], help='Tags/keywords to add to the Keywords metadata (comma will be preserved)')
    p.add_argument('--apply', action='store_true', help='Apply changes (write metadata and rename). Default: dry-run')
    args = p.parse_args(argv)

    root = Path(args.root).expanduser()
    if not root.exists():
        print(f"Root folder {root} does not exist", file=sys.stderr)
        return 2

    rows = process_folder(root, args.tags, apply=args.apply)
    csv_path = write_csv_log(rows, root)
    # print summary
    print(f"Planned items: {len(rows)}; log: {csv_path}")
    # show a short preview
    for r in rows[:200]:
        print(r.action.ljust(8), r.original_path, '->', r.proposed_path)

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
