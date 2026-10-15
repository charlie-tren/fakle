"""Today's real headlines: One Story's committed history, plus a few oddity feeds."""
from __future__ import annotations

import datetime as dt
import email.utils
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

RAW = ("https://raw.githubusercontent.com/the-one-story/the-one-story.github.io/"
       "main/data/history/{date}.json")
# Built with chr() so no tool on the way to disk can rewrite an escape into the glyph.
QUOTES = {chr(0x2018): "'", chr(0x2019): "'", chr(0x201C): '"', chr(0x201D): '"',
          chr(0x2013): "-", chr(0x2014): "-", chr(0x2011): "-", chr(0x2010): "-",
          chr(0x00A0): " ", chr(0x202F): " "}
SUFFIX = re.compile(r"\s+[-|]\s+[A-Z][\w .&']{1,40}$")
JUNK = re.compile(r"(scores|live updates|live blog|newsletter|podcast|watch:|video:|quiz)", re.I)
# Features, explainers and opinion pieces do not read as headlines (Charlie, 11/10/2026:
# the "Did a baby dinosaur eat its own kind?" title), and a title cut off with an
# ellipsis is a fragment.
NOT_HEADLINE = re.compile(
    r"^((how|why|what|who|where|when|did|does|do|is|are|can|could|will|would|should|"
    r"here's|inside|opinion|analysis|explainer|editorial|letters?|from the archive|"
    r"the conversation|you|your|top \d+)\b|(?-i:[A-Z][A-Z ]{3,}:))", re.I)
DUPE = 0.6
# One Story's outlets are hard news; the strangest stories of a day are thin in them
# (probed 11/10/2026). Tabloid weird sections (Mirror, Daily Star) were lifestyle filler;
# Metro's and Sky's went quiet for a week (15/10/2026), leaving 2 strange headlines in 883.
ODDITIES = {
    "UPI": "https://rss.upi.com/news/odd_news.rss",
    "New York Post": "https://nypost.com/weird-but-true/feed/",
}
# Every outlet's strange stories, found by the words they are written up with. Noisy
# (sport and reviews come too); the shortlist step is what reads them.
SEARCH = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q={q}%20when:1d"
SEARCHES = ["bizarre", "%22world%20record%22", "unusual", "weird", "strange"]
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}


def sydney_today() -> str:
    return dt.datetime.now(ZoneInfo("Australia/Sydney")).date().isoformat()


def load_history(date: str, local_dir: str | None = None) -> dict | None:
    if local_dir:
        p = Path(local_dir) / f"{date}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    r = requests.get(RAW.format(date=date), timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def parse_feed(body: bytes, source: str | None, now: dt.datetime) -> list[dict]:
    """A feed's last 24 hours. With no source given, each item names its own outlet
    (Google News) and only English titles are kept: a search also returns Korean ones."""
    out = []
    for it in ET.fromstring(body).iter("item"):
        title = (it.findtext("title") or "").strip()
        try:
            when = email.utils.parsedate_to_datetime(it.findtext("pubDate") or "")
        except (TypeError, ValueError):
            continue
        if (now - when).total_seconds() > 86400 or title.lower().startswith("watch:"):
            continue
        if source is None and not clean_title(title).isascii():
            continue
        out.append({"title": title, "source": source or (it.findtext("source") or "").strip(),
                    "url": (it.findtext("link") or "").strip()})
    return out


def load_oddities() -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    feeds = list(ODDITIES.items()) + [(None, SEARCH.format(q=q)) for q in SEARCHES]
    out = []
    for source, url in feeds:
        # A dead feed costs its headlines, never the puzzle.
        try:
            r = requests.get(url, headers=UA, timeout=30)
            r.raise_for_status()
            out += parse_feed(r.content, source, now)
        except Exception as exc:
            print(f"oddities: {source or url}: {type(exc).__name__}")
    return out


def clean_title(t: str) -> str:
    for a, b in QUOTES.items():
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t).strip()
    # Until stable: some feeds stack two ("... - Region - Al Jazeera").
    while True:
        s = SUFFIX.sub("", t).strip(" -|")
        if s == t:
            return t
        t = s


def clean_source(s: str) -> str:
    """One Story's feed labels carry a lean tag or a section: "Common Dreams (US, left)",
    "BBC News - World". A player wants the outlet."""
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return re.sub(r"\s+-\s+.*$", "", s).strip()


def words(t: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", t.lower()))


def usable(t: str) -> bool:
    t = clean_title(t)
    if "?" in t or t.endswith("...") or t.endswith(chr(0x2026)) or NOT_HEADLINE.search(t):
        return False
    return len(t.split()) >= 5 and not JUNK.search(t)


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def build_pool(articles: list[dict], trump: bool = False) -> list[dict]:
    out, seen = [], []
    for a in articles:
        text = clean_title(a.get("title", ""))
        if not usable(text):
            continue
        if trump and "trump" not in words(text):
            continue
        w = words(text)
        if any(_jaccard(w, s) >= DUPE for s in seen):
            continue
        seen.append(w)
        url = a.get("url", "")
        # The page links these after a reveal, on an origin the whole hub shares.
        url = url if url.startswith(("https://", "http://")) else ""
        out.append({"text": text, "source": clean_source(a.get("source", "")), "url": url})
    return out
