#!/usr/bin/env python3
"""
verify_csv_vs_disk.py

Compares the renamer CSV against the files on disk and the PDF metadata (Author, Title).
Reports counts and sample mismatches for:
 - filename mismatch (proposed_path doesn't exist or real filename differs)
 - metadata mismatch (author/title in PDF vs proposed)

Usage:
  python verify_csv_vs_disk.py /path/to/metadata-rename-plan.csv

Requires PyMuPDF (fitz) installed to inspect PDF metadata; if not available the script
will only check filenames.
"""
import argparse
import csv
from pathlib import Path
from collections import Counter

try:
    import fitz
except Exception:
    fitz = None


def get_pdf_metadata(path: Path):
    if fitz is None:
        return {}
    try:
        d = fitz.open(str(path))
        md = d.metadata or {}
        d.close()
        return {k.lower(): (v or "").strip() for k, v in md.items()}
    except Exception:
        return {}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=str)
    p.add_argument("--sample", type=int, default=10, help="Number of sample mismatches to show")
    args = p.parse_args()

    csvp = Path(args.csv)
    if not csvp.exists():
        print("CSV not found:", csvp)
        return

    rows = []
    with csvp.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)

    total = len(rows)
    filename_missing = []
    filename_mismatch = []
    meta_author_mismatch = []
    meta_title_mismatch = []

    for r in rows:
        # guess columns
        prop = r.get("proposed_path") or r.get("new_path") or r.get("proposed") or r.get("target_path")
        prop_author = r.get("proposed_author") or r.get("author")
        prop_title = r.get("proposed_title") or r.get("title")
        if not prop:
            continue
        ppath = Path(prop)
        if not ppath.exists():
            filename_missing.append((prop, r))
            continue
        # check actual filename vs expected basename
        if ppath.name != Path(prop).name:
            filename_mismatch.append((str(ppath), r))
        # check metadata
        md = get_pdf_metadata(ppath)
        author = md.get("author", "")
        title = md.get("title", "")
        if prop_author and prop_author.strip() and prop_author.strip() != author.strip():
            meta_author_mismatch.append((str(ppath), prop_author, author))
        if prop_title and prop_title.strip() and prop_title.strip() != title.strip():
            meta_title_mismatch.append((str(ppath), prop_title, title))

    print(f"Rows checked: {total}")
    print(f"Files missing (proposed path doesn't exist): {len(filename_missing)}")
    print(f"Filename mismatches: {len(filename_mismatch)}")
    print(f"Author metadata mismatches: {len(meta_author_mismatch)}")
    print(f"Title metadata mismatches: {len(meta_title_mismatch)}")

    def show_samples(lst, name):
        if not lst:
            return
        print(f"\nSample {name} (up to {args.sample}):")
        for item in lst[:args.sample]:
            print(item)

    show_samples(filename_missing, "missing files")
    show_samples(filename_mismatch, "filename mismatches")
    show_samples(meta_author_mismatch, "author metadata mismatches")
    show_samples(meta_title_mismatch, "title metadata mismatches")

if __name__ == '__main__':
    main()
