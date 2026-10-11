"""What the model is asked. Picks are INDICES into the pool, so a real headline
can never be reworded or invented on the way through."""
from __future__ import annotations

import llm

ROUNDS, PER = 5, 3

PICK = """You are choosing headlines for a daily game. Players see four headlines,
three real and one invented, and try to spot the invented one.

From the numbered real headlines below, choose the {n} that a reader would find
hardest to believe are real: strange, surprising or absurd, but plainly true.
Avoid deaths, disasters and violence. Group them into {rounds} rounds of {per}.
Use each headline at most once.

Reply with JSON only: {{"rounds": [[i, j, k], ...]}}

{lines}"""

FAKE = """You are writing the invented headline for each round of a daily game.
Each round has three real headlines. Write ONE new headline per round that a
careful reader could not tell apart from the three beside it.

Rules:
- Same length, register, punctuation and capitalisation style as its three.
- Same spelling convention as its three (American if they are American).
- Plausible, a little strange, never a joke.
- Only name people, places and organisations that appear somewhere in the
  real headlines given below.
- Never claim anyone committed a crime, did anything sexual, is ill or died.

Reply with JSON only: {{"fakes": ["...", ...]}} with one string per round, in order.

{rounds}"""


def pick_prompt(pool: list[dict]) -> str:
    lines = "\n".join(f"{i}. {x['text']}" for i, x in enumerate(pool))
    return PICK.format(n=ROUNDS * PER, rounds=ROUNDS, per=PER, lines=lines)


def parse_pick(raw, pool_len: int) -> list[list[int]]:
    d = llm.extract_json(raw)
    rounds = d.get("rounds") if isinstance(d, dict) else None
    if not isinstance(rounds, list) or len(rounds) != ROUNDS:
        raise ValueError(f"expected {ROUNDS} rounds")
    if any(not isinstance(r, list) or len(r) != PER for r in rounds):
        raise ValueError(f"each round needs {PER}")
    flat = [i for r in rounds for i in r]
    if len(set(flat)) != len(flat) or any(not isinstance(i, int) or not 0 <= i < pool_len for i in flat):
        raise ValueError("duplicate or out-of-range index")
    return rounds


def fake_prompt(rounds: list[list[dict]], notes: dict[int, list[str]] | None = None) -> str:
    blocks = []
    for n, r in enumerate(rounds):
        lines = "\n".join(f"- {x['text']} ({x['source']})" for x in r)
        extra = ""
        if notes and notes.get(n):
            extra = f"\nYour last attempt for this round failed: {', '.join(notes[n])}."
        blocks.append(f"Round {n + 1}:\n{lines}{extra}")
    return FAKE.format(rounds="\n\n".join(blocks))


def parse_fakes(raw, n: int) -> list[str]:
    d = llm.extract_json(raw)
    fakes = d.get("fakes") if isinstance(d, dict) else None
    if not isinstance(fakes, list) or len(fakes) != n or not all(isinstance(f, str) and f.strip() for f in fakes):
        raise ValueError(f"expected {n} fakes")
    return [f.strip() for f in fakes]
