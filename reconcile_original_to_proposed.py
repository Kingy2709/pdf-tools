#!/usr/bin/env python3
"""
reconcile_original_to_proposed.py

Reads a renamer CSV and for rows where the `proposed_path` does not exist but
`original_path` does, rename original -> proposed. Dry-run by default.

Usage:
  python reconcile_original_to_proposed.py /path/to/metadata-rename-plan.csv [--apply]
"""
import argparse
import csv
from pathlib import Path


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
    with csvp.open('r', newline='') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)

    planned = []
    for r in rows:
        proposed = r.get('proposed_path') or r.get('new_path') or r.get('proposed')
        original = r.get('original_path') or r.get('original') or r.get('src_path')
        if not proposed or not original:
            continue
        ppath = Path(proposed)
        opath = Path(original)
        if ppath.exists():
            continue
        if opath.exists():
            planned.append((opath, ppath))

    print('Planned reconciliations:', len(planned))
    for oldp, newp in planned:
        print(('DRY-RUN' if not args.apply else 'APPLY'), oldp, '->', newp)
        if args.apply:
            if newp.exists():
                print('SKIP - target exists:', newp)
                continue
            # ensure parent dir exists
            newp.parent.mkdir(parents=True, exist_ok=True)
            oldp.rename(newp)

if __name__ == '__main__':
    main()
