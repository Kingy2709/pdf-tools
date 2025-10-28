#!/usr/bin/env python3
"""
pdf_utils.py - Shared utilities for PDF processing

Common functions used across multiple scripts for:
- Text extraction (with fallbacks)
- Metadata reading/writing (atomic operations)
- PDF merging and splitting
- Word document conversion
- File safety utilities
"""

import tempfile
import os
from pathlib import Path
from typing import Optional, List, Dict, Tuple

try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    fitz = None

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    pdfplumber = None

try:
    from PyPDF2 import PdfReader, PdfWriter
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    PdfReader = None
    PdfWriter = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    canvas = None

try:
    from docx import Document
    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False
    Document = None


# ============================================================================
# TEXT EXTRACTION
# ============================================================================

def extract_text_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> str:
    """
    Extract text from PDF using best available library.
    Tries pdfplumber first, falls back to PyPDF2.
    
    Args:
        pdf_path: Path to PDF file
        max_pages: Optional limit on pages to extract (None = all pages)
    
    Returns:
        Extracted text as string (empty string on failure)
    """
    text = ""
    
    # Try pdfplumber (best quality)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages = pdf.pages[:max_pages] if max_pages else pdf.pages
                for page in pages:
                    text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"⚠️  pdfplumber failed: {e}, trying PyPDF2...")
    
    # Fallback to PyPDF2
    if PYPDF2_AVAILABLE:
        try:
            with open(pdf_path, 'rb') as file:
                pdf = PdfReader(file)
                pages = pdf.pages[:max_pages] if max_pages else pdf.pages
                for page in pages:
                    text += page.extract_text() or ""
            return text
        except Exception as e:
            print(f"❌ Text extraction failed: {e}")
    
    return text


def extract_text_from_page(pdf_path: str, page_num: int) -> str:
    """
    Extract text from a specific page (0-indexed).
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0 = first page)
    
    Returns:
        Extracted text from that page
    """
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if page_num < len(pdf.pages):
                    return pdf.pages[page_num].extract_text() or ""
        except Exception:
            pass
    
    if PYPDF2_AVAILABLE:
        try:
            with open(pdf_path, 'rb') as file:
                pdf = PdfReader(file)
                if page_num < len(pdf.pages):
                    return pdf.pages[page_num].extract_text() or ""
        except Exception:
            pass
    
    return ""


# ============================================================================
# METADATA OPERATIONS
# ============================================================================

def get_pdf_metadata(path: Path) -> Dict[str, str]:
    """
    Read PDF metadata using PyMuPDF.
    
    Args:
        path: Path to PDF file
    
    Returns:
        Dictionary of metadata (lowercase keys)
    """
    if not FITZ_AVAILABLE:
        return {}
    
    try:
        doc = fitz.open(str(path))
        metadata = doc.metadata or {}
        doc.close()
        return {k.lower(): (v or "").strip() for k, v in metadata.items()}
    except Exception as e:
        return {"_error": str(e)}


def atomic_write_metadata(path: str, title: Optional[str] = None, 
                          author: Optional[str] = None) -> Tuple[bool, str]:
    """
    Atomically write PDF metadata using temp file strategy.
    Tries incremental save first, falls back to temp file + replace.
    
    Args:
        path: Path to PDF file
        title: Optional title to set
        author: Optional author to set
    
    Returns:
        (success: bool, method: str)
        method values: 'incr', 'atomic', or error message
    """
    if not FITZ_AVAILABLE:
        return False, 'pymupdf-missing'
    
    try:
        doc = fitz.open(path)
    except Exception as e:
        return False, str(e)
    
    # Update metadata
    md = doc.metadata
    if title:
        md['title'] = title
    if author:
        md['author'] = author
    doc.set_metadata(md)
    
    # Try incremental save (fastest, preserves structure)
    try:
        doc.saveIncr()
        doc.close()
        return True, 'incr'
    except Exception:
        pass
    
    # Fallback: save to temp file and replace
    try:
        tmpfd, tmppath = tempfile.mkstemp(suffix='.pdf', prefix='tmp-metadata-')
        os.close(tmpfd)
        doc.save(tmppath)
        doc.close()
        os.replace(tmppath, path)
        return True, 'atomic'
    except Exception as e:
        try:
            doc.close()
        except:
            pass
        if os.path.exists(tmppath):
            os.unlink(tmppath)
        return False, str(e)


# ============================================================================
# PDF MERGING & SPLITTING
# ============================================================================

def merge_pdfs(pdf_paths: List[str], output_path: str) -> bool:
    """
    Merge multiple PDFs into one.
    
    Args:
        pdf_paths: List of PDF paths to merge (in order)
        output_path: Path for merged output PDF
    
    Returns:
        True on success, False on failure
    """
    if not PYPDF2_AVAILABLE:
        print("❌ PyPDF2 not available for merging")
        return False
    
    try:
        writer = PdfWriter()
        
        for pdf_path in pdf_paths:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                writer.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
    except Exception as e:
        print(f"❌ PDF merge failed: {e}")
        return False


def split_pdf(pdf_path: str, output_dir: str, prefix: str = "page") -> bool:
    """
    Split PDF into individual pages.
    
    Args:
        pdf_path: Path to PDF to split
        output_dir: Directory for output files
        prefix: Filename prefix (default: "page")
    
    Returns:
        True on success, False on failure
    """
    if not PYPDF2_AVAILABLE:
        print("❌ PyPDF2 not available for splitting")
        return False
    
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        reader = PdfReader(pdf_path)
        
        for i, page in enumerate(reader.pages, start=1):
            writer = PdfWriter()
            writer.add_page(page)
            
            output_file = output_path / f"{prefix}-{i:03d}.pdf"
            with open(output_file, 'wb') as f:
                writer.write(f)
        
        return True
    except Exception as e:
        print(f"❌ PDF split failed: {e}")
        return False


