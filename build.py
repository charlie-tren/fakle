"""Today's Fakle. Reads One Story, writes puzzle.json, or writes nothing."""
from __future__ import annotations

import argparse
import datetime
import json
import random
import re
import sys
from pathlib import Path

import requests

import gates
import llm
import pool
import prompts

TRUMP_ROUNDS = 1   # the last round of the day; every headline in it is about Trump
CHUNK = 200      # headlines per prompt: Groq's free tier allows 8K tokens a minute
NOMINATE = 8     # at least this many of each chunk's strangest go through to the final pick
OTHERS = 100     # headlines shown to the fake writer as a source of names
FAKE_TRIES = 5
JUDGE_TRIES = 2  # rounds a model can tell apart are sent back this many times at most
MEMORY_DAYS = 7  # a story picked within this many days is not picked again
HARD_SHOWN = 8   # fakes that fooled the most players, shown to the writer
HARD_KEPT = 30
HARD_MIN_PLAYERS = 5
CROWD = "https://fakle-stats.charlietrenorden.com/stats?date={date}&id={id}"
# Dropped before sampling a big pool, so the sample is dense in strange stories. Only a
# filter on the full day: Trump mode's pool is small and its politics are the point.
BORING = re.compile(
    r"\b(shares?|stocks?|markets?|earnings|profit|revenue|investors?|gdp|inflation|interest rates?|"
    r"budget|tariffs?|summit|talks|ceasefire|sanctions?|minister|parliament|election|poll|"
    r"league|cup|coach|match|semi-final|final|quarterly|forecasts?|opposition|protests?|"
    r"lawmakers?|senators?|congress|ministry)\b", re.I)
MODES = {"normal": None, "trump": "trump"}   # mode -> word every headline in it carries
# Grim stories are not the strange-world game, however odd (14/10/2026: a plane crash and
# "decaying bodies" made the general rounds). Trump's round keeps its politics.
DARK = re.compile(
    r"\b(crash\w*|bod(y|ies)|corpses?|war|wars|troops?|military|missiles?|bomb\w*|explosi\w*|"
    r"blasts?|sabotag\w*|hostages?|refugees?|earthquakes?|floods?|flooding|wildfires?|"
    r"hurricanes?|typhoons?|airstrikes?|invasion|hezbollah|hamas|gaza|famine|starv\w*|"
    r"massacre\w*|genocide)\b", re.I)


STOP = {"says", "said", "after", "over", "with", "from", "that", "this", "will", "into",
        "about", "their", "they", "have", "more", "than", "what", "when", "amid", "year",
        "years", "first", "back", "just", "make", "makes", "could", "would", "should"}


def same_story(a: str, b: str, required: str | None = None) -> bool:
    """Two content words in common reads as one story, and two reals on one story
    vouch for each other, leaving the fake as the odd one out."""
    def content(t):
        return {w for w in pool.words(t) if len(w) >= 4 and w not in STOP and w != required}
    return len(content(a) & content(b)) >= 2


def _name_pairs(t: str, required: str | None) -> set[tuple[str, str]]:
    toks = [re.sub(r"'s$", "", w.lower()) if w[0].isupper() else None
            for w in re.findall(r"[A-Za-z][\w']*", t)]
    skip = {required, "donald"}
    return {(a, b) for a, b in zip(toks, toks[1:]) if a and b and not {a, b} & skip}


def echoes(t: str, recent: list[str], required: str | None = None) -> bool:
    """The same story as one picked in the last week: a shared two-word name ("Kid Rock")
    or the same-story test. Two Kid Rock rounds in three days, 12-14/10/2026."""
    mine = _name_pairs(t, required)
    return any(mine & _name_pairs(r, required) or same_story(t, r, required) for r in recent)


def remember(mem: dict, date: str, rounds: list[dict]) -> dict:
    """The week's real headlines, today's replacing any earlier build of today."""
    start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=MEMORY_DAYS)).isoformat()
    recent = {d: t for d, t in (mem.get("recent") or {}).items() if start <= d < date}
    recent[date] = [h["text"] for r in rounds for i, h in enumerate(r.get("headlines", []))
                    if i != r.get("fake")]
    return {**mem, "recent": recent}


