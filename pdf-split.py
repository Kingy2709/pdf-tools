#!/usr/bin/env python3
"""
pdf-split.py
Split PDF into individual pages or extract specific pages

Usage:
  python pdf-split.py document.pdf                    # Split all pages
  python pdf-split.py document.pdf --pages 1,3,5      # Extract specific pages (1-indexed)
  python pdf-split.py document.pdf --range 1-10       # Extract page range
  python pdf-split.py document.pdf -o output_dir/     # Custom output directory
"""

import argparse
import sys
from pathlib import Path
from pdf_utils import split_pdf, extract_pages


def parse_page_spec(spec: str) -> list:
    """Parse page specification like '1,3,5' or '1-10' into list of page numbers (0-indexed)"""
    pages = []
    
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            # Range like "1-10"
            start, end = part.split('-')
            pages.extend(range(int(start) - 1, int(end)))  # Convert to 0-indexed
        else:
            # Single page
            pages.append(int(part) - 1)  # Convert to 0-indexed
    
    return sorted(set(pages))  # Remove duplicates and sort


def main():
    parser = argparse.ArgumentParser(
        description='Split PDF or extract specific pages',
        epilog='Page numbers are 1-indexed (first page = 1)'
    )
    parser.add_argument('input', help='PDF file to split')
    parser.add_argument('-o', '--output', help='Output directory (default: same as input)')
    parser.add_argument('--pages', help='Specific pages to extract (e.g., "1,3,5")')
    parser.add_argument('--range', help='Page range to extract (e.g., "1-10")')
    parser.add_argument('--prefix', default='page', help='Output filename prefix (default: "page")')
    
    args = parser.parse_args()
    
    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ File not found: {input_path}")
        return 1
    
    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = input_path.parent / f"{input_path.stem}-pages"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract specific pages
    if args.pages or args.range:
        page_spec = args.pages or args.range
        try:
            page_numbers = parse_page_spec(page_spec)
        except ValueError as e:
            print(f"❌ Invalid page specification: {e}")
            return 1
        
        if not page_numbers:
            print("❌ No pages specified")
            return 1
        
        output_path = output_dir / f"{input_path.stem}-extracted.pdf"
        
        print(f"📄 Extracting {len(page_numbers)} pages from {input_path.name}")
        print(f"   Pages: {', '.join(str(p+1) for p in page_numbers)}")
        
        if extract_pages(str(input_path), page_numbers, str(output_path)):
            print(f"✅ Created: {output_path}")
            return 0
        else:
            print(f"❌ Extraction failed")
            return 1
    
    # Split all pages
    print(f"📄 Splitting {input_path.name} into individual pages...")
    
    if split_pdf(str(input_path), str(output_dir), args.prefix):
        page_files = sorted(output_dir.glob(f"{args.prefix}-*.pdf"))
        print(f"✅ Created {len(page_files)} files in {output_dir}")
        return 0
    else:
        print(f"❌ Split failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
