#!/usr/bin/env python3
"""
PDF Letterhead Merger & Auto-Renamer
Takes the latest PDF from Downloads, overlays clinic letterhead and signature,
parses content, and saves with naming format: {LastName}{FirstInitial}-{BodyArea}-Letter to {Referrer}-{dd.mm.yy}.pdf

This script:
1. Finds the latest PDF in Downloads
2. Extracts text and parses patient/referrer info
3. Overlays letterhead template on every page
4. Adds signature with text description and date
5. Ensures proper formatting and pagination
6. Saves with standardized naming convention
"""

import os
import sys
import re
from datetime import datetime
from pathlib import Path
from io import BytesIO

import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.utils import ImageReader

# ======================
# CONFIGURATION
# ======================
DOWNLOADS_DIR = Path.home() / "Downloads"
LETTERHEAD_PDF = Path.home() / "Documents/clinic/templates-clinic/template-letterhead/template-letterhead-2.pdf"
SIGNATURE_PNG = Path.home() / "Documents/clinic/templates-clinic/template-signature/template-signature-transparent-v1.png"  # Transparent version!
OUTPUT_DIR = Path.home() / "Documents/clinic/letters-referrals"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Signature configuration
SIGNATURE_TEXT = "Matthew King"  # Name without credentials (APAM added automatically)
SIGNATURE_TITLE = "Physiotherapist"
SIGNATURE_WIDTH = 4*cm  # Signature image width
SIGNATURE_HEIGHT = 1.5*cm  # Signature image height
SIGNATURE_X = 2.5*cm  # Position from left
SIGNATURE_Y = 10*cm  # Position from bottom (needs to be high enough for 6cm block)

# Content margins (to fit within letterhead)
CONTENT_MARGIN_TOP = 4*cm  # Space for letterhead header
CONTENT_MARGIN_BOTTOM = 5*cm  # Space for signature/footer
CONTENT_MARGIN_LEFT = 2.5*cm
CONTENT_MARGIN_RIGHT = 2.5*cm

# ======================
# HELPER FUNCTIONS
# ======================

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
    """Extract text content from PDF for parsing"""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    except Exception as e:
        print(f"⚠️  Could not extract text with pdfplumber: {e}")
        # Fallback to PyPDF2
        try:
            with open(pdf_path, 'rb') as file:
                pdf = PdfReader(file)
                for page in pdf.pages:
                    text += page.extract_text() or ""
        except Exception as e2:
            print(f"❌ Text extraction failed: {e2}")
            return ""
    return text

def parse_patient_info(text):
    """
    Parse patient name, body area, referrer from PDF text
    Adjust regex patterns based on your PDF format
    """
    patient_name = None
    body_area = None
    referrer = None
    
    # Pattern for name - adjust to your actual PDF format
    name_patterns = [
        r'(?:Patient|Re|Name):\s*([A-Z][a-z]+)\s+([A-Z][a-z]+)',
        r'Dear Dr.*\n.*regarding\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)',
        r'([A-Z][A-Z]+),\s+([A-Z][a-z]+)',  # SMITH, John format
        r'Re:\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)',
    ]
    
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            if len(match.groups()) == 2:
                first_name, last_name = match.groups()
                patient_name = f"{last_name}{first_name[0]}"  # SmithJ format
                break
    
    # Pattern for body area
    body_area_keywords = ['shoulder', 'knee', 'hip', 'ankle', 'back', 'neck', 
                          'elbow', 'wrist', 'spine', 'lumbar', 'cervical', 'thoracic',
                          'foot', 'hand', 'calf', 'hamstring', 'quadriceps']
    for keyword in body_area_keywords:
        if re.search(rf'\b{keyword}\b', text, re.IGNORECASE):
            body_area = keyword.capitalize()
            break
    
    # Pattern for referrer
    referrer_patterns = [
        r'Dear\s+(?:Dr\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+)',
        r'To:\s+(?:Dr\.?|Mr\.?|Mrs\.?|Ms\.?)\s+([A-Z][a-z]+)',
    ]
    
    for pattern in referrer_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            referrer = match.group(1)
            break
    
    return patient_name, body_area, referrer

def create_content_spacer(width, height):
    """Create a transparent spacer to push content down from header"""
    packet = BytesIO()
    can = canvas.Canvas(packet, pagesize=(width, height))
    # Just save empty transparent canvas
    can.save()
    packet.seek(0)
    return PdfReader(packet)

