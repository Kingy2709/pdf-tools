#!/usr/bin/env python3
"""
Flatten a PDF collection and deduplicate by file content (SHA256).

Usage:
  python3 flatten_and_dedup_pdfs.py --root ~/Documents/clinic/research-articles

Options:
  --root       root folder to scan (required)
  --flat-dir   folder to move unique PDFs into (defaults to <root>/flat-YYYYMMDD-HHMMSS)
  --apply      actually perform deletions/moves (default: dry-run)
  --delete-duplicates  delete duplicate files when applying (default: keep duplicates in backup)
    --keep-policy  how to pick keeper among duplicates: clean-suffix|largest|newest|newest-largest (default: newest-largest)
  --log         CSV path to write results (defaults to <flat-dir>/flatten-dedup-log-TS.csv)

This script is conservative by default (dry-run). It outputs a CSV with planned actions. When --apply is used it will perform moves and deletions.

"""

import argparse
import csv
import datetime as dt
import hashlib
import os
from pathlib import Path
import shutil
import sys

CHUNK = 1024 * 1024


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    i = 2
    while True:
        cand = target.with_name(f"{stem}-{i}{suffix}")
        if not cand.exists():
            return cand
        i += 1


def pick_keeper(paths, policy: str):
    # paths: list of Path
    # policy: 'clean-suffix' prefers exact .pdf suffix, then larger size, then newest mtime
    if len(paths) == 1:
        return paths[0]
    def score(p: Path):
        s = 0
        # clean suffix
        if p.suffix.lower() == '.pdf':
            s += 100000
        # prefer name that doesn't end with underscores or extra chars after .pdf
        name = p.name
        if name.lower().endswith('.pdf_') or name.lower().endswith('.pdf~') or name.lower().endswith('.pdfx'):
            s -= 1000
        try:
            s += p.stat().st_size // 1024
            s += int(p.stat().st_mtime) % 1000
        except Exception:
            pass
        return s

    if policy == 'largest':
        return max(paths, key=lambda p: (p.stat().st_size if p.exists() else 0))
    if policy == 'newest':
        return max(paths, key=lambda p: (p.stat().st_mtime if p.exists() else 0))
    if policy == 'newest-largest':
        # prefer newest modified time, then largest size
        return max(paths, key=lambda p: ((p.stat().st_mtime if p.exists() else 0), (p.stat().st_size if p.exists() else 0)))
    # default clean-suffix
    return max(paths, key=score)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', required=True)
    p.add_argument('--flat-dir')
    p.add_argument('--apply', action='store_true')
    p.add_argument('--delete-duplicates', action='store_true')
    p.add_argument('--keep-policy', choices=['clean-suffix','largest','newest','newest-largest'], default='newest-largest')
    p.add_argument('--log')
    args = p.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"root not found: {root}", file=sys.stderr)
        sys.exit(1)

    ts = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
    flat_dir = Path(args.flat_dir) if args.flat_dir else root / f"flat-{ts}"
    log_path = Path(args.log) if args.log else flat_dir / f"flatten-dedup-log-{ts}.csv"

    print(f"Scanning PDFs under: {root}")
    # gather pdfs
    pdfs = []
    for pth in root.rglob('*'):
        if not pth.is_file():
            continue
        # consider files that look like pdfs by extension or containing .pdf in name
        if pth.suffix and pth.suffix.lower() == '.pdf':
            pdfs.append(pth)
            continue
        # some files may have strange suffixes like .pdf_ or .pdfx -> include them
        name_lower = pth.name.lower()
        if '.pdf' in name_lower:
            pdfs.append(pth)

    print(f"Found {len(pdfs)} candidate files")

    # compute hashes
    hash_map = {}
    for i, fpath in enumerate(pdfs, start=1):
        try:
            h = sha256_of_file(fpath)
        except Exception as e:
            print(f"ERROR hashing {fpath}: {e}", file=sys.stderr)
            h = None
        hash_map.setdefault(h, []).append(fpath)
        if i % 50 == 0:
            print(f"Hashed {i}/{len(pdfs)} files...", file=sys.stderr)

    # identify duplicates
    duplicates = {h: paths for h, paths in hash_map.items() if h is not None and len(paths) > 1}
    uniques = {h: paths for h, paths in hash_map.items() if h is not None and len(paths) == 1}

    print(f"Unique content hashes: {len(uniques)}; Duplicates groups: {len(duplicates)}")

    planned = []
    # for each hash group, pick keeper and mark others as duplicates
    for h, paths in duplicates.items():
        keeper = pick_keeper(paths, args.keep_policy)
        for pth in paths:
            planned.append({
                'hash': h,
                'old_path': str(pth),
                'is_keeper': str(pth==keeper),
                'target_name': '',
                'action': 'keep' if pth==keeper else 'delete' if args.delete_duplicates else 'keep (duplicate)'
            })
    # also include uniques - will be moved
    for h, paths in uniques.items():
        pth = paths[0]
        planned.append({
            'hash': h,
            'old_path': str(pth),
            'is_keeper': 'True',
            'target_name': '',
            'action': 'keep'
        })

    # ensure flat dir parent exists for planning CSV (create flat dir later if applying)
    flat_dir_parent = flat_dir.parent
    flat_dir_parent.mkdir(parents=True, exist_ok=True)
    # create the flat dir now to avoid race with timestamp differences when writing the log
    flat_dir.mkdir(parents=True, exist_ok=True)

    # assign new target names (for keepers)
    seen_targets = set()
    for row in planned:
        if row['is_keeper'] != 'True' and row['action'].startswith('delete'):
            continue
        old = Path(row['old_path'])
        # choose a safe target name: use original name cleaned to .pdf if needed
        name = old.name
        lname = name.lower()
        if '.pdf' in lname:
            # trim everything after the last '.pdf' (handles .pdf_, .pdf~ .pdf.pdf etc.)
            idx = lname.rfind('.pdf')
            name = name[:idx+4]
        # strip trailing punctuation/underscores that may precede extension
        name = name.rstrip(' _~.-')
        # ensure suffix
        if not name.lower().endswith('.pdf'):
            name = name + '.pdf'
        target = flat_dir / name
        # avoid collisions
        if str(target) in seen_targets or target.exists():
            target = unique_path(target)
        seen_targets.add(str(target))
        row['target_name'] = str(target)

    # write CSV plan/log
    with open(log_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['hash','old_path','is_keeper','action','target_name']
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in planned:
            w.writerow({k: r.get(k,'') for k in fieldnames})

    print(f"Plan written to: {log_path}")

    # show summary
    to_delete = [r for r in planned if r['action'].startswith('delete')]
    to_move = [r for r in planned if r['action'].startswith('keep')]
    print(f"Plan summary: keep/move candidates={len(to_move)} duplicates-to-delete={len(to_delete)}")

    if not args.apply:
        print("Dry-run only. Rerun with --apply to execute moves/deletions.")
        return

    # apply moves
    moved = 0
    deleted = 0
    for r in planned:
        old = Path(r['old_path'])
        tgt = Path(r['target_name'])
        if r['is_keeper'] != 'True' and r['action'].startswith('delete'):
            try:
                old.unlink()
                deleted += 1
            except Exception as e:
                print(f"ERROR deleting {old}: {e}", file=sys.stderr)
            continue
        # ensure target dir
        tgt.parent.mkdir(parents=True, exist_ok=True)
        try:
            if old.resolve() == tgt.resolve():
                # already at target
                continue
            shutil.move(str(old), str(tgt))
            moved += 1
        except Exception as e:
            print(f"ERROR moving {old} -> {tgt}: {e}", file=sys.stderr)

    print(f"Applied: moved={moved} deleted={deleted}")
    print("Done.")


if __name__ == '__main__':
    main()
