"""Browser checks of the viewer against a running dev server (`make
live-test` in a course, or by hand):

    SLIDES_URL=http://localhost:8000 SLIDES_COURSE=<course dir> \\
        uv run --extra browser pytest -m browser tests/browser

SLIDES_URL is a deck served by `typst-slides serve`; SLIDES_COURSE, its
course directory, for the live-update test (a source file is edited, then
restored). Skipped without SLIDES_URL or Playwright.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.browser
URL = os.environ.get("SLIDES_URL")
playwright = pytest.importorskip("playwright.sync_api")
if not URL:
    pytest.skip("SLIDES_URL (a running dev server) is not set", allow_module_level=True)


@pytest.fixture(scope="module")
def page():
    with playwright.sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1200, "height": 675})
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        p = context.new_page()
        p.errors = []  # type: ignore[attr-defined]
        p.on("pageerror", lambda e: p.errors.append(str(e)))  # type: ignore[attr-defined]
        p.goto(URL, wait_until="load")
        p.wait_for_selector(".page > svg .tsel")
        yield p
        browser.close()


def test_loads_without_errors(page):
    assert page.errors == []
    n = page.evaluate(
        "document.querySelectorAll('.reveal .slides section[data-g]').length"
    )
    assert n > 1


def test_text_layer_selection_and_copy(page):
    text = page.evaluate(
        """() => {
        const d = document.querySelector('.present .page > svg .tsel')
            ?? document.querySelector('.page > svg .tsel');
        const r = document.createRange();
        r.selectNodeContents(d);
        const sel = getSelection();
        sel.removeAllRanges();
        sel.addRange(r);
        return sel.toString();
      }"""
    )
    assert text.strip()
    # find-in-page sees it: the text is in the DOM
    assert page.evaluate("document.body.innerText.length") > 0


def test_internal_link(page):
    # go through the deck until a page with an internal link is shown
    link = None
    for _ in range(200):
        page.keyboard.press("n")  # next slide or step
        page.wait_for_timeout(30)
        link = page.evaluate(
            "document.querySelector('section.present[data-g] > .page > svg a[onclick]')?.getAttribute('onclick') ?? null"
        )
        if link:
            break
    assert link and "handleTypstLocation" in link
    target = int(re.search(r"handleTypstLocation\(this, (\d+)", link).group(1))
    before = page.evaluate("location.hash")
    page.locator("section.present[data-g] > .page > svg a[onclick]").first.click(
        force=True
    )
    page.wait_for_timeout(800)
    shown = page.evaluate(
        "[...document.querySelectorAll('section.present[data-g] > .page')].map(p => +p.dataset.page)"
    )
    assert target in shown, (
        f"the link to page {target} moved there ({before} -> {shown})"
    )


def test_help_opens(page):
    page.keyboard.press("Escape")
    page.keyboard.press("h")
    page.keyboard.press("H")
    page.wait_for_selector(".sb-overlay", timeout=5000)
    assert "API index" in page.content() or "typst" in page.content().lower()
    page.keyboard.press("Escape")


def test_live_update(page):
    course = os.environ.get("SLIDES_COURSE")
    if not course:
        pytest.skip("SLIDES_COURSE is not set")
    outline = page.evaluate(
        "JSON.parse(document.getElementById('deck-outline').textContent)"
    )
    files = []

    def walk(n):
        if n.get("src"):
            files.append(n["src"]["file"])
        for c in n.get("children") or []:
            walk(c)

    walk(outline)
    module = next(f for f in files if "/modules/" in f)
    path = Path(course) / module
    original = path.read_text()
    page.evaluate(
        "window.__updates = []; const o = console.log; console.log = (...a) => (window.__updates.push(a.join(' ')), o(...a));"
    )
    try:
        lines = original.split("\n")
        i = next(k for k, line in enumerate(lines) if line.startswith("=== "))
        lines[i] += " (edited)"
        path.write_text("\n".join(lines))
        deadline = time.time() + 30
        while time.time() < deadline:
            logs = page.evaluate("window.__updates")
            if any("[typst] v" in x for x in logs):
                break
            page.wait_for_timeout(200)
        assert any("[typst] v" in x for x in page.evaluate("window.__updates"))
    finally:
        path.write_text(original)
    assert page.errors == []


def test_course_widget_mounts(page):
    found = page.evaluate(
        """() => {
        const w = [...document.querySelectorAll('.widget[data-widget]')]
            .find(w => w.dataset.widget !== 'todo-note' && w.dataset.widget !== 'svg-object');
        if (!w) return null;
        return +w.closest('section[data-g]').querySelector('.page').dataset.page;
      }"""
    )
    if found is None:
        pytest.skip("no course widget in this deck")
    page.evaluate(f"handleTypstLocation(null, {found})")
    page.wait_for_function(
        """() => [...document.querySelectorAll('section.present[data-g] > .widget')]
            .some(w => w.dataset.widget !== 'todo-note' && w.childElementCount > 0)""",
        timeout=15000,
    )
    assert page.errors == []