def create_signature_block(width, height):
    """Create signature block on a full-page canvas positioned correctly"""
    from reportlab.pdfgen.canvas import Canvas
    
    packet = BytesIO()
    # Create FULL page canvas to match letterhead
    can = Canvas(packet, pagesize=(width, height))
    
    # Start signature block higher up - leave room for letterhead header
    y_start = 12*cm  # Start 12cm from bottom (well above footer)
    y_pos = y_start
    
    # Add signature image if it exists  
    if SIGNATURE_PNG.exists():
        try:
            img = ImageReader(str(SIGNATURE_PNG))
            # Draw signature image at top of block
            can.drawImage(img, SIGNATURE_X, y_pos - SIGNATURE_HEIGHT,
                         width=SIGNATURE_WIDTH, height=SIGNATURE_HEIGHT,
                         preserveAspectRatio=True, mask='auto')
            y_pos -= SIGNATURE_HEIGHT + 0.3*cm
        except Exception as e:
            print(f"⚠️  Could not add signature image: {e}")
            y_pos -= 0.5*cm
    
    # All text in black
    can.setFillColorRGB(0, 0, 0)
    
    # Add name with credentials
    can.setFont("Helvetica-Bold", 9)
    can.drawString(SIGNATURE_X, y_pos, f"{SIGNATURE_TEXT} APAM")
    y_pos -= 0.35*cm
    
    # Add title
    can.setFont("Helvetica", 9)
    can.drawString(SIGNATURE_X, y_pos, SIGNATURE_TITLE)
    y_pos -= 0.35*cm
    
    # Add qualifications
    can.setFont("Helvetica", 9)
    can.drawString(SIGNATURE_X, y_pos, "B.Physio (Hons)")
    y_pos -= 0.5*cm
    
    # Add horizontal line
    can.setStrokeColorRGB(0, 0, 0)
    can.setLineWidth(0.5)
    can.line(SIGNATURE_X, y_pos, SIGNATURE_X + 12*cm, y_pos)
    y_pos -= 0.4*cm
    
    # Add Special Interests text
    can.setFont("Helvetica-Bold", 9)
    can.drawString(SIGNATURE_X, y_pos, "Special interests: ")
    
    # Continue with regular font on same line
    can.setFont("Helvetica", 9)
    special_interests = (
        "Lower limb injuries (hip, groin, knee, ankle, and foot); sports injuries (with special interest in all martial arts "
        "and dance injuries); tendinopathy; adolescent growth-related conditions; neck pain and headaches; complex injuries "
        "requiring detailed assessment and clinical reasoning."
    )
    
    # Text wrapping
    from textwrap import wrap
    wrapped_text = wrap(special_interests, width=95)
    first_line_start = SIGNATURE_X + 3.5*cm  # After "Special interests: "
    can.drawString(first_line_start, y_pos, wrapped_text[0])
    y_pos -= 0.35*cm
    
    # Remaining lines
    for line in wrapped_text[1:4]:
        can.drawString(SIGNATURE_X, y_pos, line)
        y_pos -= 0.35*cm
    
    can.save()
    packet.seek(0)
    
    # Read the PDF
    sig_pdf = PdfReader(packet)
    # Return signature PDF and approximate height used
    signature_height_used = y_start - y_pos
    return sig_pdf, width, signature_height_used

def add_top_spacing(page, spacing_cm=2):
    """
    Add spacing at top of page by shifting content down
    """
    try:
        from PyPDF2 import Transformation
        # Translate content down by spacing amount
        spacing_points = spacing_cm * cm
        page.add_transformation(Transformation().translate(tx=0, ty=-spacing_points))
    except (ImportError, AttributeError):
        # Older PyPDF2 version or method not available
        # Content spacing will be handled by letterhead margins
        pass
    return page

