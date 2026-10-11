"""Every rule a fake must pass. In code, not only in the prompt."""
from __future__ import annotations

import re

from pool import clean_title, words

OVERLAP = 0.6
LEN_LO, LEN_HI = 0.7, 1.3
# Crime, sex, health and death. Death is barred too, so a fake is never a death; the
# picker drops reals carrying these words as well, so a barred word cannot mark a
# headline as provably real.
ALLEGATION = re.compile(
    r"\b(arrest\w*|charg\w*|indict\w*|convict\w*|jail\w*|prison\w*|sentenc\w*|guilty|"
    r"accus\w*|alleg\w*|su(e|ed|es|ing)|lawsuit\w*|probe\w*|investigat\w*|"
    r"steal\w*|stole\w*|theft\w*|thie\w*|smuggl\w*|corrupt\w*|fraud\w*|brib\w*|"
    r"launder\w*|embezzl\w*|scam\w*|drug\w*|traffick\w*|"
    r"rape\w*|sex\w*|assault\w*|abus\w*|harass\w*|affair\w*|grop\w*|"
    r"murder\w*|kill\w*|shot|shoot\w*|stab\w*|attack\w*|suicid\w*|"
    r"dies|died|dead|death\w*|dying|"
    r"cancer\w*|dementia|stroke\w*|diagnos\w*|ill|illness\w*|sick\w*|surger\w*|"
    r"hospital\w*|collaps\w*|overdose\w*|drunk\w*|pregnan\w*|disease\w*)\b", re.I)


# A state names no one, so it cannot defame anyone, and Trump-mode fakes reach for them
# constantly. People and organisations still have to come from the day's news.
US_STATES = set("""alabama alaska arizona arkansas california colorado connecticut delaware
florida georgia hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland
massachusetts michigan minnesota mississippi missouri montana nebraska nevada new hampshire
jersey mexico york north carolina dakota ohio oklahoma oregon pennsylvania rhode island south
tennessee texas utah vermont virginia washington west wisconsin wyoming""".split())


STORY_STOP = {"says", "said", "after", "over", "with", "from", "that", "this", "will", "into",
              "about", "their", "they", "have", "more", "than", "what", "when", "amid", "year",
              "years", "first", "back", "just", "make", "makes", "could", "would", "should", "new"}


def _content(t: str, required: str | None) -> set[str]:
    """Words that carry the story, compared by their first five letters so "camels" meets
    "camel" and "planking" meets "plank"."""
    out = set()
    for w in words(t):
        if len(w) < 4 or w in STORY_STOP or w == required:
            continue
        w = w[:-1] if len(w) > 4 and w.endswith("s") else w
        out.add(w[:5])
    return out


def _overlap(a: set, b: set) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _proper_nouns(t: str) -> set[str]:
    # Every capitalised word, the first included: headlines lead with their subject.
    # Tokenised with words() so "Social's" splits the same way as the day's vocabulary.
    toks = re.findall(r"[A-Za-z][\w']*", t)
    return {w for tok in toks if tok[0].isupper() for w in words(tok) if len(w) > 1}


def check_fake(fake: str, reals: list[str], day_titles: list[str], required: str | None = None) -> list[str]:
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
    if _proper_nouns(fake) - known - US_STATES:
        fails.append("new name")
    if required and required not in fw:
        fails.append("required")
    if fake.endswith(")"):
        fails.append("format")
    # Two names shared with one real in its own round means the fake is that story
    # extended ("Chad Smith launches Mocha Chad coffee line" beside the real Chad Smith).
    mine = _proper_nouns(fake) - {required}
    if any(len(mine & _proper_nouns(r)) >= 2 for r in reals):
        fails.append("borrows from its round")
    # The same story by its content words: two shared with a real in its own round, or
    # three with any headline of the day (Charlie, 11/10/2026: "Ruto proposes camel milk
    # tax" beside the real Ruto milk headline).
    c = _content(fake, required)
    if any(len(c & _content(r, required)) >= 2 for r in reals) or \
            any(len(c & _content(t, required)) >= 3 for t in day_titles):
        fails.append("same story")
    return fails
