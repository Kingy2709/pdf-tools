#!/usr/bin/env python3
"""
fix_filenames_lastname.py

Scans a metadata-rename CSV and fixes filenames that used a single-letter
lastname initial (e.g., "kM-2009-adhd.pdf") to the full lastname with the same
capital initial ("kingM-2009-adhd.pdf").

The script is conservative: it only renames when the CSV contains both the
original filename and the intended `proposed_author` (like "King, Michael") so
we can deterministically build the correct new filename.

Usage:
  python fix_filenames_lastname.py /path/to/metadata-rename-plan.csv [--apply]

Dry-run by default. Use --apply to perform filesystem renames.
"""
import argparse
import csv
from pathlib import Path
import re


def build_expected_filename_from_author(author: str, year: str, title: str) -> str:
    # author expected like "Lastname, Firstname" or "Lastname"
    # filename policy: lowercase(lastname) + CapitalInitial + '-' + year + '-' + kebab(title) + '.pdf'
    lastname = author.split(",")[0].strip() if "," in author else author.strip()
    initial = (author.split(",")[-1].strip()[0] if "," in author and author.split(",")[-1].strip() else lastname[0].upper())
    # ensure initial uppercase
    initial = initial.upper()
    # kebab simple: lowercase words, keep alnum, replace spaces with '-'
    t = title or ""
    t = re.sub(r"[^A-Za-z0-9 ]+", "", t)
    t = re.sub(r"\s+", "-", t.strip().lower())
    return f"{lastname.lower()}{initial}-{year}-{t}.pdf"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=str, help="Path to renamer CSV")
    p.add_argument("--apply", action="store_true", help="Actually perform renames")
    args = p.parse_args()

    csvp = Path(args.csv)
    if not csvp.exists():
        print("CSV not found:", csvp)
        return

    with csvp.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        header = [h.lower() for h in (rdr.fieldnames or [])]
        # detect columns
        proposed_col = None
        orig_col = None
        author_col = None
        title_col = None
        year_col = None
        for name in header:
            if name in ("proposed_path", "new_path", "proposed"):
                proposed_col = name
            if name in ("original_path", "original", "src_path"):
                orig_col = name
            if name in ("proposed_author", "author", "proposed_author_name"):
                author_col = name
            if name in ("proposed_title", "title"):
                title_col = name
            if name in ("year", "proposed_year", "pub_year"):
                year_col = name

        # Fallback guesses
        if proposed_col is None:
            for cand in ("new_path", "proposed_path", "proposed"):
                if cand in header:
                    proposed_col = cand
                    break
        if orig_col is None:
            for cand in ("original_path", "original"):
                if cand in header:
                    orig_col = cand
                    break
        if author_col is None:
            for cand in ("proposed_author", "author"):
                if cand in header:
                    author_col = cand
                    break
        if title_col is None:
            for cand in ("proposed_title", "title"):
                if cand in header:
                    title_col = cand
                    break
        if year_col is None:
            for cand in ("year", "proposed_year", "pub_year"):
                if cand in header:
                    year_col = cand
                    break

        if proposed_col is None and orig_col is None:
            print("Could not find proposed_path/new_path or original_path in CSV header:", rdr.fieldnames)
            return

        fixes = []
        for r in rdr:
            proposed = r.get(proposed_col) if proposed_col else None
            orig = r.get(orig_col) if orig_col else None
            if proposed:
                fname = Path(proposed).name
            elif orig:
                fname = Path(orig).name
            else:
                continue

            # detect pattern like single-letter lastname then capital initial: e.g., kM-2009-adhd.pdf
            m = re.match(r"^([a-z])( [A-Z])?([A-Z])-([0-9]{4}|0000)-(.+)$", fname)
            # Simpler detection: starts with 1 lowercase letter followed by 1 uppercase letter then '-'
            if re.match(r"^[a-z][A-Z]-", fname):
                # Need author to patch
                author = r.get(author_col) if author_col else None
                title = r.get(title_col) if title_col else ''
                year = r.get(year_col) if year_col else '0000'
                if not author:
                    # cannot reliably reconstruct
                    continue
                expected = build_expected_filename_from_author(author, year, title)
                if expected == fname:
                    # already ok
                    continue
                # If current fname starts with single-letter prefix, craft new path
                new_name = expected
                # folder
                folder = Path(proposed or orig).parent
                old_path = Path(proposed or orig)
                new_path = folder / new_name
                fixes.append((old_path, new_path))

        print(f"Planned fixes: {len(fixes)}")
        for oldp, newp in fixes:
            print(("DRY-RUN" if not args.apply else "APPLY"), oldp.name, "->", newp.name)
            if args.apply:
                if newp.exists():
                    print("SKIP - target exists:", newp)
                    continue
                oldp.rename(newp)

if __name__ == "__main__":
    main()
