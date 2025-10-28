# PDF Letterhead Overlay - Usage Guide

## ✅ Setup Complete!

Your PDF processing system is ready. Here's what's configured:

### Files Located
- ✅ **Letterhead**: `template-letterhead-2.pdf` (54.4 KB)
- ✅ **Signature**: `template-signature-white-master-v1.png` (73.4 KB)
- ✅ **Downloads**: 420 PDFs ready to process
- ✅ **Dependencies**: PyPDF2, pdfplumber, reportlab installed

### Current Settings
- **Signature**: Matthew King, Physiotherapist
- **Date format**: dd/mm/yyyy (auto-added)
- **Output format**: `{LastName}{FirstInitial}-{BodyArea}-Letter to {Referrer}-{dd.mm.yy}.pdf`
- **Output folder**: `~/Documents/clinic/letters-referrals/`

---

## 🚀 Quick Start

### Process Latest PDF from Downloads

```bash
cd ~/dev/python/pdf-tools
./run_merge_letterhead.sh
```

This will:
1. Find the latest PDF in your Downloads folder
2. Extract text and parse: patient name, body area, referrer
3. Overlay letterhead template on every page
4. Add signature + name + title + date on last page
5. Save with auto-generated filename
6. Prompt to open the result

### Test Your Setup

```bash
cd ~/dev/python/pdf-tools
source venv/bin/activate
python3 test_setup.py
```

---

## ⚙️ Customization

### Change Signature Details

Edit `merge_letterhead_and_rename.py` lines 30-35:

```python
SIGNATURE_TEXT = "Your Name"
SIGNATURE_TITLE = "Your Title"
```

### Adjust Signature Position

Edit lines 36-41:

```python
SIGNATURE_WIDTH = 4*cm
SIGNATURE_HEIGHT = 2*cm
SIGNATURE_X = 2.5*cm  # From left edge
SIGNATURE_Y = 3*cm    # From bottom edge
```

### Change Content Margins

Edit lines 43-47 to ensure content fits within your letterhead:

```python
CONTENT_MARGIN_TOP = 4*cm     # Space for letterhead header
CONTENT_MARGIN_BOTTOM = 5*cm  # Space for signature/footer
CONTENT_MARGIN_LEFT = 2.5*cm
CONTENT_MARGIN_RIGHT = 2.5*cm
```

### Improve Text Parsing

The script uses regex patterns to extract patient/referrer info. If parsing fails, edit the patterns in the `parse_patient_info()` function (lines 59-98) to match your PDF format.

---

## 📝 Manual Input Mode

If automatic parsing fails, the script will prompt you to enter information manually:

```
⚠️  Some information could not be parsed automatically.
Enter information manually? (y/n): y
  Last name: Smith
  First initial: J
  Body area (e.g., Shoulder, Knee): Knee
  Referrer name: Johnson
```

---

## 🔧 Troubleshooting

### "No PDF files found in Downloads"
- Ensure you have a PDF in ~/Downloads
- Or edit `DOWNLOADS_DIR` in the script to point elsewhere

### "Letterhead not found"
- Check the path in `LETTERHEAD_PDF` (line 20)
- Verify file exists: `ls -la ~/Documents/clinic/templates-clinic/template-letterhead/`

### "Could not add signature image"
- Check the path in `SIGNATURE_PNG` (line 21)
- Verify it's a valid PNG file
- Script will continue without signature if file missing

### Parsing doesn't work
1. Run the script and copy the extracted text
2. Look at the patterns in `parse_patient_info()`
3. Adjust regex to match your PDF format
4. Or use manual input mode

---

## 📁 File Structure

```
pdf-tools/
├── merge_letterhead_and_rename.py  # Main script
├── run_merge_letterhead.sh         # Quick runner
├── test_setup.py                   # Verify setup
├── requirements.txt                # Dependencies
├── config_template.py              # Configuration template
├── README.md                       # Script overview
└── USAGE.md                        # This file
```

---

## 🎯 Next Steps

1. **Test with a sample PDF**: Download a test PDF and run the script
2. **Fine-tune parsing**: Adjust regex patterns if needed
3. **Create alias**: Add to ~/.zshrc:
   ```bash
   alias merge-pdf="bash ~/dev/python/pdf-tools/run_merge_letterhead.sh"
   ```
4. **Optional**: Set up as Raycast script for quick access
5. **Optional**: Create Hazel/Automator rule to auto-process Downloads

---

## 💡 Tips

- The script always uses the **most recent PDF** in Downloads
- Letterhead is overlaid on **every page** (not just first)
- Signature appears on **last page only**
- Date is automatically added (current date)
- Filename uses **dd.mm.yy** format (e.g., 21.10.25)
- Content should stay within letterhead margins automatically
