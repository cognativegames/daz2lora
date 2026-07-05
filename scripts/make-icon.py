"""Generate daz2lora.ico — dark rounded rect with "D2L" text.

Run: python scripts/make-icon.py
Requires Pillow (installed automatically if missing).
Output: daz2lora.ico in repo root.
"""
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def main() -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
        from PIL import Image, ImageDraw, ImageFont

    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r = 12
    draw.rounded_rectangle([0, 0, size - 1, size - 1], r, fill=(30, 30, 30, 255))

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except OSError:
        try:
            font = ImageFont.truetype("C:\\Windows\\Fonts\\segoeui.ttf", 22)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "D2L", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), "D2L", fill=(13, 115, 119, 255), font=font)

    dest = REPO / "daz2lora.ico"
    img.save(dest, format="ICO", sizes=[(64, 64)])
    print(f"✓ {dest}")


if __name__ == "__main__":
    main()
