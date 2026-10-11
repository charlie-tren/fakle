"""Today's real headlines, read from One Story's committed history. No feeds here."""
from __future__ import annotations

import datetime as dt
import json
import re
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
    r"^(how|why|what|who|where|when|did|does|do|is|are|can|could|will|would|should|"
    r"here's|inside|opinion|analysis|explainer|editorial|letters?)\b", re.I)
DUPE = 0.6


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
        out.append({"text": text, "source": a.get("source", ""), "url": url})
    return out
