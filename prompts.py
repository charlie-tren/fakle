"""What the model is asked. Picks are INDICES into the pool, so a real headline
can never be reworded or invented on the way through."""
from __future__ import annotations

import llm

ROUNDS, PER = 5, 3
PICK_ROUNDS = ROUNDS + 1   # one spare, so a round whose fake never passes does not sink the mode

PICK = """You are choosing headlines for Fakle, a daily game whose whole point is to show
how strange the world is. Players see four headlines, three real and one invented, and
try to spot the invented one.

From the numbered real headlines below, choose the {n} most absurd, the ones a reader
would least believe are real. The bar is "Candidate named Hitler Mussolini elected mayor
in Peru": true, and barely believable. {focus}

Leave out anything boring: ordinary politics, markets, sport results, routine business,
diplomacy and policy announcements, however important. Leave out deaths, disasters and
violence. If a headline would not make someone say "wait, really?", it does not belong.

Group them into {rounds} rounds of {per}. Use each headline at most once. Each round's
headlines are about three different stories.

Reply with JSON only: {{"rounds": [[i, j, k], ...]}}

{lines}"""

TRUMP_FOCUS = ("Every headline here involves Trump: pick the craziest things Trump said, "
               "did or was caught up in today, not the routine politics.")

# One shape per round, so the five fakes do not share a structure (Charlie, 11/10/2026:
# "all the fake ones have the same kind of structure - easy to guess after a while").
SHAPES = [
    "short and punchy, with no trailing clause",
    "built around a quote in quotation marks",
    "opens with a number or a statistic",
    "a town, council, school or business doing something strange",
    "an official ban, ruling or rule that sounds absurd",
    "an animal, an object or a food at the centre of the story",
    "a person with an unusual record, job or habit",
]

FAKE = """You are writing the invented headline for each round of a daily game.
Each round has three real headlines. Write ONE new headline per round that a
careful reader could not tell apart from the three beside it.

A good fake is plausible, specific and quietly odd, as strange as the real ones beside
it. Example of a fake that worked: "Singapore installs smart misting poles along walkways
to combat afternoon heat".

Rules:
- Never end with an "amid ...", "as ...", "ahead of ..." or "after ..." clause. That
  crutch is how earlier fakes gave themselves away.
- Each fake reports a different event from all three in its round. Never combine,
  rephrase or borrow phrases from them: a fake stitched from its neighbours is the
  first thing a player spots.
- Steer well clear of every real story below, the other headlines included:
  never restate, paraphrase, extend or contradict one. A fake that turns out to be true is
  the worst mistake this game can make. Put the names in a situation none of today's
  headlines describe.
- Same length, register, punctuation and capitalisation style as its three.
- Same spelling convention as its three (American if they are American).
- Plausible, a little strange, never a joke.
- Only name people, places and organisations that appear somewhere in the real
  headlines below, including the list of other real headlines from today.
- Never claim anyone committed a crime, did anything sexual, is ill or died.

Reply with JSON only: {{"fakes": ["...", ...]}} with one string per round, in order.

{rounds}

Other real headlines from today (for names only, not phrasing):
{others}"""


def pick_prompt(pool: list[dict], required: str | None = None, rounds: int = PICK_ROUNDS) -> str:
    lines = "\n".join(f"{i}. {x['text']}" for i, x in enumerate(pool))
    focus = TRUMP_FOCUS if required == "trump" else ""
    return PICK.format(n=rounds * PER, rounds=rounds, per=PER, lines=lines, focus=focus)


SHORTLIST = """You are helping pick headlines for Fakle, a daily game whose whole point is to
show how strange the world is. From the numbered real headlines below, nominate the {k}
that a reader would least believe are real: absurd, but true. The bar is "Candidate named
Hitler Mussolini elected mayor in Peru". {focus} Nothing boring, nothing about deaths,
disasters or violence.

Reply with JSON only: {{"picks": [i, j, ...]}}

{lines}"""


def shortlist_prompt(chunk: list[dict], k: int, required: str | None = None) -> str:
    lines = "\n".join(f"{i}. {x['text']}" for i, x in enumerate(chunk))
    focus = TRUMP_FOCUS if required == "trump" else ""
    return SHORTLIST.format(k=k, lines=lines, focus=focus)


def parse_shortlist(raw, n: int) -> list[int]:
    d = llm.extract_json(raw)
    picks = d.get("picks") if isinstance(d, dict) else None
    if not isinstance(picks, list):
        raise ValueError("expected picks")
    out = []
    for i in picks:
        if isinstance(i, int) and 0 <= i < n and i not in out:
            out.append(i)
    if not out:
        raise ValueError("no valid picks")
    return out


def parse_pick(raw, pool_len: int, rounds: int = PICK_ROUNDS) -> list[list[int]]:
    want = rounds
    d = llm.extract_json(raw)
    rounds = d.get("rounds") if isinstance(d, dict) else None
    if not isinstance(rounds, list) or len(rounds) != want:
        raise ValueError(f"expected {want} rounds")
    if any(not isinstance(r, list) or len(r) != PER for r in rounds):
        raise ValueError(f"each round needs {PER}")
    flat = [i for r in rounds for i in r]
    if len(set(flat)) != len(flat) or any(not isinstance(i, int) or not 0 <= i < pool_len for i in flat):
        raise ValueError("duplicate or out-of-range index")
    return rounds


def fake_prompt(rounds: list[list[dict]], notes: dict[int, list[str]] | None = None,
                others: list[dict] | None = None, required: str | None = None,
                seed: str = "") -> str:
    blocks = []
    start = sum(map(ord, seed)) % len(SHAPES)
    for n, r in enumerate(rounds):
        # No source labels: the model copies them into its fake.
        lines = "\n".join(f"- {x['text']}" for x in r)
        extra = ""
        if notes and notes.get(n):
            extra = f"\nYour last attempt for this round failed: {', '.join(notes[n])}."
        # A range, the same one the length gate checks; a single target made the model
        # pad its fakes with a stray last word to hit it.
        mean = sum(len(x["text"].split()) for x in r) / len(r)
        lo, hi = round(mean * 0.7 + 0.49), int(mean * 1.3)
        shape = (f"\nShape for this round: {SHAPES[(start + n) % len(SHAPES)]}."
                 f"\nLength: between {lo} and {hi} words.")
        blocks.append(f"Round {n + 1}:\n{lines}{shape}{extra}")
    other = "\n".join(f"- {x['text']}" for x in (others or [])) or "(none)"
    text = FAKE.format(rounds="\n\n".join(blocks), others=other)
    if required:
        # Every real in the round carries it, so a fake without it is the answer.
        text = text.replace("Rules:\n", f"Rules:\n- Every fake must mention {required.title()}, "
                            "but not always as the first word.\n", 1)
    return text


def parse_fakes(raw, n: int) -> list[str]:
    d = llm.extract_json(raw)
    fakes = d.get("fakes") if isinstance(d, dict) else None
    if not isinstance(fakes, list) or len(fakes) != n or not all(isinstance(f, str) and f.strip() for f in fakes):
        raise ValueError(f"expected {n} fakes")
    return [f.strip() for f in fakes]
