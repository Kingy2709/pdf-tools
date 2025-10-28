#!/usr/bin/env python3
"""
apply_plan_from_csv.py

Applies a metadata-rename plan CSV exactly as recorded.
Dry-run by default; use --apply to execute. Writes metadata using the same
atomic write fallback used by the renamer.

Usage:
  python apply_plan_from_csv.py plan.csv [--apply]

Columns expected: at least 'original_path' and 'proposed_path'; 'meta_author' and 'meta_title' are optional.
"""
import argparse
import csv
import os
import shutil
import tempfile
from pathlib import Path

try:
    import fitz
except Exception:
    fitz = None


def atomic_write_metadata(path, title, author):
    if fitz is None:
        return False, 'pymupdf-missing'
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
    try:
        doc.saveIncr()
        doc.close()
        return True, 'incr'
    except Exception:
        pass
    try:
        tmpfd, tmppath = tempfile.mkstemp(suffix='.pdf', prefix='tmp-apply-')
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument('csv', type=str)
    p.add_argument('--apply', action='store_true')
    args = p.parse_args()

    csvp = Path(args.csv)
    if not csvp.exists():
        print('CSV not found:', csvp)
        return

    rows = []
    with csvp.open('r', newline='', encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)

    planned = []
    for r in rows:
        src = r.get('original_path')
        dst = r.get('proposed_path')
        if not src or not dst:
            continue
        srcp = Path(src)
        dstp = Path(dst)
        if not srcp.exists():
            # If original no longer exists but dst exists, consider it done
            if dstp.exists():
                continue
            planned.append((src, dst, 'missing-src'))
            continue
        if srcp.exists() and dstp.exists() and srcp.samefile(dstp):
            continue
        if srcp.exists() and dstp.exists() and not srcp.samefile(dstp):
            planned.append((src, dst, 'dst-exists'))
            continue
        # otherwise plan to rename
        planned.append((src, dst, 'rename'))

    print(f"Planned operations: {len(planned)}")
    samples = planned[:20]
    if samples:
        print('Sample planned ops:')
        for s in samples:
            print(s)

    if not args.apply:
        print('Dry-run: no changes made. Re-run with --apply to perform operations.')
        return

    # perform operations
    for src, dst, kind in planned:
        srcp = Path(src)
        dstp = Path(dst)
        if dstp.exists() and not srcp.samefile(dstp):
            print(f"SKIP - target exists: {dst}")
            continue
        # ensure parent directory exists
        dstp.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.rename(src, dst)
            print(f"APPLY {src} -> {dst}")
        except Exception as e:
            print(f"FAIL rename {src} -> {dst}: {e}")
            continue
        # write metadata if present
        ok, msg = atomic_write_metadata(dstp, r.get('meta_title'), r.get('meta_author'))
        if ok:
            print(f"OK {dst}")
        else:
            print(f"WARN metadata {dst}: {msg}")

if __name__ == '__main__':
    main()