def harvest(mem: dict, puzzle: dict, crowd: dict) -> dict:
    """A finished day's general-round fakes, ranked by how many players they fooled."""
    n = crowd.get("players", 0)
    if n < HARD_MIN_PLAYERS or puzzle.get("date") in {h["date"] for h in mem.get("hard", [])}:
        return mem
    rounds = puzzle.get("rounds") or []
    general = rounds[:-1] if puzzle.get("trump_round") else rounds
    new = []
    for r, counts in zip(general, crowd.get("rounds", [])):
        fooled = 1 - counts[r["fake"]] / n
        new.append({"text": r["headlines"][r["fake"]]["text"], "fooled": round(fooled, 3),
                    "players": n, "date": puzzle["date"]})
    hard = sorted(mem.get("hard", []) + new, key=lambda h: -h["fooled"])[:HARD_KEPT]
    return {**mem, "hard": hard}


def fetch_crowd(puzzle: dict) -> dict:
    try:
        r = requests.get(CROWD.format(date=puzzle["date"], id=puzzle.get("id", "")), timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        print(f"crowd: {type(exc).__name__}")
        return {}


def recent_texts(mem: dict, date: str) -> list[str]:
    start = (datetime.date.fromisoformat(date) - datetime.timedelta(days=MEMORY_DAYS)).isoformat()
    return [t for d, ts in sorted((mem.get("recent") or {}).items()) if start <= d < date for t in ts]


CONNECTORS = (" amid ", " as ", " ahead of ", " after ", " in bid to ", " despite ")


SMALL = {"a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "but", "by", "as"}


def _is_title_case(t: str) -> bool:
    long = [w for w in t.split() if len(w.strip("'\"")) >= 4]
    return bool(long) and sum(w.strip("'\"")[:1].isupper() for w in long) / len(long) >= 0.7


def match_case(fake: str, reals: list[str]) -> str:
    """Real outlets write in Title Case or sentence case; a fake always in sentence case
    beside a Title Case round is a tell. Follow the round's majority."""
    if sum(_is_title_case(r) for r in reals) * 2 <= len(reals):
        return fake
    out = []
    for i, w in enumerate(fake.split()):
        lead = len(w) - len(w.lstrip("'\""))
        core = w[lead:]
        if i == 0 or core.lower() not in SMALL:
            core = core[:1].upper() + core[1:]
        out.append(w[:lead] + core)
    return " ".join(out)


def structure_clash(fakes: list[str], required: str | None = None) -> set[int]:
    """Indices of fakes that share an opening or a connector with an earlier one."""
    seen_open, seen_conn, clash = set(), set(), set()
    for i, f in enumerate(fakes):
        w = [x for x in f.lower().split() if x != required]
        opening = " ".join(w[:2])
        conns = {c for c in CONNECTORS if c in f" {f.lower()} "}
        if opening in seen_open or conns & seen_conn:
            clash.add(i)
        seen_open.add(opening)
        seen_conn |= conns
    return clash


def _pick(p, gen, required=None, n=prompts.PICK_ROUNDS):
    best = None
    for _ in range(3):
        raw, _prov = gen(prompts.pick_prompt(p, required, n))
        try:
            rounds = prompts.parse_pick(raw, len(p), n)
        except ValueError:
            continue
        best = rounds
        if not any(same_story(p[a]["text"], p[b]["text"], required)
                   for r in rounds for i, a in enumerate(r) for b in r[i + 1:]):
            return rounds
    # A same-story round is a weaker puzzle, not a broken one: better than no puzzle.
    return best


def _judged(rounds, fakes, done, gen, seed) -> dict[int, str]:
    """Rounds where a model, shown the four as a player sees them, picks the fake."""
    shown, where = [], []
    for t in done:
        heads = [x["text"] for x in rounds[t]]
        pos = random.Random(f"{seed}:judge:{t}").randrange(4)
        heads.insert(pos, fakes[t])
        shown.append(heads)
        where.append(pos)
    try:
        raw, _prov = gen(prompts.judge_prompt(shown))
        guesses, why = prompts.parse_judge(raw, len(done))
    except (ValueError, llm.NoProvider) as exc:
        print(f"{seed}: judge skipped: {exc}")
        return {}
    caught = {t: w for t, g, pos, w in zip(done, guesses, where, why) if g == pos}
    for t, w in caught.items():
        print(f"{seed} round {t + 1} spotted by the judge ({w}): {fakes[t]}")
    return caught


def make_mode(p: list[dict], gen, seed: str, day: list[str] | None = None,
              required: str | None = None, others_pool: list[dict] | None = None,
              count: int = prompts.ROUNDS, recent: list[str] | None = None,
              hard: list[str] | None = None) -> list[dict] | None:
    picks = count + 1                      # one spare round
    min_pool = picks * prompts.PER
    # A real carrying a barred word could never be the fake, so it would be a free
    # elimination. It stays in the day's vocabulary; it just cannot be picked.
    day = day if day is not None else [x["text"] for x in p]
    p = [x for x in p if not gates.ALLEGATION.search(x["text"]) and not pool.LABEL.search(x["text"])]
    if required is None:
        p = [x for x in p if not DARK.search(x["text"])]
    if recent:
        fresh = [x for x in p if not echoes(x["text"], recent, required)]
        # A thin day keeps a repeat rather than losing its puzzle.
        p = fresh if len(fresh) >= 2 * min_pool else p
    if len(p) < min_pool:
        return None
    if len(p) > CHUNK:
        lively = [x for x in p if not BORING.search(x["text"])]
        p = lively if len(lively) >= min_pool else p
    if len(p) > CHUNK:
        # Every headline of the day is read: each chunk nominates its strangest and the
        # final pick is made from those, so the best story cannot miss a random sample.
        shortlist = []
        # Enough nominees that the final pick has twice what it needs: two chunks of eight
        # gave 16 finalists for an 18-headline pick on 11/10/2026, and the day failed.
        chunks = -(-len(p) // CHUNK)
        k = max(NOMINATE, -(-2 * min_pool // chunks))
        for c in range(0, len(p), CHUNK):
            chunk = p[c:c + CHUNK]
            try:
                raw, _prov = gen(prompts.shortlist_prompt(chunk, k, required))
                shortlist += [chunk[i] for i in prompts.parse_shortlist(raw, len(chunk))[:k]]
            except (ValueError, llm.NoProvider) as exc:
                # One chunk lost costs that chunk's nominees, not the day's puzzle.
                print(f"{seed}: chunk {c // CHUNK + 1} skipped: {exc}")
                continue
        p = shortlist
        if len(p) < min_pool:
            print(f"{seed}: shortlist too short ({len(p)})")
            return None
    idx = _pick(p, gen, required, picks)
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
        # General fakes draw first on the strange stories nominated and not picked: names
        # from hard news made dull fakes ("Posco Future M launches AI-driven mineral
        # survey", trial 15/10/2026). Trump's leftovers are his other stories, too close.
        lead = [] if required else [x for i, x in enumerate(p) if i not in picked][:OTHERS // 2]
        skip = taken | {x["text"] for x in lead}
        rest = [x for x in others_pool if x["text"] not in skip and not gates.ALLEGATION.search(x["text"])]
        others = lead + random.Random(seed).sample(rest, min(OTHERS - len(lead), len(rest)))
    fakes: dict[int, str] = {}
    notes: dict[int, list[str]] = {}
    todo = list(range(len(rounds)))
    for _ in range(FAKE_TRIES):
        # Only the rounds still failing go back, each with the reasons it failed.
        raw, _prov = gen(prompts.fake_prompt([rounds[t] for t in todo],
                                             {k: notes[t] for k, t in enumerate(todo) if t in notes},
                                             others, required, seed, hard))
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
                fakes[t] = match_case(pool.clean_title(f), [x["text"] for x in rounds[t]])
        # Five fakes with one shape are guessable by the third: send back any that
        # repeats an opening or a connector already used today.
        order = sorted(fakes)
        for k in structure_clash([fakes[t] for t in order], required):
            t = order[k]
            print(f"{seed} round {t + 1} rejected (structure): {fakes.pop(t)}")
            notes[t] = ["same structure as another fake"]
            still.append(t)
        todo = sorted(still)
        if not todo or len(fakes) >= count:
            break
    done = sorted(fakes)[:count]
    if len(done) < count:
        return None
    # Players said they would soon spot a pattern; a model that can is the test.
    for _ in range(JUDGE_TRIES):
        caught = _judged(rounds, fakes, done, gen, seed)
        if not caught:
            break
        spotted = sorted(caught)
        # The judge's own reason goes back with it: the writer fixes the actual tell.
        notes2 = {k: [f"a reader spotted it as the invented one ({caught[t] or 'it read as made up'}); "
                      "fix that, and keep it as matter-of-fact as the real ones"]
                  for k, t in enumerate(spotted)}
        try:
            raw, _prov = gen(prompts.fake_prompt([rounds[t] for t in spotted], notes2,
                                                 others, required, seed, hard))
            got = prompts.parse_fakes(raw, len(spotted))
        except (ValueError, llm.NoProvider):
            continue
        for t, f in zip(spotted, got):
            if gates.check_fake(f, [x["text"] for x in rounds[t]], day, required):
                continue
            trial = {**fakes, t: match_case(pool.clean_title(f), [x["text"] for x in rounds[t]])}
            # A replacement that clashes with another fake keeps the spotted one.
            if not structure_clash([trial[x] for x in done], required):
                fakes = trial
    out = []
    for n, t in enumerate(done):
        pos = random.Random(f"{seed}:{n}").randrange(4)
        heads = [dict(x) for x in rounds[t]]
        heads.insert(pos, {"text": fakes[t], "source": "", "url": ""})
        out.append({"headlines": heads, "fake": pos})
    return out


def build(date: str, history: dict, gen, recent: list[str] | None = None,
          hard: list[str] | None = None) -> dict:
    """The general rounds (five, so there is a full game without Trump) and one Trump round."""
    modes = tuple(MODES)
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
            # The general rounds leave Trump to his own round, or the same story turns up twice.
            src = pool.build_pool(arts, trump=True) if MODES[name] else \
                [x for x in everyone if "trump" not in pool.words(x["text"])]
            result[name] = make_mode(src, tracked,
                                     f"{date}:{name}", day=day, required=MODES[name],
                                     # Names come from the whole day, not the shortlist's
                                     # leftovers, so a fake need not borrow from its round.
                                     others_pool=everyone if MODES[name] else src,
                                     count=TRUMP_ROUNDS if MODES[name] else prompts.ROUNDS,
                                     recent=recent, hard=hard)
        except llm.NoProvider as exc:
            # A spent quota in one mode must not cost the other its puzzle.
            print(f"{date} {name}: no provider: {exc}")
            result[name] = None
        result["providers"][name] = used["p"]
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=pool.sydney_today())
    ap.add_argument("--local")
    ap.add_argument("--out", default="puzzle.json")
    # Rebuild today's puzzle from scratch, e.g. after a change to the prompts.
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    have = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    # Not committed, like the puzzle: the workflow fetches it from the live site.
    mem_path = out.with_name("memory.json")
    mem = json.loads(mem_path.read_text(encoding="utf-8")) if mem_path.exists() else {}
    # A published puzzle is never changed under someone mid-game, unless forced.
    if have.get("date") == a.date and have.get("rounds") and not a.force:
        print(f"{a.date} already built")
        if a.date not in mem.get("recent", {}):
            mem_path.write_text(json.dumps(remember(mem, a.date, have["rounds"]), ensure_ascii=False),
                                encoding="utf-8")
        return 0
    # Yesterday's puzzle is still on disk: score its fakes before it is replaced.
    if have.get("rounds") and have.get("date") != a.date and not a.local:
        mem = harvest(mem, have, fetch_crowd(have))
    history = pool.load_history(a.date, a.local)
    if history is None:
        print(f"{a.date}: waiting for One Story")
        return 0
    if not a.local:
        history["articles"] = history["articles"] + pool.load_oddities()
    new = build(a.date, history, lambda prompt: llm.generate(prompt),
                recent=recent_texts(mem, a.date),
                hard=[h["text"] for h in mem.get("hard", [])][:HARD_SHOWN])
    if not new.get("normal"):
        print(f"{a.date}: general rounds failed, nothing written")
        return 1
    keep = prompts.ROUNDS - (TRUMP_ROUNDS if new.get("trump") else 0)
    rounds = new["normal"][:keep] + (new.get("trump") or [])
    # A forced rebuild changes the rounds on the same date: the id tells the page that
    # progress saved against the earlier build no longer applies.
    built = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result = {"date": a.date, "id": built, "rounds": rounds, "trump_round": bool(new.get("trump")),
              "providers": new.get("providers", {})}
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    mem_path.write_text(json.dumps(remember(mem, a.date, rounds), ensure_ascii=False), encoding="utf-8")
    print(f"{a.date}: {len(rounds)} rounds, Trump round {'yes' if result['trump_round'] else 'no'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
