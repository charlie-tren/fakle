"""Rasterise Fakle's favicon.svg into the icon files, with the right alpha for each.

    python tools/make_icons.py

Two targets that want OPPOSITE things, which is what went wrong before:

- **Browser tabs** (favicon.ico, favicon-192.png, favicon-48.png) want the corners
  TRANSPARENT, so the rounded tile reads as a tile. Flattening them onto white puts
  four white dots in the corners of every dark tab bar, which is exactly what went
  wrong on the hub.
- **apple-touch-icon.png** wants NO transparency and NO rounding: iOS applies its
  own mask and paints anything transparent BLACK. So it is drawn full-bleed in the
  tile colour with square corners and let iOS round it.

Rasterised with Playwright rather than a native SVG library so this needs nothing
installed beyond what the thumbnail job already uses.
"""

import io
import re
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SVG = (ROOT / "favicon.svg").read_text(encoding="utf-8")
TILE = "#6b4cf6"   # the face of the tile, not its darker edge

# apple-touch: same glyph, full-bleed tile, square corners.
SVG_SQUARE = SVG.replace('rx="14"', 'rx="0"')


def render(pw, svg: str, size: int, transparent: bool) -> Image.Image:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": size, "height": size})
    pg.set_content(
        f'<style>html,body{{margin:0;padding:0;background:transparent}}'
        f'svg{{display:block;width:{size}px;height:{size}px}}</style>{svg}'
    )
    png = pg.screenshot(omit_background=transparent)
    b.close()
    return Image.open(io.BytesIO(png)).convert("RGBA")


def main():
    with sync_playwright() as pw:
        big = render(pw, SVG, 192, True)
        big.save(ROOT / "favicon-192.png")
        big.resize((48, 48), Image.LANCZOS).save(ROOT / "favicon-48.png")
        # A real multi-size .ico: 16 is what a tab actually draws.
        big.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128)])

        touch = render(pw, SVG_SQUARE, 180, False)
        flat = Image.new("RGB", touch.size, TILE)
        flat.paste(touch, mask=touch.split()[3])
        flat.save(ROOT / "apple-touch-icon.png")

    for f in ("favicon-192.png", "favicon-48.png", "favicon.ico", "apple-touch-icon.png"):
        im = Image.open(ROOT / f).convert("RGBA")
        w, h = im.size
        print(f"{f:24} {w}x{h}  corner={im.getpixel((0, 0))}")


if __name__ == "__main__":
    main()
