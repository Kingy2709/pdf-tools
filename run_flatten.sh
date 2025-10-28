#!/usr/bin/env bash
# Wrapper to run flatten_and_dedup_pdfs.py in the preferred venv
# Edit ROOT to change the target folder
ROOT="~/Documents/clinic/research-articles"
PYTHON="/Users/kingm/Documents/dev/virtual-environments/venv/.venv/bin/python"
SCRIPT="/Users/kingm/Documents/dev/flatten_and_dedup_pdfs.py"

# Dry-run (default)
$PYTHON $SCRIPT --root "$ROOT"

# To apply moves (non-deleting), uncomment:
# $PYTHON $SCRIPT --root "$ROOT" --apply

# To apply and delete duplicates (destructive), uncomment:
# $PYTHON $SCRIPT --root "$ROOT" --apply --delete-duplicates --keep-policy newest-largest
