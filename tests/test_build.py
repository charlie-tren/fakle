import json
import re
from pathlib import Path

import build
import pool

FIX = json.loads((Path(__file__).parent / "fixtures/history.json").read_text(encoding="utf-8"))


def stub(fakes_by_call):
    """A gen() that answers pick prompts with the first 15 indices and fake prompts
    from a queue, so the retry path can be driven exactly."""
    calls = {"fake": 0}

    def gen(prompt):
        if "hardest to believe" in prompt:
            return json.dumps({"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]]}), "stub"
        out = fakes_by_call[calls["fake"]]
        calls["fake"] += 1
        n = len(re.findall(r"^Round \d+:", prompt, re.M))
        return json.dumps({"fakes": out[:n]}), "stub"
    return gen, calls


BASE = "Officials say the new plan will be reviewed again later after more talks this year".split()


def rounds_of(p):
    """The rounds make_mode will form from the stub's first 15 picks."""
    c = [x for x in p if not build.gates.ALLEGATION.search(x["text"])]
    return [c[i:i + 3] for i in range(0, 15, 3)]


def good_fakes(rounds_pool):
    # Lowercase after the first word, so no new names; common words only, so no
    # overlap; sized to its round's mean so the length gate passes. Distinct per round.
    out = []
    for i, r in enumerate(rounds_pool):
        n = round(sum(len(x["text"].split()) for x in r) / len(r))
        out.append(" ".join(BASE[:n - 1] + [f"w{i}"]))
    return out


def test_make_mode_shape_and_cleanliness():
    p = pool.build_pool(FIX["articles"])
    rounds_pool = rounds_of(p)
    gen, _ = stub([good_fakes(rounds_pool)])
    rounds = build.make_mode(p, gen, "2026-10-11:normal")
    assert rounds and len(rounds) == 5
    for r in rounds:
        assert len(r["headlines"]) == 4 and 0 <= r["fake"] < 4
        assert all(h["text"] == pool.clean_title(h["text"]) for h in r["headlines"])


def test_fake_position_is_deterministic():
    p = pool.build_pool(FIX["articles"])
    rounds_pool = rounds_of(p)
    a = build.make_mode(p, stub([good_fakes(rounds_pool)])[0], "s")
    b = build.make_mode(p, stub([good_fakes(rounds_pool)])[0], "s")
    assert [r["fake"] for r in a] == [r["fake"] for r in b]


def test_failing_round_is_retried_then_mode_dropped():
    p = pool.build_pool(FIX["articles"])
    bad = ["Senator Jane Hargreaves arrested"] * 5
    gen, calls = stub([bad, bad, bad])
    assert build.make_mode(p, gen, "s") is None
    assert calls["fake"] == 3


def test_small_pool_gives_none_without_calling_model():
    gen, calls = stub([])
    assert build.make_mode(pool.build_pool(FIX["articles"])[:10], gen, "s") is None
    assert calls["fake"] == 0


def test_main_skips_when_today_already_built(tmp_path, capsys):
    out = tmp_path / "puzzle.json"
    out.write_text(json.dumps({"date": "2026-10-11", "normal": [{"x": 1}], "trump": [{"x": 1}]}))
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(out)]) == 0
    assert "already built" in capsys.readouterr().out


def test_main_waits_for_one_story(tmp_path, capsys):
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(tmp_path / "p.json")]) == 0
    assert "waiting for One Story" in capsys.readouterr().out
    assert not (tmp_path / "p.json").exists()


def test_build_records_date_and_provider():
    p = [x for x in pool.build_pool(FIX["articles"]) if not build.gates.ALLEGATION.search(x["text"])]
    t = [x for x in pool.build_pool(FIX["articles"], trump=True) if not build.gates.ALLEGATION.search(x["text"])]
    gen, _ = stub([good_fakes(rounds_of(p)),
                   trump_fakes([t[i:i + 3] for i in range(0, 15, 3)])])
    result = build.build("2026-10-11", FIX, gen)
    assert result["date"] == "2026-10-11" and result["providers"]["normal"] == "stub"
    assert result["normal"] is not None


def test_thin_trump_pool_drops_only_trump_mode():
    no_trump = {"articles": [a for a in FIX["articles"] if "trump" not in a["title"].lower()]}
    p = pool.build_pool(no_trump["articles"])
    fakes = good_fakes(rounds_of(p))
    gen, _ = stub([fakes])
    result = build.build("2026-10-11", no_trump, gen)
    assert result["normal"] is not None
    assert result["trump"] is None


def test_fake_prompt_carries_unpicked_headlines():
    p = pool.build_pool(FIX["articles"])
    seen = []
    base, _ = stub([good_fakes(rounds_of(p))])

    def gen(prompt):
        seen.append(prompt)
        return base(prompt)
    build.make_mode(p, gen, "s")
    fake_prompts = [x for x in seen if "hardest to believe" not in x]
    first_unpicked = [x for x in p if not build.gates.ALLEGATION.search(x["text"])][15]
    assert fake_prompts and all(first_unpicked["text"] in x for x in fake_prompts)


def test_provider_failure_in_one_mode_keeps_the_other():
    # Once normal mode has had its fakes written, every call after that (Trump mode)
    # fails the way a spent quota does.
    p = pool.build_pool(FIX["articles"])
    base, _ = stub([good_fakes(rounds_of(p))])
    state = {"faked": False}

    def gen(prompt):
        if state["faked"]:
            raise build.llm.NoProvider("quota")
        if "hardest to believe" not in prompt:
            state["faked"] = True
        return base(prompt)
    result = build.build("2026-10-11", FIX, gen)
    assert result["normal"] is not None
    assert result["trump"] is None


