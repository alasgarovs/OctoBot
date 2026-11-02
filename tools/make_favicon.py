"""Regenerate icons/favicon.ico from the in-app octopus logo.

The octopus paths mirror theme.logo_pixmap, rendered onto the sidebar's dark
teal tile with bolder strokes so it stays readable down to 16x16.

Run from the repository root:
    .venv/bin/python tools/make_favicon.py
"""
import io
import sys
from pathlib import Path

from PIL import Image
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent
ACCENT = "#00D4FF"       # theme.ACCENT
TILE = "#0E3A46"         # the sidebar logo box background
TILE_BORDER = "#1E4F5E"

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect x="2" y="2" width="60" height="60" rx="14" fill="{TILE}"
        stroke="{TILE_BORDER}" stroke-width="1.5"/>
  <g transform="translate(8, 8) scale(2)">
    <g fill="none" stroke="{ACCENT}" stroke-width="1.8"
       stroke-linecap="round" stroke-linejoin="round">
      <path d="M5 12a7 7 0 0 1 14 0v1H5z"/>
      <path d="M6.5 14c0 3-1.5 4-2.5 5M10 14v5M14 14v5M17.5 14c0 3 1.5 4 2.5 5"/>
    </g>
    <circle cx="9.5" cy="10.5" r="0.9" fill="{ACCENT}"/>
    <circle cx="14.5" cy="10.5" r="0.9" fill="{ACCENT}"/>
  </g>
</svg>"""

SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def render(master=512):
    renderer = QSvgRenderer(QByteArray(SVG.encode("utf-8")))
    image = QImage(master, master, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def to_pil(image):
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return Image.open(io.BytesIO(bytes(buffer.data())))


def main():
    pil = to_pil(render())
    target = ROOT / "icons" / "favicon.ico"
    pil.save(target, format="ICO", sizes=SIZES)
    preview = Path("/tmp/opencode/favicon_preview.png")
    if preview.parent.exists():
        pil.save(preview)
    print(f"wrote {target} ({target.stat().st_size} bytes, sizes: {SIZES})")
    if preview.exists():
        print(f"preview: {preview}")


if __name__ == "__main__":
    sys.exit(main())
