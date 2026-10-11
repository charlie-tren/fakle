"""Every rule a fake must pass. In code, not only in the prompt."""
from __future__ import annotations

import re

from pool import clean_title, words

OVERLAP = 0.6
LEN_LO, LEN_HI = 0.7, 1.3
# Death is barred too, so a fake is never a death. A sharp player could learn that;
# accepted, because a fabricated death of a named person is the worst output possible.
ALLEGATION = re.compile(
    r"\b(arrest\w*|charged|indict\w*|convict\w*|jail\w*|prison|rape\w*|sex\w*|"
    r"assault\w*|abus\w*|affair|fraud\w*|brib\w*|launder\w*|murder\w*|kill\w*|"
    r"dies|died|dead|death|cancer|dementia|diagnos\w*|illness|hospitali[sz]\w*|"
    r"overdose|drunk|pregnan\w*)\b", re.I)


def _overlap(a: set, b: set) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _proper_nouns(t: str) -> set[str]:
    # Tokenised with words() so "Social's" splits the same way as the day's vocabulary.
    toks = re.findall(r"[A-Za-z][\w']*", t)
    return {w for tok in toks[1:] if tok[0].isupper() for w in words(tok) if len(w) > 1}


def check_fake(fake: str, reals: list[str], day_titles: list[str]) -> list[str]:
    fake = clean_title(fake)
    fails = []
    fw = words(fake)
    if any(_overlap(fw, words(t)) >= OVERLAP for t in day_titles):
        fails.append("overlap")
    mean = sum(len(r.split()) for r in reals) / len(reals)
    if not LEN_LO * mean <= len(fake.split()) <= LEN_HI * mean:
        fails.append("length")
    if ALLEGATION.search(fake):
        fails.append("allegation")
    known = set().union(*(words(t) for t in day_titles))
    if _proper_nouns(fake) - known:
        fails.append("new name")
    return fails
