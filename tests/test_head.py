import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEAD = (ROOT / "index.html").read_text(encoding="utf-8")


def meta(prop):
    m = re.search(rf'<meta (?:property|name)="{re.escape(prop)}" content="([^"]*)"', HEAD)
    return m and m.group(1)


def test_share_card_is_declared_built_and_deployed():
    img = meta("og:image")
    assert img == "https://charlietrenorden.com/fakle/og-card.png"
    assert meta("twitter:card") == "summary_large_image"
    assert (ROOT / "og-card.png").stat().st_size < 300_000
    deploy = (ROOT / ".github/workflows/daily.yml").read_text(encoding="utf-8")
    assert re.search(r"cp [^\n]*og-card\.png[^\n]*_site/", deploy)
    for p in ("og:title", "og:description", "og:url", "og:type", "og:image:alt",
              "og:image:width", "og:image:height"):
        assert meta(p), p
