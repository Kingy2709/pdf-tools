#!/usr/bin/env python3
"""
Test script to verify letterhead overlay setup
Checks that all required files exist and displays current configuration
"""

from pathlib import Path
from reportlab.lib.units import cm
import sys

# Import config from main script
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 PDF Letterhead Setup Verification")
print("=" * 60)

# Check paths
LETTERHEAD_PDF = Path.home() / "Documents/clinic/templates-clinic/template-letterhead/template-letterhead-2.pdf"
SIGNATURE_PNG = Path.home() / "Documents/clinic/templates-clinic/template-signature/template-signature-white-master-v1.png"
DOWNLOADS_DIR = Path.home() / "Downloads"
OUTPUT_DIR = Path.home() / "Documents/clinic/letters-referrals"

checks = []

# Letterhead PDF
if LETTERHEAD_PDF.exists():
    size = LETTERHEAD_PDF.stat().st_size / 1024
    checks.append(f"✅ Letterhead PDF: {LETTERHEAD_PDF.name} ({size:.1f} KB)")
else:
    checks.append(f"❌ Letterhead PDF NOT FOUND: {LETTERHEAD_PDF}")

# Signature PNG
if SIGNATURE_PNG.exists():
    size = SIGNATURE_PNG.stat().st_size / 1024
    checks.append(f"✅ Signature PNG: {SIGNATURE_PNG.name} ({size:.1f} KB)")
else:
    checks.append(f"⚠️  Signature PNG NOT FOUND: {SIGNATURE_PNG}")
    checks.append(f"   (Optional - will work without it)")

# Downloads directory
if DOWNLOADS_DIR.exists():
    pdf_count = len(list(DOWNLOADS_DIR.glob("*.pdf")))
    checks.append(f"✅ Downloads folder: {pdf_count} PDF(s) found")
else:
    checks.append(f"❌ Downloads folder NOT FOUND: {DOWNLOADS_DIR}")

# Output directory
if OUTPUT_DIR.exists():
    checks.append(f"✅ Output folder exists: {OUTPUT_DIR}")
else:
    checks.append(f"⚠️  Output folder will be created: {OUTPUT_DIR}")

print("\n📋 File Checks:")
for check in checks:
    print(f"  {check}")

# Check dependencies
print("\n📦 Dependency Checks:")
try:
    import PyPDF2
    print(f"  ✅ PyPDF2: {PyPDF2.__version__}")
except ImportError:
    print(f"  ❌ PyPDF2 not installed (pip install PyPDF2)")

try:
    import pdfplumber
    print(f"  ✅ pdfplumber: {pdfplumber.__version__}")
except ImportError:
    print(f"  ❌ pdfplumber not installed (pip install pdfplumber)")

try:
    import reportlab
    print(f"  ✅ reportlab: {reportlab.Version}")
except ImportError:
    print(f"  ❌ reportlab not installed (pip install reportlab)")

# Configuration summary
print("\n⚙️  Current Configuration:")
print(f"  Signature text: Matthew King")
print(f"  Signature title: Physiotherapist")
print(f"  Signature position: ({2.5*cm:.0f}pt, {3*cm:.0f}pt)")
print(f"  Signature size: {4*cm:.0f}pt × {2*cm:.0f}pt")

print("\n" + "=" * 60)
all_critical_ok = LETTERHEAD_PDF.exists() and DOWNLOADS_DIR.exists()

if all_critical_ok:
    print("✅ Setup complete! Ready to process PDFs")
    print("\nRun: ./run_merge_letterhead.sh")
else:
    print("❌ Setup incomplete - fix errors above")
    sys.exit(1)
