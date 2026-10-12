"""Render og-card-source.html to og-card.png: 1200x630 CSS px drawn natively at 2x.

    python tools/make_card.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "og-card.png"

with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page(viewport={"width": 1200, "height": 630}, device_scale_factor=2)
    pg.goto((ROOT / "og-card-source.html").as_uri())
    pg.wait_for_function("document.fonts.status === 'loaded' && [...document.fonts].some(f => f.family.includes('Baloo') && f.status === 'loaded')")
    pg.screenshot(path=str(OUT))
    b.close()

size = OUT.stat().st_size
assert size < 300_000, f"{OUT.name} is {size} bytes; WhatsApp drops thumbnails over 300KB"
print(f"{OUT.name} {size} bytes")
