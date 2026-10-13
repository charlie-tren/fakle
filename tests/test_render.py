import http.server
import json
import shutil
import socketserver
import threading
from functools import partial
from pathlib import Path

import pytest

pw = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[1]
# The fixture is dated 2026-10-11 and the page refuses a stale puzzle, so every
# context runs on that morning's clock. Without this the suite goes red tomorrow.
NOW = "2026-10-11T09:00:00+11:00"


def context(browser, **kw):
    ctx = browser.new_context(**kw)
    # The page must not depend on a third-party font server, and nor may its tests.
    ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    ctx.route("**/fonts.gstatic.com/**", lambda r: r.abort())
    ctx.add_init_script("""(() => { const T = new Date('%s').getTime(); const D = Date;
      class F extends D { constructor(...a) { super(...(a.length ? a : [T])); } static now() { return T; } }
      window.Date = F; })()""" % NOW)
    return ctx


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp("site")
    for f in ("index.html", "app.js", "style.css"):
        shutil.copy(ROOT / f, d / f)
    shutil.copy(ROOT / "tests/fixtures/puzzle.json", d / "puzzle.json")
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), partial(Quiet, directory=str(d)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def page_at(browser, url, width=1280):
    ctx = context(browser, viewport={"width": width, "height": 900})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    enter(pg)
    return pg, errors


def enter(pg):
    """Through the start screen, if it is showing, into the game."""
    pg.wait_for_selector("#play:visible, .headline, #end:not([hidden]), #none:not([hidden])")
    if pg.locator("#play").is_visible():
        pg.locator("#play").click()
    pg.wait_for_selector(".headline")


def play_all(pg):
    for _ in range(5):
        pg.locator(".headline").first.click()
        pg.locator("#next").click()


def test_draws_without_errors_and_no_sideways_scroll(site, browser):
    for w in (1280, 390):
        pg, errors = page_at(browser, site, w)
        assert errors == []
        assert pg.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        assert pg.locator(".headline").count() == 4


def test_reveal_marks_fake_and_links_reals(site, browser):
    pg, _ = page_at(browser, site)
    pg.locator(".headline").first.click()
    assert pg.locator(".headline.is-fake").count() == 1
    assert pg.locator(".headline a[href]").count() == 3


def test_share_text_has_no_headline_words(site, browser):
    pg, _ = page_at(browser, site)
    play_all(pg)
    share = pg.locator("#share-text").text_content()
    puzzle = json.loads((ROOT / "tests/fixtures/puzzle.json").read_text(encoding="utf-8"))
    words = {w.lower() for r in puzzle["rounds"] for h in r["headlines"] for w in h["text"].split() if len(w) > 4}
    assert share.startswith("Fakle")
    assert not any(w in share.lower() for w in words)


def test_progress_resumes_same_day_and_resets_next_day(site, browser):
    pg, _ = page_at(browser, site)
    pg.locator(".headline").first.click()
    pg.reload()
    enter(pg)
    assert pg.evaluate("window.fakleState.picks.length") == 1
    pg.evaluate("""localStorage.setItem('fakle:progress',
        JSON.stringify({date:'2026-10-10', picks:[0,0,0,0,0]}))""")
    pg.reload()
    enter(pg)
    assert pg.evaluate("window.fakleState.picks.length") == 0


def test_plays_when_storage_throws(site, browser):
    ctx = context(browser)
    ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site)
    enter(pg)
    play_all(pg)
    assert errors == []
    assert pg.locator("#share").is_visible()


def test_missing_mode_says_so(site, browser):
    ctx = context(browser)
    pg = ctx.new_page()
    pg.route("**/puzzle.json", lambda r: r.fulfill(json={"date": "2026-10-11", "rounds": None}))
    pg.goto(site)
    pg.wait_for_selector("#none", state="visible")


def test_no_dashes_in_copy():
    for f in ("index.html", "app.js", "style.css"):
        t = (ROOT / f).read_text(encoding="utf-8")
        assert chr(0x2013) not in t and chr(0x2014) not in t
        assert "\\u2013" not in t and "\\u2014" not in t


def _with_date(browser, site, puzzle_date, now):
    ctx = browser.new_context()
    ctx.route("**/fonts.googleapis.com/**", lambda r: r.abort())
    pg = ctx.new_page()
    pg.clock.set_fixed_time(now)
    data = json.loads((ROOT / "tests/fixtures/puzzle.json").read_text(encoding="utf-8"))
    data["date"] = puzzle_date
    pg.route("**/puzzle.json", lambda r: r.fulfill(json=data))
    pg.goto(site)
    return pg


