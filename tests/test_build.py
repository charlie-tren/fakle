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
        if "most absurd" in prompt:
            return json.dumps({"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14], [15, 16, 17]]}), "stub"
        out = fakes_by_call[calls["fake"]]
        calls["fake"] += 1
        n = len(re.findall(r"^Round \d+:", prompt, re.M))
        return json.dumps({"fakes": out[:n]}), "stub"
    return gen, calls


# No connectors ("after", "amid") and a numbered opening per round, so the stub's fakes
# pass the cross-fake structure check the way distinct real fakes would.
BASE = "officials say the new plan will be reviewed again later with more talks this year".split()


def rounds_of(p):
    """The rounds make_mode will form from the stub's first 15 picks."""
    c = [x for x in p if not build.gates.ALLEGATION.search(x["text"])]
    return [c[i:i + 3] for i in range(0, 18, 3)]


def good_fakes(rounds_pool):
    # Lowercase after the first word, so no new names; common words only, so no
    # overlap; sized to its round's mean so the length gate passes. Distinct per round.
    out = []
    for i, r in enumerate(rounds_pool):
        n = round(sum(len(x["text"].split()) for x in r) / len(r))
        out.append(" ".join([str(i + 2)] + BASE[:n - 2] + [f"w{i}"]))
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
    bad = ["Senator Jane Hargreaves arrested"] * 6
    gen, calls = stub([bad] * 5)
    assert build.make_mode(p, gen, "s") is None
    assert calls["fake"] == 5


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
                   trump_fakes([t[i:i + 3] for i in range(0, 18, 3)])])
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
    fake_prompts = [x for x in seen if "most absurd" not in x]
    first_unpicked = [x for x in p if not build.gates.ALLEGATION.search(x["text"])][18]
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
        if "most absurd" not in prompt:
            state["faked"] = True
        return base(prompt)
    result = build.build("2026-10-11", FIX, gen)
    assert result["normal"] is not None
    assert result["trump"] is None


def trump_pool():
    """The fixture's real Trump headlines, topped up to a full pick with Trump-led
    versions of the day's other headlines (every word already in the day's vocabulary)."""
    t = pool.build_pool(FIX["articles"], trump=True)
    extra = [{"text": "Trump " + x["text"][0].lower() + x["text"][1:], "source": "X", "url": ""}
             for x in pool.build_pool(FIX["articles"]) if "trump" not in pool.words(x["text"])]
    return t + extra[:30]


def trump_fakes(rounds_pool):
    return ["Trump " + f for f in good_fakes(rounds_pool)]


def test_trump_mode_fake_must_mention_trump():
    p = trump_pool()
    day = [x["text"] for x in pool.build_pool(FIX["articles"])]
    no_trump = good_fakes(rounds_of(p))
    gen, calls = stub([no_trump] * 5)
    assert build.make_mode(p, gen, "s", day=day, required="trump") is None
    assert calls["fake"] == 5


def test_trump_mode_vocabulary_is_the_whole_day():
    # "Officials" appears in the day's non-Trump headlines, so a Trump fake may use it.
    p = trump_pool()
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
        "Grenade brought to police headquarters", "Penguin escapes zoo by riding a delivery van"]]
    bad = {"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14], [15, 16, 17]]}
    good = {"rounds": [[0, 2, 3], [4, 5, 6], [7, 8, 9], [10, 11, 12], [13, 14, 15], [16, 17, 1]]}
    answers = [bad, good]
    gen = lambda prompt: (json.dumps(answers.pop(0)), "stub")
    assert build._pick(p, gen) == good["rounds"]


def test_pick_keeps_a_same_story_round_rather_than_nothing():
    p = [{"text": f"Ukraine president story number {i}, envoy says", "source": "X", "url": ""} for i in range(20)]
    bad = {"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14], [15, 16, 17]]}
    gen = lambda prompt: (json.dumps(bad), "stub")
    assert build._pick(p, gen) == bad["rounds"]


def test_dropped_mode_says_why(capsys):
    p = pool.build_pool(FIX["articles"])
    bad = ["Senator Jane Hargreaves arrested"] * 6
    gen, _ = stub([bad] * 5)
    assert build.make_mode(p, gen, "s") is None
    out = capsys.readouterr().out
    assert "allegation" in out and "new name" in out and "Hargreaves" in out


def test_trump_fake_writer_sees_names_from_the_whole_day():
    t = trump_pool()
    everyone = pool.build_pool(FIX["articles"])
    non_trump = [x["text"] for x in everyone if "trump" not in pool.words(x["text"])]
    seen = []
    base, _ = stub([trump_fakes(rounds_of(t))])

    def gen(prompt):
        seen.append(prompt)
        return base(prompt)
    build.make_mode(t, gen, "s", day=[x["text"] for x in everyone], required="trump", others_pool=everyone)
    fake_prompt = [x for x in seen if "most absurd" not in x][0]
    assert any(h in fake_prompt for h in non_trump)


def test_five_fake_attempts():
    assert build.FAKE_TRIES == 5



def test_structure_clash_flags_repeated_openings_and_connectors():
    fakes = ["Trump announces new plan for farms amid trade talks",
             "Trump announces deal with China amid tariff fight",
             "Dubai police launch robot traffic wardens",
             "Mayor bans leaf blowers after noise complaints"]
    assert build.structure_clash(fakes) == {1}


def test_structure_clash_ignores_the_required_word():
    fakes = ["Trump says he will build a moon base",
             "Trump orders gold-plated golf carts for Air Force One"]
    assert build.structure_clash(fakes, required="trump") == set()


def test_force_rebuilds_both_modes(tmp_path, monkeypatch):
    (tmp_path / "2026-10-11.json").write_text(json.dumps(FIX), encoding="utf-8")
    out = tmp_path / "puzzle.json"
    out.write_text(json.dumps({"date": "2026-10-11", "normal": [{"x": 1}], "trump": [{"x": 1}]}))
    asked = []

    def fake_build(date, history, gen, modes=("normal", "trump")):
        asked.append(tuple(modes))
        return {"date": date, "normal": [{"new": 1}], "trump": [{"new": 2}], "providers": {}}
    monkeypatch.setattr(build, "build", fake_build)
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(out), "--force"]) == 0
    assert asked == [("normal", "trump")]
    assert json.loads(out.read_text())["normal"] == [{"new": 1}]