def trump_fakes(rounds_pool):
    return ["Trump " + f for f in good_fakes(rounds_pool)]


def test_trump_mode_fake_must_mention_trump():
    p = pool.build_pool(FIX["articles"], trump=True)
    day = [x["text"] for x in pool.build_pool(FIX["articles"])]
    no_trump = good_fakes(rounds_of(p))
    gen, calls = stub([no_trump, no_trump, no_trump])
    assert build.make_mode(p, gen, "s", day=day, required="trump") is None
    assert calls["fake"] == 3


def test_trump_mode_vocabulary_is_the_whole_day():
    # "Officials" appears in the day's non-Trump headlines, so a Trump fake may use it.
    p = pool.build_pool(FIX["articles"], trump=True)
    day = [x["text"] for x in pool.build_pool(FIX["articles"])] + ["Officials say the plan is on hold"]
    gen, _ = stub([trump_fakes(rounds_of(p))])
    assert build.make_mode(p, gen, "s", day=day, required="trump") is not None


def test_allegation_headlines_are_never_picked_as_reals():
    p = [{"text": f"Police arrest man number {i} for odd reasons today", "source": "X", "url": ""} for i in range(10)]
    p += pool.build_pool(FIX["articles"])
    seen = []
    base, _ = stub([good_fakes(rounds_of(p))])

    def gen(prompt):
        seen.append(prompt)
        return base(prompt)
    build.make_mode(p, gen, "s")
    assert "Police arrest" not in seen[0]


def test_main_rebuilds_only_the_missing_mode(tmp_path, monkeypatch):
    (tmp_path / "2026-10-11.json").write_text(json.dumps(FIX), encoding="utf-8")
    kept = {"headlines": [], "fake": 0, "marker": "kept"}
    out = tmp_path / "puzzle.json"
    out.write_text(json.dumps({"date": "2026-10-11", "normal": [kept], "trump": None,
                               "providers": {"normal": "gemini", "trump": None}}))
    asked = []

    def fake_build(date, history, gen, modes=("normal", "trump")):
        asked.append(tuple(modes))
        return {"date": date, "normal": None, "trump": [{"headlines": [], "fake": 1}],
                "providers": {"trump": "stub"}}
    monkeypatch.setattr(build, "build", fake_build)
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(out)]) == 0
    got = json.loads(out.read_text())
    assert asked == [("trump",)]
    assert got["normal"] == [kept] and got["trump"] == [{"headlines": [], "fake": 1}]
    assert got["providers"] == {"normal": "gemini", "trump": "stub"}


def test_pick_prompt_is_capped_for_groq_token_limit():
    big = [{"text": f"Odd headline about thing number {i} in a town", "source": "X", "url": ""} for i in range(600)]
    seen = []

    def gen(prompt):
        seen.append(prompt)
        raise build.llm.NoProvider("stop after the pick")
    try:
        build.make_mode(big, gen, "s")
    except build.llm.NoProvider:
        pass
    lines = [l for l in seen[0].splitlines() if l[:1].isdigit()]
    assert len(lines) == build.PICK_CAP
    # same seed, same sample
    seen2 = []
    try:
        build.make_mode(big, lambda pr: (seen2.append(pr), (_ for _ in ()).throw(build.llm.NoProvider("x")))[1], "s")
    except build.llm.NoProvider:
        pass
    assert seen2[0] == seen[0]



def test_same_story_detects_shared_content_words():
    assert build.same_story("Trump says Ukraine needs new president",
                            "Time for Ukraine to get new president, says Trump", "trump")
    assert not build.same_story("Trump lifts sanctions on Russian diesel",
                                "Trump picks new press secretary", "trump")


def test_pick_with_a_same_story_round_is_retried():
    p = [{"text": t, "source": "X", "url": ""} for t in [
        "Ukraine needs a new president, envoy says", "Ukraine president must change, envoy says",
        "Camels win prize at a county fair", "Moroccan king says migration model hit limit",
        "Alberta woman planks for five hours", "China unveils robot to breed wheat",
        "Japanese brewer designs wobbly beer glass", "Polka king shares Oktoberfest memories",
        "Qing ceramics damaged in museum display", "Peru elects mayor named after dictators",
        "Feathers turned into fertiliser by pupils", "Baby dinosaur fossil puzzles scientists",
        "Dolly Parton records a Welsh cover", "Rogue AI agent gives police a tip",
        "Horseback archery thrills two riders", "Ragebait named youth word of the year",
        "Grenade brought to police headquarters"]]
    bad = {"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]]}
    good = {"rounds": [[0, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12], [13, 14, 15]]}
    answers = [bad, good]
    gen = lambda prompt: (json.dumps(answers.pop(0)), "stub")
    assert build._pick(p, gen) == good["rounds"]


def test_pick_keeps_a_same_story_round_rather_than_nothing():
    p = [{"text": f"Ukraine president story number {i}, envoy says", "source": "X", "url": ""} for i in range(20)]
    bad = {"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14]]}
    gen = lambda prompt: (json.dumps(bad), "stub")
    assert build._pick(p, gen) == bad["rounds"]
