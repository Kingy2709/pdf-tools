#!/usr/bin/env python3
"""
retry_atomic_metadata.py

Reads a metadata-rename CSV produced by your renamer and re-applies metadata writes
using a temp-file + atomic os.replace() strategy to avoid "save to original must be
incremental" errors.

Usage:
  python retry_atomic_metadata.py /path/to/metadata-rename-plan-YYYYMMDD-HHMMSS.csv

This script does not rename files; it only (re)writes metadata for the "proposed" files
listed in the CSV. It runs in dry-run mode by default; pass --apply to actually write.

It depends on PyMuPDF (fitz).
"""
import argparse
import csv
import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import fitz
except Exception as e:
    fitz = None


def write_pdf_metadata(path: Path, title: Optional[str] = None, author: Optional[str] = None,
                       keywords: Optional[str] = None, atomic: bool = True) -> bool:
    """
    Write metadata to PDF at `path`.
    Returns True on success, False on failure.
    By default uses atomic=True which saves to a temp file in the same directory then
    os.replace() to the original path.
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not available in this environment")

    meta = {}
    if title is not None:
        meta["title"] = str(title)
    if author is not None:
        meta["author"] = str(author)
    if keywords is not None:
        meta["keywords"] = str(keywords)

    doc = None
    tmp_path = None
    try:
        doc = fitz.open(str(path))
        existing = doc.metadata or {}
        existing.update({k: v for k, v in meta.items() if v is not None})
        doc.set_metadata(existing)

        if not atomic:
            try:
                # incremental save - may fail on some PDFs
                doc.saveIncr()
                return True
            except Exception:
                pass

        # atomic path: save to temp file in same dir then replace
        dirpath = path.parent
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(dirpath))
        os.close(fd)
        tmp_path = Path(tmp_name)
        doc.save(str(tmp_path))
        doc.close()
        doc = None
        # Ensure permissions/stat are preserved if desired
        try:
            import shutil
            shutil.copystat(str(path), str(tmp_path))
        except Exception:
            pass
        os.replace(str(tmp_path), str(path))
        tmp_path = None
        return True
    except Exception as e:
        # Caller may log details
        return False
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


def find_failure_column(fieldnames):
    """Try common column names indicating metadata write success/failure."""
    lower = [c.lower() for c in fieldnames]
    candidates = [
        "metadata_success",
        "metadata_written",
        "metadata_ok",
        "metadata_applied",
        "meta_ok",
        "meta_written",
        "metadata_write_ok",
        "write_metadata_ok",
    ]
    for cand in candidates:
        if cand in lower:
            return fieldnames[lower.index(cand)]
    for name in fieldnames:
        if "meta" in name.lower() and "success" in name.lower():
            return name
    return None


def find_proposed_path_col(fieldnames):
    lower = [c.lower() for c in fieldnames]
    for cand in ("proposed_path", "new_path", "proposed", "proposed_filepath", "target_path"):
        if cand in lower:
            return fieldnames[lower.index(cand)]
    return None


def find_proposed_author_col(fieldnames):
    lower = [c.lower() for c in fieldnames]
    for cand in ("proposed_author", "author", "proposed_author_name"):
        if cand in lower:
            return fieldnames[lower.index(cand)]
    return None


def find_proposed_title_col(fieldnames):
    lower = [c.lower() for c in fieldnames]
    for cand in ("proposed_title", "title"):
        if cand in lower:
            return fieldnames[lower.index(cand)]
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=str, help="Path to metadata-rename CSV produced by renamer")
    p.add_argument("--apply", action="store_true", help="Actually write metadata; default is dry-run")
    p.add_argument("--atomic", action="store_true", default=True, help="Force atomic temp-file write (default: True)")
    args = p.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print("CSV not found:", csv_path)
        raise SystemExit(2)

    rows = []
    with csv_path.open("r", newline="") as f:
        rdr = csv.DictReader(f)
        fieldnames = rdr.fieldnames or []
        fail_col = find_failure_column(fieldnames)
        prop_col = find_proposed_path_col(fieldnames)
        author_col = find_proposed_author_col(fieldnames)
        title_col = find_proposed_title_col(fieldnames)

        if prop_col is None:
            print("Could not detect proposed_path/new_path column. CSV header:", fieldnames)
            raise SystemExit(2)

        for r in rdr:
            # treat missing/blank as failure
            meta_ok = True
            if fail_col:
                val = (r.get(fail_col) or "").strip().lower()
                if val in ("false", "0", "no", "n", ""):
                    meta_ok = False
            # If no fail_col, we'll attempt to rewrite metadata for all rows
            if not meta_ok or fail_col is None:
                rows.append(r)

    print(f"Found {len(rows)} candidate rows to (re)write metadata")
    if not rows:
        return

    for r in rows:
        proposed = Path(r.get(prop_col) or "")
        if not proposed.exists():
            print("Skipping missing file:", proposed)
            continue
        author = r.get(author_col) if author_col else None
        title = r.get(title_col) if title_col else None
        print(("DRY-RUN" if not args.apply else "APPLY"), proposed, f"author={author!r}", f"title={title!r}")
        if args.apply:
            ok = write_pdf_metadata(proposed, title=title, author=author, atomic=args.atomic)
            print(("OK" if ok else "FAIL"), proposed)


if __name__ == "__main__":
    main()