def test_boring_headlines_are_dropped_before_sampling_a_big_pool():
    boring = [{"text": f"Shares in company {i} rise after quarterly earnings beat forecasts", "source": "X", "url": ""} for i in range(300)]
    odd = [{"text": f"Town elects goat number {i} as honorary mayor for a week", "source": "X", "url": ""} for i in range(20)]
    seen = []

    def gen(prompt):
        seen.append(prompt)
        raise build.llm.NoProvider("stop after the pick")
    try:
        build.make_mode(boring + odd, gen, "s")
    except build.llm.NoProvider:
        pass
    assert "goat number 19" in seen[0] and "Shares in company" not in seen[0]


def test_small_pools_are_not_filtered_for_boredom():
    p = [{"text": f"Trump says shares will rise again in week {i} of trading", "source": "X", "url": ""} for i in range(40)]
    seen = []

    def gen(prompt):
        seen.append(prompt)
        raise build.llm.NoProvider("stop")
    try:
        build.make_mode(p, gen, "s", required="trump")
    except build.llm.NoProvider:
        pass
    assert "week 39" in seen[0]


def test_big_pool_is_shortlisted_in_chunks_and_nothing_is_skipped():
    p = [{"text": f"Village number {i} elects a goat to its council again", "source": "X", "url": ""} for i in range(450)]
    prompts_seen = []

    def gen(prompt):
        prompts_seen.append(prompt)
        if "nominate" in prompt:
            return json.dumps({"picks": [0, 1, 2, 3, 4, 5, 6, 7]}), "stub"
        raise build.llm.NoProvider("stop at the final pick")
    try:
        build.make_mode(p, gen, "s")
    except build.llm.NoProvider:
        pass
    chunks = [x for x in prompts_seen if "nominate" in x]
    assert len(chunks) == 3
    seen = "".join(chunks)
    assert all(f"Village number {i} " in seen for i in range(450))
    final = prompts_seen[-1]
    assert "most absurd" in final and final.count("Village number") == 24


def test_a_stubborn_round_is_replaced_by_the_spare():
    p = pool.build_pool(FIX["articles"])
    fakes = good_fakes(rounds_of(p))
    fakes[2] = "Senator Jane Hargreaves arrested in a hotel lobby"   # round 3 never passes
    gen, _ = stub([fakes] + [["Senator Jane Hargreaves arrested again"]] * 4)
    rounds = build.make_mode(p, gen, "s")
    assert rounds and len(rounds) == 5
    texts = [h["text"] for r in rounds for h in r["headlines"]]
    assert not any("Hargreaves" in t for t in texts)


def test_a_failed_chunk_is_skipped_not_fatal():
    p = [{"text": f"Village number {i} elects a goat to its council again", "source": "X", "url": ""} for i in range(450)]
    calls = {"n": 0}

    def gen(prompt):
        if "nominate" in prompt:
            calls["n"] += 1
            if calls["n"] == 2:
                raise build.llm.NoProvider("minute limit")
            return json.dumps({"picks": list(range(10))}), "stub"
        return json.dumps({"rounds": [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9, 10, 11], [12, 13, 14], [15, 16, 17]]}), "stub"
    try:
        build.make_mode(p, gen, "s")
    except build.llm.NoProvider:
        raise AssertionError("one failed chunk sank the mode")
    except (IndexError, ValueError):
        pass   # the stub has no fakes to give; reaching the fake stage is the point
