#!/usr/bin/env python3
"""
verify_csv_safe.py

Safer version of verify_csv_vs_disk.py that catches OSError (e.g. filename too long)
and reports those rows instead of crashing.

Usage:
  python verify_csv_safe.py /path/to/metadata-rename-plan.csv

"""
import argparse
import csv
from pathlib import Path

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
    except Exception as e:
        return {"_error": str(e)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=str)
    p.add_argument("--sample", type=int, default=10)
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
    filename_errors = []

    for r in rows:
        prop = r.get("proposed_path") or r.get("new_path") or r.get("proposed") or r.get("target_path")
        prop_author = r.get("proposed_author") or r.get("author")
        prop_title = r.get("proposed_title") or r.get("title")
        if not prop:
            continue
        ppath = Path(prop)
        try:
            exists = ppath.exists()
        except OSError as e:
            filename_errors.append((prop, str(e), r))
            continue
        if not exists:
            filename_missing.append((prop, r))
            continue
        # actual filename check (redundant but kept for parity)
        try:
            if ppath.name != Path(prop).name:
                filename_mismatch.append((str(ppath), r))
        except OSError as e:
            filename_errors.append((prop, str(e), r))
            continue
        # metadata
        md = get_pdf_metadata(ppath)
        if md.get("_error"):
            # metadata read failed; record as filename_errors for attention
            filename_errors.append((str(ppath), md.get("_error"), r))
            continue
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
    print(f"Filename / metadata read errors (OSError or read failure): {len(filename_errors)}")

    def show_samples(lst, name):
        if not lst:
            return
        print(f"\nSample {name} (up to {args.sample}):")
        for item in lst[:args.sample]:
            print(item)

    show_samples(filename_errors, "filename/metadata errors")
    show_samples(filename_missing, "missing files")
    show_samples(filename_mismatch, "filename mismatches")
    show_samples(meta_author_mismatch, "author metadata mismatches")
    show_samples(meta_title_mismatch, "title metadata mismatches")


if __name__ == '__main__':
    main()
