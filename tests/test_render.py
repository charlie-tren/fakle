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
    ctx = browser.new_context(viewport={"width": width, "height": 900})
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
    share = pg.locator("#share-text").inner_text()
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
    ctx = browser.new_context()
    ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}})")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(site)
    pg.wait_for_selector(".headline")
    play_all(pg)
    assert errors == []
    assert pg.locator("#share-text").is_visible()


def test_missing_mode_says_so(site, browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.route("**/puzzle.json", lambda r: r.fulfill(json={"date": "2026-10-11", "normal": None, "trump": None}))
    pg.goto(site)
    pg.wait_for_selector("#none", state="visible")


def test_no_dashes_in_copy():
    for f in ("index.html", "app.js", "style.css"):
        t = (ROOT / f).read_text(encoding="utf-8")
        assert chr(0x2013) not in t and chr(0x2014) not in t
        assert "\\u2013" not in t and "\\u2014" not in t
