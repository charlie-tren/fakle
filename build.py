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
FAKE_TRIES = 3


def _pick(p, gen):
    for _ in range(2):
        raw, _prov = gen(prompts.pick_prompt(p))
        try:
            return prompts.parse_pick(raw, len(p))
        except ValueError:
            continue
    return None


def make_mode(p: list[dict], gen, seed: str) -> list[dict] | None:
    if len(p) < MIN_POOL:
        return None
    idx = _pick(p, gen)
    if idx is None:
        return None
    rounds = [[p[i] for i in r] for r in idx]
    day = [x["text"] for x in p]
    fakes: dict[int, str] = {}
    notes: dict[int, list[str]] = {}
    todo = list(range(len(rounds)))
    for _ in range(FAKE_TRIES):
        # Only the rounds still failing go back, each with the reasons it failed.
        raw, _prov = gen(prompts.fake_prompt([rounds[t] for t in todo],
                                             {k: notes[t] for k, t in enumerate(todo) if t in notes}))
        try:
            got = prompts.parse_fakes(raw, len(todo))
        except ValueError:
            continue
        still = []
        for t, f in zip(todo, got):
            why = gates.check_fake(f, [x["text"] for x in rounds[t]], day)
            if why:
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


def build(date: str, history: dict, gen) -> dict:
    provider = {"used": None}

    def tracked(prompt):
        raw, prov = gen(prompt)
        provider["used"] = prov
        return raw, prov

    arts = history["articles"]
    return {
        "date": date,
        "normal": make_mode(pool.build_pool(arts), tracked, f"{date}:normal"),
        "trump": make_mode(pool.build_pool(arts, trump=True), tracked, f"{date}:trump"),
        "provider": provider["used"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=pool.sydney_today())
    ap.add_argument("--local")
    ap.add_argument("--out", default="puzzle.json")
    a = ap.parse_args(argv)
    out = Path(a.out)
    if out.exists() and json.loads(out.read_text(encoding="utf-8")).get("date") == a.date:
        print(f"{a.date} already built")
        return 0
    history = pool.load_history(a.date, a.local)
    if history is None:
        print(f"{a.date}: waiting for One Story")
        return 0
    result = build(a.date, history, lambda prompt: llm.generate(prompt))
    if result["normal"] is None and result["trump"] is None:
        print(f"{a.date}: both modes failed, nothing written")
        return 1
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{a.date}: normal={'ok' if result['normal'] else 'none'} "
          f"trump={'ok' if result['trump'] else 'none'} via {result['provider']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
