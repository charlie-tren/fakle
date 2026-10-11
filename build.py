"""Today's Fakle. Reads One Story, writes puzzle.json, or writes nothing."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import gates
import llm
import pool
import prompts

MIN_POOL = 15
PICK_CAP = 250   # Groq's free tier allows 12K tokens a minute; ~660 headlines is ~10K
OTHERS = 100     # headlines shown to the fake writer as a source of names
FAKE_TRIES = 3
MODES = {"normal": None, "trump": "trump"}   # mode -> word every headline in it carries


STOP = {"says", "said", "after", "over", "with", "from", "that", "this", "will", "into",
        "about", "their", "they", "have", "more", "than", "what", "when", "amid", "year",
        "years", "first", "back", "just", "make", "makes", "could", "would", "should"}


def same_story(a: str, b: str, required: str | None = None) -> bool:
    """Two content words in common reads as one story, and two reals on one story
    vouch for each other, leaving the fake as the odd one out."""
    def content(t):
        return {w for w in pool.words(t) if len(w) >= 4 and w not in STOP and w != required}
    return len(content(a) & content(b)) >= 2


def _pick(p, gen, required=None):
    best = None
    for _ in range(3):
        raw, _prov = gen(prompts.pick_prompt(p))
        try:
            rounds = prompts.parse_pick(raw, len(p))
        except ValueError:
            continue
        best = rounds
        if not any(same_story(p[a]["text"], p[b]["text"], required)
                   for r in rounds for i, a in enumerate(r) for b in r[i + 1:]):
            return rounds
    # A same-story round is a weaker puzzle, not a broken one: better than no puzzle.
    return best


def make_mode(p: list[dict], gen, seed: str, day: list[str] | None = None,
              required: str | None = None, others_pool: list[dict] | None = None) -> list[dict] | None:
    # A real carrying a barred word could never be the fake, so it would be a free
    # elimination. It stays in the day's vocabulary; it just cannot be picked.
    day = day if day is not None else [x["text"] for x in p]
    p = [x for x in p if not gates.ALLEGATION.search(x["text"])]
    if len(p) < MIN_POOL:
        return None
    if len(p) > PICK_CAP:
        keep = sorted(random.Random(seed).sample(range(len(p)), PICK_CAP))
        p = [p[i] for i in keep]
    idx = _pick(p, gen, required)
    if idx is None:
        print(f"{seed}: no valid pick")
        return None
    rounds = [[p[i] for i in r] for r in idx]
    picked = {i for r in idx for i in r}
    if others_pool is None:
        others = [x for i, x in enumerate(p) if i not in picked][:OTHERS]
    else:
        # The name source must match the gate's vocabulary, which is the whole day:
        # shown only Trump headlines, the writer invented names the gate then rejected.
        taken = {p[i]["text"] for i in picked}
        rest = [x for x in others_pool if x["text"] not in taken and not gates.ALLEGATION.search(x["text"])]
        others = random.Random(seed).sample(rest, min(OTHERS, len(rest)))
    fakes: dict[int, str] = {}
    notes: dict[int, list[str]] = {}
    todo = list(range(len(rounds)))
    for _ in range(FAKE_TRIES):
        # Only the rounds still failing go back, each with the reasons it failed.
        raw, _prov = gen(prompts.fake_prompt([rounds[t] for t in todo],
                                             {k: notes[t] for k, t in enumerate(todo) if t in notes},
                                             others, required))
        try:
            got = prompts.parse_fakes(raw, len(todo))
        except ValueError:
            continue
        still = []
        for t, f in zip(todo, got):
            why = gates.check_fake(f, [x["text"] for x in rounds[t]], day, required)
            if why:
                # Printed so a dropped mode says which rule dropped it.
                print(f"{seed} round {t + 1} rejected ({', '.join(why)}): {f}")
                notes[t] = why
                still.append(t)
            else:
                fakes[t] = pool.clean_title(f)
        todo = still
        if not todo:
            break
    if todo:
        return None
    out = []
    for n, r in enumerate(rounds):
        pos = random.Random(f"{seed}:{n}").randrange(4)
        heads = [dict(x) for x in r]
        heads.insert(pos, {"text": fakes[n], "source": "", "url": ""})
        out.append({"headlines": heads, "fake": pos})
    return out


def build(date: str, history: dict, gen, modes=tuple(MODES)) -> dict:
    arts = history["articles"]
    # Every mode is gated against the WHOLE day, so a Trump fake cannot restate a real
    # non-Trump story and get it labelled as made up.
    everyone = pool.build_pool(arts)
    day = [x["text"] for x in everyone]
    result = {"date": date, "providers": {}}
    for name in modes:
        used = {"p": None}

        def tracked(prompt):
            raw, prov = gen(prompt)
            used["p"] = prov
            return raw, prov
        try:
            result[name] = make_mode(pool.build_pool(arts, trump=name == "trump"), tracked,
                                     f"{date}:{name}", day=day, required=MODES[name],
                                     others_pool=everyone if MODES[name] else None)
        except llm.NoProvider as exc:
            # A spent quota in one mode must not cost the other its puzzle.
            print(f"{date} {name}: no provider: {str(exc)[:160]}")
            result[name] = None
        result["providers"][name] = used["p"]
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=pool.sydney_today())
    ap.add_argument("--local")
    ap.add_argument("--out", default="puzzle.json")
    a = ap.parse_args(argv)
    out = Path(a.out)
    have = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    if have.get("date") != a.date:
        have = {}
    missing = [m for m in MODES if not have.get(m)]
    if not missing:
        print(f"{a.date} already built")
        return 0
    history = pool.load_history(a.date, a.local)
    if history is None:
        print(f"{a.date}: waiting for One Story")
        return 0
    new = build(a.date, history, lambda prompt: llm.generate(prompt), modes=missing)
    if not any(new.get(m) for m in missing):
        print(f"{a.date}: {', '.join(missing)} failed, nothing written")
        return 0 if have else 1
    # A mode already published today is never replaced, only a missing one filled.
    result = {"date": a.date, "providers": dict(have.get("providers", {}))}
    for m in MODES:
        result[m] = have.get(m) or new.get(m)
        if not have.get(m):
            result["providers"][m] = new["providers"].get(m)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.date}: " + " ".join(f"{m}={'ok' if result[m] else 'none'}" for m in MODES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
