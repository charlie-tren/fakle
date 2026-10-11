import json
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
        n = prompt.count("Round ")
        return json.dumps({"fakes": out[:n]}), "stub"
    return gen, calls


BASE = "Officials say the new plan will be reviewed again later after more talks this year".split()


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
    rounds_pool = [p[i:i + 3] for i in range(0, 15, 3)]
    gen, _ = stub([good_fakes(rounds_pool)])
    rounds = build.make_mode(p, gen, "2026-10-11:normal")
    assert rounds and len(rounds) == 5
    for r in rounds:
        assert len(r["headlines"]) == 4 and 0 <= r["fake"] < 4
        assert all(h["text"] == pool.clean_title(h["text"]) for h in r["headlines"])


def test_fake_position_is_deterministic():
    p = pool.build_pool(FIX["articles"])
    rounds_pool = [p[i:i + 3] for i in range(0, 15, 3)]
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
    out.write_text(json.dumps({"date": "2026-10-11"}))
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(out)]) == 0
    assert "already built" in capsys.readouterr().out


def test_main_waits_for_one_story(tmp_path, capsys):
    assert build.main(["--date", "2026-10-11", "--local", str(tmp_path), "--out", str(tmp_path / "p.json")]) == 0
    assert "waiting for One Story" in capsys.readouterr().out
    assert not (tmp_path / "p.json").exists()


def test_build_records_date_and_provider():
    p = pool.build_pool(FIX["articles"])
    fakes = good_fakes([p[i:i + 3] for i in range(0, 15, 3)])
    gen, _ = stub([fakes, fakes])
    result = build.build("2026-10-11", FIX, gen)
    assert result["date"] == "2026-10-11" and result["provider"] == "stub"
    assert result["normal"] is not None


def test_thin_trump_pool_drops_only_trump_mode():
    no_trump = {"articles": [a for a in FIX["articles"] if "trump" not in a["title"].lower()]}
    p = pool.build_pool(no_trump["articles"])
    fakes = good_fakes([p[i:i + 3] for i in range(0, 15, 3)])
    gen, _ = stub([fakes])
    result = build.build("2026-10-11", no_trump, gen)
    assert result["normal"] is not None
    assert result["trump"] is None
