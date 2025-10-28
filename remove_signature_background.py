#!/usr/bin/env python3
"""
Remove white background from signature PNG and create transparent version
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "Pillow"])
    from PIL import Image

def remove_white_background(input_path, output_path, threshold=250):
    """
    Convert white/near-white pixels to transparent
    threshold: pixels with RGB values above this become transparent (0-255)
    """
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    
    new_data = []
    for item in datas:
        # If pixel is mostly white (all RGB > threshold), make it transparent
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            new_data.append((255, 255, 255, 0))  # Transparent white
        else:
            new_data.append(item)  # Keep as-is
    
    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"✅ Saved transparent version: {output_path}")
    
    # Show stats
    transparent_count = sum(1 for item in new_data if item[3] == 0)
    total_pixels = len(new_data)
    print(f"   Made {transparent_count}/{total_pixels} pixels transparent ({transparent_count/total_pixels*100:.1f}%)")

if __name__ == "__main__":
    template_dir = Path.home() / "Documents/clinic/templates-clinic/template-signature"
    
    # Process the white-master version
    input1 = template_dir / "template-signature-white-master-v1.png"
    output1 = template_dir / "template-signature-transparent-v1.png"
    
    print("🎨 Removing white background from signature images...\n")
    
    if input1.exists():
        print(f"Processing: {input1.name}")
        remove_white_background(input1, output1)
        print()
    
    # Check other files
    print("📋 Other available signature files:")
    originals = template_dir / "originals-png"
    if originals.exists():
        for png in sorted(originals.glob("*.png")):
            size = png.stat().st_size / 1024
            print(f"  • {png.name} ({size:.1f} KB)")
    
    print("\n✅ Done! Use the transparent version in your script.")