def overlay_letterhead_and_signature(source_pdf_path, letterhead_pdf_path, output_path):
    """
    Overlay letterhead on every page and add signature to last page
    If signature won't fit, create a new page for it
    Ensures content fits within letterhead margins
    Adds extra spacing at top and before signature
    """
    try:
        # Read source document
        source_pdf = PdfReader(str(source_pdf_path))
        letterhead_pdf = PdfReader(str(letterhead_pdf_path))
        
        if not letterhead_pdf.pages:
            print("❌ Letterhead PDF is empty")
            return False
        
        letterhead_page = letterhead_pdf.pages[0]
        num_pages = len(source_pdf.pages)
        
        # Get page dimensions
        page_width = float(letterhead_page.mediabox.width)
        page_height = float(letterhead_page.mediabox.height)
        
        # Create signature block (returns small PDF + dimensions)
        sig_pdf, sig_width, sig_height = create_signature_block(page_width, page_height)
        
        # Calculate if signature fits on last page
        # Assume content uses top 80% of page, signature needs bottom area
        signature_needs_space = sig_height + SIGNATURE_Y  # Total height needed from bottom
        available_space = page_height * 0.25  # Conservative estimate
        
        needs_new_page = signature_needs_space > available_space
        
        if needs_new_page:
            print("ℹ️  Content is long - adding signature on new page")
        
        # Create output PDF
        output_pdf = PdfWriter()
        
        # Process each page
        for i, page in enumerate(source_pdf.pages):
            # Add top spacing (push content down from header)
            page = add_top_spacing(page, spacing_cm=2)
            
            # Create a copy of letterhead for this page
            from PyPDF2 import PageObject
            letterhead_copy = PageObject.create_blank_page(width=page_width, height=page_height)
            
            # First add letterhead as background
            letterhead_copy.merge_page(letterhead_pdf.pages[0])
            
            # Then add content on top
            letterhead_copy.merge_page(page)
            
            # Add signature to last page - but only if it fits
            if i == num_pages - 1 and sig_pdf.pages and not needs_new_page:
                # Simply merge signature
                letterhead_copy.merge_page(sig_pdf.pages[0])
            
            output_pdf.add_page(letterhead_copy)
        
        # If signature needs new page, add it now
        if needs_new_page and sig_pdf.pages:
            # Create a BLANK page with just letterhead (no content)
            from PyPDF2 import PageObject
            
            # Create new blank page with same dimensions
            blank_page = PageObject.create_blank_page(width=page_width, height=page_height)
            
            # Add letterhead to blank page
            blank_page.merge_page(letterhead_pdf.pages[0])
            
            # Add signature to this clean page
            blank_page.merge_page(sig_pdf.pages[0])
            
            output_pdf.add_page(blank_page)
        
        # Write output
        with open(output_path, 'wb') as output_file:
            output_pdf.write(output_file)
        
        print(f"✅ Applied letterhead and signature")
        return True
        
    except Exception as e:
        print(f"❌ Overlay failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_filename(patient_name, body_area, referrer):
    """Generate filename in format: {LastName}{FirstInitial}-{BodyArea}-Letter to {Referrer}-{dd.mm.yy}.pdf"""
    date_str = datetime.now().strftime("%d.%m.%y")
    
    # Use defaults if parsing failed
    patient_name = patient_name or "UnknownPatient"
    body_area = body_area or "General"
    referrer = referrer or "Referrer"
    
    filename = f"{patient_name}-{body_area}-Letter to {referrer}-{date_str}.pdf"
    
    # Clean filename (remove invalid characters)
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    return filename

def main():
    print("🚀 PDF Letterhead Overlay & Auto-Renamer")
    print("=" * 50)
    
    # Check letterhead exists
    if not LETTERHEAD_PDF.exists():
        print(f"❌ Letterhead not found: {LETTERHEAD_PDF}")
        print(f"   Please update LETTERHEAD_PDF path in script")
        sys.exit(1)
    
    # Check signature exists (warning only)
    if not SIGNATURE_PNG.exists():
        print(f"⚠️  Signature not found: {SIGNATURE_PNG}")
        print(f"   Continuing without signature image...")
    
    # Get latest PDF
    source_pdf = get_latest_pdf(DOWNLOADS_DIR)
    
    # Extract text for parsing
    print("📖 Extracting text from PDF...")
    text = extract_text_from_pdf(source_pdf)
    
    if text:
        print(f"   Extracted {len(text)} characters")
    
    # Parse patient information
    print("🔍 Parsing patient information...")
    patient_name, body_area, referrer = parse_patient_info(text)
    
    print(f"   Patient: {patient_name or '❓ Not found'}")
    print(f"   Body Area: {body_area or '❓ Not found'}")
    print(f"   Referrer: {referrer or '❓ Not found'}")
    
    # Ask for confirmation / manual input if needed
    if not all([patient_name, body_area, referrer]):
        print("\n⚠️  Some information could not be parsed automatically.")
        response = input("Enter information manually? (y/n): ")
        if response.lower() == 'y':
            if not patient_name:
                last = input("  Last name: ")
                first_init = input("  First initial: ")
                patient_name = f"{last}{first_init}"
            if not body_area:
                body_area = input("  Body area (e.g., Shoulder, Knee): ")
            if not referrer:
                referrer = input("  Referrer name: ")
        else:
            print("\n⚠️  Using default values for missing information")
    
    # Generate output filename
    output_filename = generate_filename(patient_name, body_area, referrer)
    output_path = OUTPUT_DIR / output_filename
    
    print(f"\n📝 Output filename: {output_filename}")
    
    # Apply letterhead and signature overlay
    print("🎨 Applying letterhead and signature overlay...")
    success = overlay_letterhead_and_signature(source_pdf, LETTERHEAD_PDF, output_path)
    
    if success:
        print(f"\n✅ Complete! Saved to:")
        print(f"   {output_path}")
        
        # Show file size
        file_size = output_path.stat().st_size / 1024
        print(f"   Size: {file_size:.1f} KB")
        
        # Optional: Open the file
        response = input("\nOpen file? (y/n): ")
        if response.lower() == 'y':
            os.system(f'open "{output_path}"')
    else:
        print("\n❌ Failed to create PDF with letterhead overlay")
        sys.exit(1)

if __name__ == "__main__":
    main()