def test_stale_puzzle_says_none(site, browser):
    pg = _with_date(browser, site, "2026-10-09", "2026-10-11T09:00:00+11:00")
    pg.wait_for_selector("#none", state="visible")
    assert pg.locator(".headline").count() == 0


def test_yesterdays_puzzle_still_plays_early_morning(site, browser):
    pg = _with_date(browser, site, "2026-10-10", "2026-10-11T07:00:00+11:00")
    enter(pg)


def test_yesterdays_puzzle_retired_by_afternoon(site, browser):
    pg = _with_date(browser, site, "2026-10-10", "2026-10-11T15:00:00+11:00")
    pg.wait_for_selector("#none", state="visible")



def test_focus_moves_to_first_headline_after_next(site, browser):
    pg, _ = page_at(browser, site)
    assert pg.locator(".headline").first.get_attribute("role") == "button"
    pg.locator(".headline").first.click()
    pg.locator("#next").click()
    assert pg.evaluate("document.activeElement.classList.contains('headline')")


def test_countdown_points_at_nine_sydney(site, browser):
    pg, _ = page_at(browser, site)
    play_all(pg)
    assert pg.locator("#countdown").inner_text() == "Next Fakle in 24h 0m"


def _copy_with(browser, site, clipboard_ok, exec_ok):
    ctx = context(browser)
    ctx.add_init_script("""
      Object.defineProperty(navigator, 'clipboard', {value: {writeText: () =>
        %s}});
      document.execCommand = () => %s;""" % (
        "Promise.resolve()" if clipboard_ok else "Promise.reject(new Error('denied'))",
        "true" if exec_ok else "false"))
    pg = ctx.new_page()
    pg.goto(site)
    enter(pg)
    play_all(pg)
    pg.locator("#share").click()
    pg.wait_for_function("document.getElementById('share').textContent !== 'Copy result'")
    return pg.locator("#share").inner_text()


def test_copy_falls_back_when_clipboard_denied(site, browser):
    assert _copy_with(browser, site, False, True) == "Copied"


def test_copy_says_so_when_it_cannot(site, browser):
    assert _copy_with(browser, site, False, False) == "Copy failed"


def test_letter_row_spells_the_name_and_tracks_picks(site, browser):
    pg, _ = page_at(browser, site)
    letters = pg.locator(".bar .letters li")
    assert letters.all_inner_texts() == ["F", "A", "K", "L", "E"]
    assert "now" in letters.nth(0).get_attribute("class")
    puzzle = json.loads((ROOT / "tests/fixtures/puzzle.json").read_text(encoding="utf-8"))
    fake = puzzle["rounds"][0]["fake"]
    pg.locator(".headline").nth(fake).click()
    assert "right" in letters.nth(0).get_attribute("class")
    pg.locator("#next").click()
    pg.locator(".headline").nth((puzzle["rounds"][1]["fake"] + 1) % 4).click()
    assert "wrong" in letters.nth(1).get_attribute("class")


def test_end_screen_shows_the_big_letter_row(site, browser):
    pg, _ = page_at(browser, site)
    play_all(pg)
    big = pg.locator("#end .letters li")
    assert big.count() == 5
    assert big.first.bounding_box()["width"] > 48
    assert all(("right" in c or "wrong" in c) for c in [big.nth(i).get_attribute("class") for i in range(5)])


def test_no_theme_toggle():
    assert 'id="theme"' not in (ROOT / "index.html").read_text(encoding="utf-8")



def test_font_stylesheet_does_not_block_render():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    link = [l for l in html.splitlines() if "fonts.googleapis.com/css2" in l][0]
    assert 'media="print"' in link and "onload=" in link


def test_share_uses_green_and_red_circles(site, browser):
    pg, _ = page_at(browser, site)
    play_all(pg)
    grid = pg.locator("#share-text").text_content().splitlines()[1]
    assert len(grid) == 5 and set(grid) <= {chr(0x1F7E2), chr(0x1F534)}


def test_own_icon_set():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for f in ("favicon.svg", "favicon.ico", "favicon-192.png", "apple-touch-icon.png"):
        assert f'href="{f}"' in html and (ROOT / f).exists()


