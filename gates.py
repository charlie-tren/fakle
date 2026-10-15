"""Every rule a fake must pass. In code, not only in the prompt."""
from __future__ import annotations

import re

from pool import LABEL, clean_title, words

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
    r"rape\w*|sex\w*|porn\w*|assault\w*|abus\w*|harass\w*|affair\w*|grop\w*|"
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


def _mid_caps(titles: list[str]) -> set[str]:
    return {t.lower() for title in titles for t in re.findall(r"[A-Za-z][\w']*", title)[1:] if t[0].isupper()}


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
    # No real carries one (build drops them), so a fake that did would be the answer.
    if LABEL.search(fake):
        fails.append("label")
    known = set().union(*(words(t) for t in day_titles))
    if _proper_nouns(fake) - known - US_STATES:
        fails.append("new name")
    if required and required not in fw:
        fails.append("required")
    if fake.endswith(")"):
        fails.append("format")
    # The prompt bans the trailing "amid ..." crutch and the model wrote it anyway (trial,
    # 15/10/2026). Allowed where a real in its round has one, so it is not a fake-only trait.
    trail = re.compile(r"\s(amid|as|ahead of|after|despite|in bid to)\s", re.I)
    if trail.search(fake) and not any(trail.search(r) for r in reals):
        fails.append("trailing clause")
    # A real headline names its subject or counts something; "local council chief" and
    # "three pilots" were the fakes players spotted first (14/10/2026).
    # A word is a name if the day never writes it in lower case: Title Case headlines made
    # "Local" a name, and "Local council bans neon signage after midnight" passed (15/10/2026).
    lower = {w for t in day_titles for tok in re.findall(r"[A-Za-z][\w']*", t)
             if tok[0].islower() for w in words(tok)}
    toks = re.findall(r"[A-Za-z][\w']*", fake)
    named = [t for t in toks[1:] if t[0].isupper() and words(t) - lower - {"s", required}]
    # The first word is capitalised either way; it is a name if the day writes it as one.
    if toks and toks[0].lower() != required and words(toks[0]) - lower - {"s"} and \
            toks[0].lower() in _mid_caps(day_titles) | US_STATES:
        named.append(toks[0])
    # A number only where its round has one: asked for "a concrete detail", every fake
    # on the 14/10 trial carried a figure and almost no real did.
    counted = re.search(r"\d", fake)
    if counted and not any(re.search(r"\d", r) for r in reals):
        fails.append("number")
    if not named and not counted:
        fails.append("vague")
    # Any name shared with a real in its own round makes the pair twins, and the twin
    # nobody has heard of is the fake (15/10/2026: "Brooklyn bakery unveils robot barista
    # ... for $12" beside the real Brooklyn $15 million bird; "OpenAI pauses" beside
    # "OpenAI fires"). A name is a capitalised word the day never writes in lower case.
    mine = _proper_nouns(fake) - lower - {required}
    if any(mine & _proper_nouns(r) for r in reals):
        fails.append("borrows from its round")
    # The same opening as a real beside it, or a quote opening beside a quote opening
    # ("'I run, code, debug': Germany's chancellor" beside "'I bathe, wash dishes': Japan's PM").
    def opening(t):
        return [re.sub(r"'s$", "", w) for w in t.lower().split()[:2]]
    def quoted(t):
        return t[:1] in ("'", '"')
    if any(opening(fake) == opening(r) or (quoted(fake) and quoted(r)) for r in reals):
        fails.append("copies the opening of its round")
    # The same story by its content words: two shared with a real in its own round, or
    # three with any headline of the day (Charlie, 11/10/2026: "Ruto proposes camel milk
    # tax" beside the real Ruto milk headline).
    c = _content(fake, required)
    if any(len(c & _content(r, required)) >= 2 for r in reals) or \
            any(len(c & _content(t, required)) >= 3 for t in day_titles):
        fails.append("same story")
    return fails
