#!/usr/bin/env bash
# Wrapper to run rename-pdfs-kebab.py in the preferred venv
# Edit ROOT to change the target folder
ROOT="~/Documents/clinic/research-articles"
PYTHON="/Users/kingm/Documents/dev/virtual-environments/venv/.venv/bin/python"
SCRIPT="/Users/kingm/Documents/dev/rename-pdfs-kebab.py"

# Dry-run (default)
$PYTHON $SCRIPT --root "$ROOT"

# To apply changes, uncomment the following line:
# $PYTHON $SCRIPT --root "$ROOT" --apply --force-overwrite-metadata
