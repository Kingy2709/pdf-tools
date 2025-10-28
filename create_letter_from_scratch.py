#!/usr/bin/env python3
"""
PDF Letter Formatter - COMPLETE REWRITE
Extracts text from PDF and recreates it properly formatted with letterhead and signature
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from io import BytesIO

import pdfplumber
from PyPDF2 import PdfReader, PdfWriter, PageObject
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, KeepTogether
from reportlab.pdfgen import canvas

# ======================
# CONFIGURATION
# ======================
DOWNLOADS_DIR = Path.home() / "Downloads"
LETTERHEAD_PDF = Path.home() / "Documents/clinic/templates-clinic/template-letterhead/template-letterhead-2.pdf"
SIGNATURE_PNG = Path.home() / "Documents/clinic/templates-clinic/template-signature/template-signature-transparent-v1.png"
OUTPUT_DIR = Path.home() / "Documents/clinic/letters-referrals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Page margins (to fit within letterhead)
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_LEFT = 2.5*cm
MARGIN_RIGHT = 2.5*cm
MARGIN_TOP = 6*cm  # Space for letterhead header
MARGIN_BOTTOM = 2*cm

# Signature
SIGNATURE_TEXT = "Matthew King APAM"
SIGNATURE_TITLE = "Physiotherapist"
SIGNATURE_QUALS = "B.Physio (Hons)"
SIGNATURE_INTERESTS = (
    "<b>Special interests:</b> Lower limb injuries (hip, groin, knee, ankle, and foot); "
    "sports injuries (with special interest in all martial arts and dance injuries); "
    "tendinopathy; adolescent growth-related conditions; neck pain and headaches; "
    "complex injuries requiring detailed assessment and clinical reasoning."
)

def get_latest_pdf(directory):
    """Get the most recently downloaded PDF file"""
    pdf_files = list(directory.glob("*.pdf"))
    if not pdf_files:
        print("❌ No PDF files found in Downloads")
        sys.exit(1)
    
    latest_pdf = max(pdf_files, key=lambda p: p.stat().st_mtime)
    print(f"📄 Latest PDF: {latest_pdf.name}")
    return latest_pdf

def extract_text_from_pdf(pdf_path):
    """Extract text content from PDF"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"❌ Text extraction failed: {e}")
        return ""
    return text

