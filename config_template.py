# PDF Tools Configuration Template
# Copy this to config.py and customize for your setup

from pathlib import Path

# ======================
# PATHS
# ======================
DOWNLOADS_DIR = Path.home() / "Downloads"
LETTERHEAD_PDF = Path.home() / "Documents/clinic/templates-clinic/template-letterhead/template-letterhead-2.pdf"
SIGNATURE_PNG = Path.home() / "Documents/clinic/templates-clinic/template-signature/template-signature-white-master-v1.png"
OUTPUT_DIR = Path.home() / "Documents/clinic/letters-referrals"

# ======================
# SIGNATURE SETTINGS
# ======================
SIGNATURE_TEXT = "Matthew King"
SIGNATURE_TITLE = "Physiotherapist"
SIGNATURE_REGISTRATION = ""  # Optional: e.g., "AHPRA: PHY0001234567"

# Signature positioning (from bottom-left corner)
from reportlab.lib.units import cm
SIGNATURE_WIDTH = 4*cm
SIGNATURE_HEIGHT = 2*cm
SIGNATURE_X = 2.5*cm  # From left edge
SIGNATURE_Y = 3*cm    # From bottom edge

# ======================
# CONTENT MARGINS
# ======================
# Adjust these to ensure content fits within your letterhead design
CONTENT_MARGIN_TOP = 4*cm     # Space for letterhead header
CONTENT_MARGIN_BOTTOM = 5*cm  # Space for signature/footer
CONTENT_MARGIN_LEFT = 2.5*cm
CONTENT_MARGIN_RIGHT = 2.5*cm

# ======================
# PARSING PATTERNS
# ======================
# Customize regex patterns to match your PDF format
BODY_AREA_KEYWORDS = [
    'shoulder', 'knee', 'hip', 'ankle', 'back', 'neck',
    'elbow', 'wrist', 'spine', 'lumbar', 'cervical', 'thoracic',
    'foot', 'hand', 'calf', 'hamstring', 'quadriceps', 'achilles',
    'rotator cuff', 'meniscus', 'acl', 'pcl', 'mcl'
]

# Add custom name patterns if your PDFs use specific formats
CUSTOM_NAME_PATTERNS = [
    # Examples (uncomment and modify as needed):
    # r'Patient Name:\s*([A-Z][a-z]+),?\s+([A-Z][a-z]+)',
    # r'Regarding:\s+([A-Z][a-z]+)\s+([A-Z][a-z]+)',
]

CUSTOM_REFERRER_PATTERNS = [
    # Examples (uncomment and modify as needed):
    # r'Referring GP:\s+(?:Dr\.?)\s+([A-Z][a-z]+)',
    # r'CC:\s+(?:Dr\.?)\s+([A-Z][a-z]+)',
]
