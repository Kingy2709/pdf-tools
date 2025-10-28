#!/usr/bin/env python3
"""Revert renames and metadata writes produced by update_pdf_metadata_and_rename.py

Usage:
  revert_pdf_metadata_and_renames.py <plan.csv> [--apply]

Behavior:
- Reads the CSV plan with the same columns written by the renamer.
- For each row where action=='rename', it will attempt to rename proposed_path back to original_path
  and (optionally) restore metadata title/author/keywords from the original columns.
- Dry-run by default; pass --apply to perform operations.

This script makes minimal assumptions and will skip missing files, printing warnings.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

try:
    import fitz
except Exception:
    print("Missing dependency: pymupdf (fitz). Install with: pip install pymupdf", file=sys.stderr)
    raise


def read_plan(csvpath: Path):
    rows = []
    with csvpath.open('r', encoding='utf-8') as fh:
        r = csv.DictReader(fh)
        for row in r:
            rows.append(row)
    return rows


def restore_metadata(path: Path, title: str, author: str, keywords: str):
    try:
        doc = fitz.open(path)
        meta = doc.metadata
        meta['title'] = title or ''
        meta['author'] = author or ''
        meta['keywords'] = keywords or ''
        doc.set_metadata(meta)
        doc.save(path, garbage=4, deflate=True)
        doc.close()
        return True, None
    except Exception as e:
        return False, str(e)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('plan_csv', help='CSV plan produced by update_pdf_metadata_and_rename.py')
    p.add_argument('--apply', action='store_true', help='Perform revert operations')
    args = p.parse_args(argv)

    csvpath = Path(args.plan_csv)
    if not csvpath.exists():
        print(f"Plan {csvpath} not found", file=sys.stderr)
        return 2

    rows = read_plan(csvpath)
    print(f"Plan rows: {len(rows)}")
    failures = []
    for r in rows:
        action = r.get('action','')
        if action != 'rename':
            continue
        orig = Path(r['original_path'])
        prop = Path(r['proposed_path'])
        if args.apply:
            # If original already exists, create a unique backup of original
            if not prop.exists():
                print(f"Skip: proposed file missing {prop}")
                failures.append((prop, 'missing'))
                continue
            try:
                # attempt to move proposed back to original (overwrite if needed)
                if orig.exists():
                    # move original out of the way
                    bak = orig.with_suffix(orig.suffix + '.bak')
                    orig.rename(bak)
                prop.rename(orig)
            except Exception as e:
                print(f"Failed to rename {prop} -> {orig}: {e}")
                failures.append((prop, str(e)))
                continue
            # restore metadata if provided in the CSV original fields (original_title/original_author/original_keywords)
            ok, err = restore_metadata(orig, r.get('original_title','') or '', r.get('original_author','') or '', r.get('original_keywords','') or '')
            if not ok:
                print(f"Warning: failed to restore metadata for {orig}: {err}")
                failures.append((orig, err))
        else:
            # dry-run: just report what would be done
            print(f"Would rename: {prop} -> {orig}")
            if not prop.exists():
                print(f"  Note: proposed file does not exist (ok if not applied yet): {prop}")
    print(f"Done. failures: {len(failures)}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