def parse_patient_info(text):
    """Parse patient name, body area, referrer from PDF text"""
    patient_name = None
    body_area = None
    referrer = None
    
    # Pattern for name
    name_patterns = [
        r'Re:\s+(?:Mrs?\.?|Ms\.?|Dr\.?)?\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)',
        r'(?:Patient|Name):\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match and len(match.groups()) == 2:
            first_name, last_name = match.groups()
            patient_name = f"{last_name}{first_name[0]}"
            break
    
    # Pattern for body area
    body_area_keywords = ['shoulder', 'knee', 'hip', 'ankle', 'back', 'neck', 
                          'elbow', 'wrist', 'spine', 'lumbar', 'cervical', 'foot', 'calf']
    for keyword in body_area_keywords:
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            body_area = keyword.capitalize()
            break
    
    # Pattern for referrer
    referrer_patterns = [
        r'Dear\s+(?:Dr\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+)',
        r'Dr\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
    ]
    
    for pattern in referrer_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            referrer = match.group(1).split()[0]  # First name only
            break
    
    return patient_name, body_area, referrer

def generate_filename(patient_name, body_area, referrer):
    """Generate filename"""
    date_str = datetime.now().strftime("%d.%m.%y")
    patient_name = patient_name or "UnknownPatient"
    body_area = body_area or "General"
    referrer = referrer or "Referrer"
    filename = f"{patient_name}-{body_area}-Letter to {referrer}-{date_str}.pdf"
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    return filename

def create_formatted_pdf(text, output_path):
    """Create properly formatted PDF with letterhead and signature"""
    from reportlab.pdfgen import canvas
    from PyPDF2 import PdfReader, PdfWriter
    
    # Step 1: Create content PDF without letterhead
    temp_path = output_path.parent / f"temp_{output_path.name}"
    
    # Create document with proper margins
    doc = SimpleDocTemplate(
        str(temp_path),
        pagesize=A4,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )
    
    # Styles
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        alignment=TA_LEFT,
    )
    
    signature_style = ParagraphStyle(
        'Signature',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
    )
    
    # Build story
    story = []
    
    # Split text into paragraphs
    paragraphs = text.strip().split('\n\n')
    
    for para in paragraphs:
        if para.strip():
            # Clean up the paragraph
            para_clean = ' '.join(para.split())
            story.append(Paragraph(para_clean, body_style))
            story.append(Spacer(1, 0.3*cm))
    
    # Add spacing before signature
    story.append(Spacer(1, 0.5*cm))
    
    # Add signature image if exists
    if SIGNATURE_PNG.exists():
        try:
            sig_img = RLImage(str(SIGNATURE_PNG), width=4*cm, height=1.5*cm)
            story.append(sig_img)
            story.append(Spacer(1, 0.2*cm))
        except Exception as e:
            print(f"⚠️  Signature image error: {e}")
    
    # Add signature text
    story.append(Paragraph(f"<b>{SIGNATURE_TEXT}</b>", signature_style))
    story.append(Paragraph(SIGNATURE_TITLE, signature_style))
    story.append(Paragraph(SIGNATURE_QUALS, signature_style))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(SIGNATURE_INTERESTS, signature_style))
    
    # Build content PDF
    doc.build(story)
    print(f"✅ Created content PDF")
    
    # Step 2: Overlay letterhead on each page
    if LETTERHEAD_PDF.exists():
        print(f"🎨 Adding letterhead to all pages...")
        
        # Read letterhead and content
        letterhead_pdf = PdfReader(str(LETTERHEAD_PDF))
        content_pdf = PdfReader(str(temp_path))
        output_pdf = PdfWriter()
        
        letterhead_page = letterhead_pdf.pages[0]
        
        # Overlay letterhead on each content page
        for page in content_pdf.pages:
            # Create new blank page
            from PyPDF2 import PageObject
            new_page = PageObject.create_blank_page(
                width=page.mediabox.width,
                height=page.mediabox.height
            )
            
            # Add letterhead as background
            new_page.merge_page(letterhead_page)
            
            # Add content on top
            new_page.merge_page(page)
            
            output_pdf.add_page(new_page)
        
        # Write final PDF
        with open(output_path, 'wb') as f:
            output_pdf.write(f)
        
        # Clean up temp file
        temp_path.unlink()
        print(f"✅ Added letterhead successfully")
    else:
        # No letterhead available, just rename temp file
        temp_path.rename(output_path)
        print(f"⚠️  No letterhead found, using plain PDF")

def main():
    print("🚀 PDF Letter Formatter (NEW APPROACH)")
    print("=" * 50)
    
    # Get latest PDF
    source_pdf = get_latest_pdf(DOWNLOADS_DIR)
    
    # Extract text
    print("📖 Extracting text...")
    text = extract_text_from_pdf(source_pdf)
    
    if text:
        print(f"   Extracted {len(text)} characters")
    else:
        print("❌ No text extracted")
        sys.exit(1)
    
    # Parse info
    print("🔍 Parsing information...")
    patient_name, body_area, referrer = parse_patient_info(text)
    
    print(f"   Patient: {patient_name or '❓'}")
    print(f"   Body Area: {body_area or '❓'}")
    print(f"   Referrer: {referrer or '❓'}")
    
    # Generate filename
    output_filename = generate_filename(patient_name, body_area, referrer)
    output_path = OUTPUT_DIR / output_filename
    
    print(f"\n📝 Output: {output_filename}")
    
    # Create formatted PDF
    print("🎨 Creating formatted PDF...")
    create_formatted_pdf(text, output_path)
    
    print(f"\n✅ Complete! Saved to:")
    print(f"   {output_path}")
    print(f"   Size: {output_path.stat().st_size / 1024:.1f} KB")
    
    # Open file
    response = input("\nOpen file? (y/n): ")
    if response.lower() == 'y':
        os.system(f'open "{output_path}"')

if __name__ == "__main__":
    main()
