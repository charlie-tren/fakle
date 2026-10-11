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
    pg.wait_for_selector(".headline")
    return pg, errors


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
    words = {w.lower() for r in puzzle["normal"] for h in r["headlines"] for w in h["text"].split() if len(w) > 4}
    assert share.startswith("Fakle")
    assert not any(w in share.lower() for w in words)


def test_trump_mode_has_own_progress(site, browser):
    pg, _ = page_at(browser, site)
    pg.locator(".headline").first.click()
    pg.goto(site + "?mode=trump")
    pg.wait_for_selector(".headline")
    assert pg.evaluate("window.fakleState.mode") == "trump"
    assert pg.evaluate("window.fakleState.picks.length") == 0


def test_progress_resumes_same_day_and_resets_next_day(site, browser):
    pg, _ = page_at(browser, site)
    pg.locator(".headline").first.click()
    pg.reload()
    pg.wait_for_selector(".headline")
    assert pg.evaluate("window.fakleState.picks.length") == 1
    pg.evaluate("""localStorage.setItem('fakle:normal:progress',
        JSON.stringify({date:'2026-10-10', picks:[0,0,0,0,0]}))""")
    pg.reload()
    pg.wait_for_selector(".headline")
    assert pg.evaluate("window.fakleState.picks.length") == 0


def test_plays_when_storage_throws(site, browser):
    ctx = context(browser)
    ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site)
    pg.wait_for_selector(".headline")
    play_all(pg)
    assert errors == []
    assert pg.locator("#share").is_visible()


def test_missing_mode_says_so(site, browser):
    ctx = context(browser)
    pg = ctx.new_page()
    pg.route("**/puzzle.json", lambda r: r.fulfill(json={"date": "2026-10-11", "normal": None, "trump": None}))
    pg.goto(site)
    pg.wait_for_selector("#none", state="visible")


def test_no_dashes_in_copy():
    for f in ("index.html", "app.js", "style.css"):
        t = (ROOT / f).read_text(encoding="utf-8")
        assert chr(0x2013) not in t and chr(0x2014) not in t
        assert "\\u2013" not in t and "\\u2014" not in t


def _with_date(browser, site, puzzle_date, now):
    ctx = browser.new_context()
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
    pg.wait_for_selector(".headline")


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
    pg.wait_for_selector(".headline")
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
    fake = puzzle["normal"][0]["fake"]
    pg.locator(".headline").nth(fake).click()
    assert "right" in letters.nth(0).get_attribute("class")
    pg.locator("#next").click()
    pg.locator(".headline").nth((puzzle["normal"][1]["fake"] + 1) % 4).click()
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