def extract_pages(pdf_path: str, page_numbers: List[int], output_path: str) -> bool:
    """
    Extract specific pages from PDF (0-indexed).
    
    Args:
        pdf_path: Source PDF
        page_numbers: List of page indices to extract (0-based)
        output_path: Output PDF path
    
    Returns:
        True on success, False on failure
    """
    if not PYPDF2_AVAILABLE:
        print("❌ PyPDF2 not available")
        return False
    
    try:
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        for page_num in page_numbers:
            if 0 <= page_num < len(reader.pages):
                writer.add_page(reader.pages[page_num])
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return True
    except Exception as e:
        print(f"❌ Page extraction failed: {e}")
        return False


# ============================================================================
# WORD DOCUMENT CONVERSION
# ============================================================================

def word_to_pdf(docx_path: str, pdf_path: str) -> bool:
    """
    Convert Word document to PDF.
    
    NOTE: Requires LibreOffice/unoconv or Microsoft Word installed.
    This function uses subprocess to call system converters.
    
    Args:
        docx_path: Path to .docx file
        pdf_path: Output PDF path
    
    Returns:
        True on success, False on failure
    """
    import subprocess
    import shutil
    
    # Try LibreOffice (cross-platform)
    if shutil.which('soffice') or shutil.which('libreoffice'):
        cmd = shutil.which('soffice') or shutil.which('libreoffice')
        try:
            subprocess.run([
                cmd,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(Path(pdf_path).parent),
                docx_path
            ], check=True, capture_output=True)
            
            # LibreOffice creates file with same name + .pdf
            generated = Path(docx_path).with_suffix('.pdf')
            if generated.exists() and str(generated) != pdf_path:
                generated.rename(pdf_path)
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ LibreOffice conversion failed: {e}")
    
    # Try unoconv (if available)
    if shutil.which('unoconv'):
        try:
            subprocess.run([
                'unoconv',
                '-f', 'pdf',
                '-o', pdf_path,
                docx_path
            ], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ unoconv conversion failed: {e}")
    
    print("❌ No Word-to-PDF converter found (install LibreOffice or unoconv)")
    return False


def extract_text_from_word(docx_path: str) -> str:
    """
    Extract text content from Word document.
    
    Args:
        docx_path: Path to .docx file
    
    Returns:
        Extracted text (empty string on failure)
    """
    if not PYTHON_DOCX_AVAILABLE:
        print("❌ python-docx not available (pip install python-docx)")
        return ""
    
    try:
        doc = Document(docx_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        print(f"❌ Word text extraction failed: {e}")
        return ""


# ============================================================================
# FILE SAFETY UTILITIES
# ============================================================================

def unique_path(target: Path) -> Path:
    """
    Generate unique path by adding counter if file exists.
    
    Args:
        target: Desired path
    
    Returns:
        Unique path (may be same as input if no collision)
    """
    if not target.exists():
        return target
    
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 1
    
    while True:
        new_path = parent / f"{stem}-{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


def safe_filename(text: str, max_length: int = 200) -> str:
    """
    Convert text to safe filename (removes special characters).
    
    Args:
        text: Input text
        max_length: Maximum filename length
    
    Returns:
        Sanitized filename
    """
    # Remove or replace unsafe characters
    safe = text.replace('/', '-').replace('\\', '-')
    safe = ''.join(c for c in safe if c.isalnum() or c in ' -_.')
    safe = safe.strip()
    
    # Collapse multiple spaces/dashes
    while '  ' in safe:
        safe = safe.replace('  ', ' ')
    while '--' in safe:
        safe = safe.replace('--', '-')
    
    # Truncate if needed
    if len(safe) > max_length:
        safe = safe[:max_length].rsplit(' ', 1)[0]  # Break at word boundary
    
    return safe or 'untitled'


def create_backup(path: Path, backup_dir: Optional[Path] = None) -> Path:
    """
    Create timestamped backup of file.
    
    Args:
        path: File to backup
        backup_dir: Optional backup directory (defaults to same dir)
    
    Returns:
        Path to backup file
    """
    from datetime import datetime
    
    if backup_dir is None:
        backup_dir = path.parent
    
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_name = f"{path.stem}-backup-{timestamp}{path.suffix}"
    backup_path = backup_dir / backup_name
    
    import shutil
    shutil.copy2(path, backup_path)
    
    return backup_path


# ============================================================================
# DEPENDENCY CHECK
# ============================================================================

def check_dependencies() -> Dict[str, bool]:
    """
    Check which PDF libraries are available.
    
    Returns:
        Dictionary of library availability
    """
    return {
        'pymupdf': FITZ_AVAILABLE,
        'pdfplumber': PDFPLUMBER_AVAILABLE,
        'pypdf2': PYPDF2_AVAILABLE,
        'reportlab': REPORTLAB_AVAILABLE,
        'python-docx': PYTHON_DOCX_AVAILABLE,
    }


def print_dependencies():
    """Print status of all dependencies."""
    deps = check_dependencies()
    print("\n📦 PDF Utils Dependencies:")
    for name, available in deps.items():
        status = "✅" if available else "❌"
        print(f"  {status} {name}")
    print()


if __name__ == '__main__':
    # When run directly, show available dependencies
    print_dependencies()
    
    # Show example usage
    print("🔧 Example Usage:")
    print("\n  from pdf_utils import extract_text_from_pdf, atomic_write_metadata")
    print("  text = extract_text_from_pdf('document.pdf')")
    print("  atomic_write_metadata('document.pdf', title='My Title', author='John Doe')")
    print()
