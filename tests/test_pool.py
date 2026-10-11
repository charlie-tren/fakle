import json
from pathlib import Path

import pool

FIX = json.loads((Path(__file__).parent / "fixtures/history.json").read_text(encoding="utf-8"))


def test_clean_title_strips_outlet_suffix_and_normalises_quotes():
    assert pool.clean_title(f"UN calls plan {chr(0x2018)}abhorrent{chr(0x2019)} - Reuters") == "UN calls plan 'abhorrent'"
    assert pool.clean_title(f"A  {chr(0x201C)}big{chr(0x201D)}  day | BBC News") == 'A "big" day'


def test_usable_rejects_junk():
    assert not pool.usable("- Reuters")
    assert not pool.usable("WNBA Scores & Daily News | WNBA Stats, Scores & News Today")
    assert not pool.usable("Live updates")
    assert pool.usable("UN calls US plans to livestream execution 'abhorrent'")


def test_build_pool_dedupes_near_identical_titles():
    arts = [
        {"title": "Fed holds rates steady in September", "source": "Reuters", "url": "https://a/u1"},
        {"title": "Fed holds rates steady in September, again", "source": "AP", "url": "https://a/u2"},
        {"title": "Moroccan king says migration model hit limit", "source": "AFP", "url": "https://a/u3"},
    ]
    p = pool.build_pool(arts)
    assert len(p) == 2
    assert {x["url"] for x in p} == {"https://a/u1", "https://a/u3"}


def test_trump_pool_only_trump():
    p = pool.build_pool(FIX["articles"], trump=True)
    assert p and all("trump" in x["text"].lower() for x in p)


def test_pool_entries_are_cleaned():
    for x in pool.build_pool(FIX["articles"]):
        assert x["text"] == pool.clean_title(x["text"])
        assert chr(0x2019) not in x["text"] and chr(0x201C) not in x["text"]


def test_load_history_local(tmp_path):
    (tmp_path / "2026-10-11.json").write_text(json.dumps(FIX), encoding="utf-8")
    assert pool.load_history("2026-10-11", local_dir=str(tmp_path))["run_date"] == "2026-10-11"
    assert pool.load_history("2026-10-12", local_dir=str(tmp_path)) is None



def test_non_http_urls_are_dropped():
    arts = [{"title": "Moroccan king says migration model hit limit", "source": "X", "url": "javascript:alert(1)"},
            {"title": "China and EU strike deal to halve hybrid exports", "source": "Y", "url": "https://ok.example/a"}]
    p = pool.build_pool(arts)
    assert [x["url"] for x in p] == ["", "https://ok.example/a"]



def test_trump_mode_matches_the_word_not_a_substring():
    arts = [{"title": "Bluey trumps Peppa in the ratings race again", "source": "X", "url": ""},
            {"title": "Trump says the diesel deal is done for now", "source": "Y", "url": ""}]
    assert [x["text"] for x in pool.build_pool(arts, trump=True)] == ["Trump says the diesel deal is done for now"]
