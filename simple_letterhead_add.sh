#!/usr/bin/env bash
# Simple approach: Use pdftk to stamp letterhead onto existing PDF

SOURCE_PDF="$HOME/Downloads/Imaging Results Letter Cassandra Bickhoff 10-22 12-50AM.pdf"
LETTERHEAD="$HOME/Documents/clinic/templates-clinic/template-letterhead/template-letterhead-2.pdf"
OUTPUT="$HOME/Documents/clinic/letters-referrals/test-simple-merge.pdf"

if command -v pdftk &> /dev/null; then
    echo "Using pdftk to add letterhead..."
    pdftk "$SOURCE_PDF" background "$LETTERHEAD" output "$OUTPUT"
    echo "✅ Done: $OUTPUT"
    open "$OUTPUT"
else
    echo "❌ pdftk not installed"
    echo "Install with: brew install pdftk-java"
fi
