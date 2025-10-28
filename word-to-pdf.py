#!/usr/bin/env python3
"""
word-to-pdf.py
Convert Word documents (.docx) to PDF format

Usage:
  python word-to-pdf.py input.docx                 # Creates input.pdf
  python word-to-pdf.py input.docx -o output.pdf   # Custom output name
  python word-to-pdf.py folder/*.docx              # Batch convert
"""

import argparse
import sys
from pathlib import Path
from pdf_utils import word_to_pdf


def main():
    parser = argparse.ArgumentParser(
        description='Convert Word documents to PDF',
        epilog='Requires LibreOffice or unoconv installed'
    )
    parser.add_argument('input', nargs='+', help='Word document(s) to convert')
    parser.add_argument('-o', '--output', help='Output PDF path (single file only)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing PDFs')
    
    args = parser.parse_args()
    
    # Single file mode
    if len(args.input) == 1 and args.output:
        docx_path = Path(args.input[0])
        if not docx_path.exists():
            print(f"❌ File not found: {docx_path}")
            return 1
        
        output_path = Path(args.output)
        if output_path.exists() and not args.overwrite:
            print(f"❌ Output exists: {output_path} (use --overwrite)")
            return 1
        
        print(f"📄 Converting: {docx_path.name}")
        if word_to_pdf(str(docx_path), str(output_path)):
            print(f"✅ Created: {output_path}")
            return 0
        else:
            print(f"❌ Conversion failed")
            return 1
    
    # Batch mode
    success_count = 0
    fail_count = 0
    
    for input_path_str in args.input:
        docx_path = Path(input_path_str)
        
        if not docx_path.exists():
            print(f"⚠️  Skipping (not found): {docx_path}")
            fail_count += 1
            continue
        
        if docx_path.suffix.lower() not in ['.docx', '.doc']:
            print(f"⚠️  Skipping (not Word doc): {docx_path}")
            fail_count += 1
            continue
        
        output_path = docx_path.with_suffix('.pdf')
        
        if output_path.exists() and not args.overwrite:
            print(f"⚠️  Skipping (exists): {output_path}")
            fail_count += 1
            continue
        
        print(f"📄 Converting: {docx_path.name}")
        if word_to_pdf(str(docx_path), str(output_path)):
            print(f"  ✅ {output_path.name}")
            success_count += 1
        else:
            print(f"  ❌ Failed")
            fail_count += 1
    
    print(f"\n📊 Results: {success_count} converted, {fail_count} failed")
    return 0 if fail_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
