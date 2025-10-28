#!/usr/bin/env python3
"""
Simple orchestrator for the PDF renaming toolkit.

Usage:
  run_all.py propose    # run the main workflow in dry-run/propose mode
  run_all.py dryrun     # same as propose (keeps consistent naming)
  run_all.py apply      # run the main workflow with --apply (will mutate files)
  run_all.py inspect <pdf>...  # run the inspection helper on one or more PDFs
  run_all.py list-scripts

This wrapper calls the `batch_rename_workflow.py` and `inspect_pdf_metadata.py`
scripts that live alongside it. It uses the same Python interpreter used to run
this script to invoke them (so virtualenvs are respected).

This file intentionally keeps CLI plumbing minimal and delegates the work to
the existing scripts (safe, auditable, and already tested during earlier runs).
"""
import argparse
import subprocess
import sys
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BATCH = ROOT / 'batch_rename_workflow.py'
INSPECT = ROOT / 'inspect_pdf_metadata.py'


def check_script(p: Path):
    if not p.exists():
        raise SystemExit(f'Required script not found: {p}')


def run_batch(args, extra_args=None):
    check_script(BATCH)
    cmd = [sys.executable, str(BATCH)]
    cmd += ['--src', args.src, '--out', args.out, '--backup', args.backup, '--logs', args.logs]
    if extra_args:
        cmd += extra_args
    print('Running:', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def cmd_propose(args):
    # run without --apply to produce proposals / dry-run outputs
    run_batch(args)


def cmd_dryrun(args):
    cmd_propose(args)


def cmd_apply(args):
    extra = ['--apply']
    if args.skip_backup:
        extra.append('--skip-backup')
    run_batch(args, extra_args=extra)


def cmd_inspect(argv):
    check_script(INSPECT)
    cmd = [sys.executable, str(INSPECT)] + argv
    print('Running:', ' '.join(cmd))
    subprocess.run(cmd, check=True)


def cmd_list_scripts():
    for p in sorted(ROOT.iterdir()):
        print(p.name)


def main():
    parser = argparse.ArgumentParser(description='Orchestrate PDF renamer tasks')
    parser.add_argument('--src', default='/Users/kingm/research-articles-output')
    parser.add_argument('--out', default='/Users/kingm/research-articles-output')
    parser.add_argument('--backup', default='/Users/kingm/research-articles-backup')
    parser.add_argument('--logs', default='/Users/kingm/Documents/dev/tmp-logs')
    parser.add_argument('--skip-backup', action='store_true', help='Pass --skip-backup to apply')

    sub = parser.add_subparsers(dest='command')
    sub.add_parser('propose')
    sub.add_parser('dryrun')
    sub.add_parser('apply')
    sub.add_parser('list-scripts')
    insp = sub.add_parser('inspect')
    insp.add_argument('pdfs', nargs='+')

    args, rest = parser.parse_known_args()

    if args.command in ('propose', 'dryrun'):
        cmd_propose(args)
    elif args.command == 'apply':
        cmd_apply(args)
    elif args.command == 'inspect':
        cmd_inspect(args.pdfs)
    elif args.command == 'list-scripts':
        cmd_list_scripts()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
