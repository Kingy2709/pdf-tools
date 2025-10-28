# PDF Processing Tools

Collection of Python scripts for automated PDF processing, merging, renaming, and metadata management.

## 🚀 New: Shared Utilities Module

All scripts now use **`pdf_utils.py`** for common operations:
- Text extraction (with fallbacks)
- Metadata reading/writing (atomic operations)
- PDF merging, splitting, page extraction
- Word document conversion
- File safety utilities

This ensures consistent behavior and easier maintenance across all tools.

## Scripts

### Core Utilities
- **`pdf_utils.py`** ⭐ Shared utilities module (imported by other scripts)
  - Text extraction with fallback support
  - Atomic metadata operations
  - PDF merge/split functions
  - Word-to-PDF conversion helpers
  - Safe filename generation

### New Tools
- **`pdf-merge.py`** - Merge multiple PDFs into one file
- **`pdf-split.py`** - Split PDF into pages or extract specific pages
- **`word-to-pdf.py`** - Convert Word documents to PDF (requires LibreOffice)

### Letterhead & Merging
- **`merge_letterhead_and_rename.py`** - Auto-overlay clinic letterhead with downloaded PDFs and rename based on parsed content
  - **Features:**
    - Overlays letterhead on every page (not just first page)
    - Adds signature image, name, title, and date on last page
    - Parses patient name, body area, and referrer from PDF text
    - Auto-generates filename: `{LastName}{FirstInitial}-{BodyArea}-Letter to {Referrer}-{dd.mm.yy}.pdf`
    - Ensures content fits within letterhead margins
  - **Configuration:** Edit top of script to set:
    - `LETTERHEAD_PDF` - Path to your letterhead template
    - `SIGNATURE_PNG` - Path to your signature image
    - `SIGNATURE_TEXT` - Your name
    - `SIGNATURE_TITLE` - Your title/credentials
    - Content margins to fit within your letterhead design
  - **Run:** `./run_merge_letterhead.sh`

### Batch Operations
- **`batch_rename_workflow.py`** - Batch rename PDFs with custom workflows
- **`flatten_and_dedup_pdfs.py`** - Flatten PDF forms and remove duplicates
- **`run_all.py`** - Execute multiple PDF operations in sequence

### Metadata Management
- **`inspect_pdf_metadata.py`** - View PDF metadata
- **`update_pdf_metadata_and_rename.py`** - Update metadata and rename files
- **`revert_pdf_metadata_and_renames.py`** - Undo metadata changes

### Renaming Utilities
- **`rename_with_two_page_infer.py`** - Smart rename using first two pages
- **`rename-pdfs-kebab.py`** - Convert filenames to kebab-case
- **`fix_filenames_lastname.py`** - Fix lastname formatting issues

### CSV & Verification
- **`apply_plan_from_csv.py`** - Apply bulk operations from CSV
- **`verify_csv_vs_disk.py`** - Verify CSV matches disk files
- **`reconcile_original_to_proposed.py`** - Reconcile filename changes

## Setup

```bash
# Install dependencies
source venv/bin/activate
pip install -r requirements.txt

# For Word-to-PDF conversion, also install LibreOffice:
# macOS: brew install libreoffice
# Linux: sudo apt install libreoffice
# Windows: Download from libreoffice.org

# Test installation
python pdf_utils.py

# Run a script
./run_merge_letterhead.sh
```

## Quick Examples

```bash
# Merge PDFs
python pdf-merge.py file1.pdf file2.pdf file3.pdf -o combined.pdf

# Split PDF into individual pages
python pdf-split.py document.pdf -o output_dir/

# Extract specific pages (1-indexed)
python pdf-split.py document.pdf --pages 1,3,5 -o selected.pdf

# Convert Word to PDF
python word-to-pdf.py letter.docx -o letter.pdf

# Batch convert Word documents
python word-to-pdf.py *.docx
```

## Configuration

Most scripts have configuration sections at the top. Adjust paths and settings as needed.
