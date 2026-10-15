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



def test_odd_hyphens_and_spaces_are_normalised():
    t = f"150{chr(0x2011)}million{chr(0x2011)}year{chr(0x00A0)}old fossil found in Alberta"
    assert pool.clean_title(t) == "150-million-year old fossil found in Alberta"



import pytest


@pytest.mark.parametrize("title", [
    "Government unveils plan to fix housing crisis...",
    "Government unveils plan to fix housing crisis" + chr(0x2026),
    "Did a Baby Dinosaur Eat Its Own Kind? Alberta Fossil Reveals Prehistoric Mystery",
    "Why the Fed is still nervous about inflation this year",
    "How a small town in Ohio learned to love its pigeons",
    "What we know about the storm that hit Florida overnight",
    "Opinion: the case for a four-day week in Australia",
])
def test_non_headlines_are_not_usable(title):
    # Charlie, 11/10/2026: no titles ending in an ellipsis, and the dinosaur
    # question "doesn't read like a headline".
    assert not pool.usable(title)


def test_plain_headline_still_usable():
    assert pool.usable("Candidate named Hitler Mussolini elected mayor in Peru")


@pytest.mark.parametrize("raw, shown", [
    ("Common Dreams (US, left)", "Common Dreams"),
    ("BBC News - World", "BBC News"),
    ("The Hindu (International)", "The Hindu"),
    ("Reuters", "Reuters"),
])
def test_outlet_names_are_shown_plainly(raw, shown):
    arts = [{"title": "Moroccan king says migration model hit limit", "source": raw, "url": "https://a/b"}]
    assert pool.build_pool(arts)[0]["source"] == shown



RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Opossum caught on fishing hook rescued from tree</title><link>https://u/1</link>
 <pubDate>Sun, 11 Oct 2026 02:00:00 +0000</pubDate></item>
<item><title>Watch: Kittens tour an aquarium</title><link>https://u/2</link>
 <pubDate>Sun, 11 Oct 2026 03:00:00 +0000</pubDate></item>
<item><title>Sewer workers find class ring missing for decades</title><link>https://u/3</link>
 <pubDate>Wed, 07 Oct 2026 03:00:00 +0000</pubDate></item>
</channel></rss>"""


def test_oddity_feed_keeps_the_last_day_and_drops_video_clips():
    import datetime as dt
    now = dt.datetime(2026, 10, 11, 18, 0, tzinfo=dt.timezone.utc)
    got = pool.parse_feed(RSS.encode(), "UPI", now)
    assert got == [{"title": "Opossum caught on fishing hook rescued from tree",
                    "source": "UPI", "url": "https://u/1"}]


SEARCH_RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Rockland Bakery breaks world record with 41-inch croissant - The Journal News</title>
 <link>https://g/1</link><pubDate>Sun, 11 Oct 2026 02:00:00 +0000</pubDate><source>The Journal News</source></item>
<item><title>Kim Min's Realistic Acting Enhances 'Between Steps' - 조선일보</title>
 <link>https://g/2</link><pubDate>Sun, 11 Oct 2026 02:00:00 +0000</pubDate><source>조선일보</source></item>
</channel></rss>"""


def test_a_search_feed_names_each_outlet_and_keeps_english_titles():
    import datetime as dt
    now = dt.datetime(2026, 10, 11, 18, 0, tzinfo=dt.timezone.utc)
    got = pool.parse_feed(SEARCH_RSS.encode(), None, now)
    assert [g["source"] for g in got] == ["The Journal News"]
    assert pool.clean_title(got[0]["title"]) == "Rockland Bakery breaks world record with 41-inch croissant"


def test_opinion_addressed_to_the_reader_is_not_a_headline():
    assert not pool.usable("You Do Not Need An AI Matchmaker. You Need To Go Outside.")
    assert not pool.usable("Top 5 weirdest things I saw at ACL")


def test_a_broken_oddity_feed_costs_nothing(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(pool.requests, "get", boom)
    assert pool.load_oddities() == []



def test_section_labels_are_not_headlines():
    assert not pool.usable("THE CONVERSATION: How pond algae led to a Nobel and new ways to study the brain")
    assert not pool.usable("From the archive: The songs that all Mexicans magically know")
    assert pool.usable("Busan kids' deep bows for free croissants go viral")