def test_phone_tap_targets_are_thumb_sized(site, browser):
    pg, _ = page_at(browser, site, 390)
    for sel in (".back",):
        for el in pg.locator(sel).all():
            assert el.bounding_box()["height"] >= 36, sel



def test_one_game_no_mode_toggle(site, browser):
    assert 'class="modes"' not in (ROOT / "index.html").read_text(encoding="utf-8")
    pg, _ = page_at(browser, site + "?mode=trump")
    assert pg.locator(".headline").count() == 4
    puzzle = json.loads((ROOT / "tests/fixtures/puzzle.json").read_text(encoding="utf-8"))
    assert pg.locator(".headline").first.inner_text() == puzzle["rounds"][0]["headlines"][0]["text"]



def _fresh(browser, site):
    ctx = context(browser)
    pg = ctx.new_page()
    pg.goto(site)
    pg.wait_for_selector("#home:not([hidden])")
    return pg


def test_start_screen_comes_first(site, browser):
    pg = _fresh(browser, site)
    assert pg.locator("#play").inner_text() == "Play"
    assert pg.locator("#home .tiles li").all_inner_texts() == ["F", "A", "K", "L", "E"]
    assert pg.locator("#home-date").inner_text() == "Sunday 11 October"
    assert "One is made up" in pg.locator("#home").inner_text()
    assert pg.locator(".headline").count() == 0
    pg.locator("#play").click()
    assert pg.locator(".headline").count() == 4
    assert pg.locator("#home").is_hidden()


def test_start_screen_says_continue_mid_game(site, browser):
    pg = _fresh(browser, site)
    pg.locator("#play").click()
    pg.locator(".headline").first.click()
    pg.reload()
    pg.wait_for_selector("#home:not([hidden])")
    assert pg.locator("#play").inner_text() == "Continue"
    pg.locator("#play").click()
    assert pg.evaluate("window.fakleState.picks.length") == 1
    assert pg.locator(".headline.is-fake").count() == 0     # round 2, not yet answered


def test_played_today_opens_on_the_result_and_can_review(site, browser):
    pg = _fresh(browser, site)
    pg.locator("#play").click()
    play_all(pg)
    pg.reload()
    pg.wait_for_selector("#end:not([hidden])")
    assert pg.locator("#home").is_hidden()
    pg.locator("#review").click()
    assert pg.locator(".headline.is-fake").count() == 1     # round 1, revealed
    for _ in range(5):
        pg.locator("#next").click()
    assert pg.locator("#end").is_visible()



def test_headlines_set_in_a_news_serif(site, browser):
    pg, _ = page_at(browser, site)
    family = pg.evaluate("getComputedStyle(document.querySelector('.headline')).fontFamily")
    assert "Libre Caslon Condensed" in family
    assert "Libre+Caslon+Condensed" in (ROOT / "index.html").read_text(encoding="utf-8")


def test_canonical_url():
    assert '<link rel="canonical" href="https://charlietrenorden.com/fakle/">' in (ROOT / "index.html").read_text(encoding="utf-8")



def test_last_round_is_labelled_as_the_trump_round(site, browser):
    pg, _ = page_at(browser, site)
    assert pg.locator("#round-label").is_hidden()
    for i in range(4):
        pg.locator(".headline").first.click()
        pg.locator("#next").click()
    assert pg.locator("#round-label").is_visible()
    assert pg.locator("#round-label").text_content() == "Trump round"


def test_no_label_when_the_day_has_no_trump_round(site, browser):
    ctx = context(browser)
    pg = ctx.new_page()
    data = json.loads((ROOT / "tests/fixtures/puzzle.json").read_text(encoding="utf-8"))
    data["trump_round"] = False
    pg.route("**/puzzle.json", lambda r: r.fulfill(json=data))
    pg.goto(site)
    enter(pg)
    for i in range(4):
        pg.locator(".headline").first.click()
        pg.locator("#next").click()
    assert pg.locator("#round-label").is_hidden()



def test_progress_from_an_earlier_build_of_the_same_day_is_dropped(site, browser):
    pg, _ = page_at(browser, site)
    pg.evaluate("""localStorage.setItem('fakle:progress',
        JSON.stringify({date:'2026-10-11', id:'an-earlier-build', picks:[0,0]}))""")
    pg.reload()
    enter(pg)
    assert pg.evaluate("window.fakleState.picks.length") == 0
