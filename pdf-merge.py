#!/usr/bin/env python3
"""
pdf-merge.py
Merge multiple PDFs into a single file

Usage:
  python pdf-merge.py file1.pdf file2.pdf file3.pdf -o merged.pdf
  python pdf-merge.py folder/*.pdf -o combined.pdf
  python pdf-merge.py --order pages.txt -o output.pdf
"""

import argparse
import sys
from pathlib import Path
from pdf_utils import merge_pdfs


def main():
    parser = argparse.ArgumentParser(
        description='Merge multiple PDF files into one',
        epilog='Files are merged in the order specified'
    )
    parser.add_argument('input', nargs='*', help='PDF files to merge')
    parser.add_argument('-o', '--output', required=True, help='Output PDF path')
    parser.add_argument('--order', help='Text file with list of PDFs (one per line)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output')
    
    args = parser.parse_args()
    
    # Collect input files
    pdf_paths = []
    
    if args.order:
        # Read from file
        order_file = Path(args.order)
        if not order_file.exists():
            print(f"❌ Order file not found: {order_file}")
            return 1
        
        with open(order_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    pdf_paths.append(line)
    else:
        # Use command line arguments
        pdf_paths = args.input
    
    if not pdf_paths:
        print("❌ No input files specified")
        parser.print_help()
        return 1
    
    # Validate input files
    valid_paths = []
    for path_str in pdf_paths:
        path = Path(path_str)
        if not path.exists():
            print(f"⚠️  File not found: {path}")
            continue
        if path.suffix.lower() != '.pdf':
            print(f"⚠️  Not a PDF: {path}")
            continue
        valid_paths.append(str(path))
    
    if not valid_paths:
        print("❌ No valid PDF files to merge")
        return 1
    
    # Check output
    output_path = Path(args.output)
    if output_path.exists() and not args.overwrite:
        print(f"❌ Output exists: {output_path} (use --overwrite)")
        return 1
    
    # Merge
    print(f"📄 Merging {len(valid_paths)} PDFs...")
    for i, path in enumerate(valid_paths, 1):
        print(f"  {i}. {Path(path).name}")
    
    if merge_pdfs(valid_paths, str(output_path)):
        print(f"\n✅ Created: {output_path}")
        return 0
    else:
        print(f"\n❌ Merge failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
