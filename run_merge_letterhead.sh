#!/usr/bin/env bash
# Quick runner for PDF letterhead merger

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Activate virtual environment if it exists
if [ -d "$VENV_DIR" ]; then
    source "$VENV_DIR/bin/activate"
fi

# Run the script
python3 "$SCRIPT_DIR/merge_letterhead_and_rename.py" "$@"
