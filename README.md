# PDF Processing Tools

Collection of Python scripts for automated PDF processing, merging, renaming, and metadata management.

## Scripts

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
pip install PyPDF2 pdfplumber reportlab

# Run a script
./run_merge_letterhead.sh
```

## Configuration

Most scripts have configuration sections at the top. Adjust paths and settings as needed.
