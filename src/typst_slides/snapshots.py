# ruff: noqa: T201
"""Pictures of the React widgets (#interactive) for the printable PDFs.

For every deck, lists its widget slots (the <interactive> metadata of the
printable document), renders each one in headless Chromium at its slot's
size, in the states its `snapshot` / `snapshots` ask for, and writes
.cache/widgets/<deck>.json: {"<slot key>@<state>": "/.cache/widgets/<hash>.png"},
and all of them in .cache/widgets/manifest.json, which the course's
common/course.typ reads (`widget-shots`): the PDF then shows the picture in
the slot (lib/slides.typ, `interactive`).

One browser for all the decks, started only when a picture is missing:
pictures are named by the hash of the slot (id, props, steps, size) and of
the widgets' code, so an unchanged widget is not rendered again. The browser
is Playwright's (`typst-slides[browser]`, then `playwright install
chromium`) or Chrome ($CHROME, or the usual places). Without one, the
manifests stay empty: the PDFs show the widgets' fallbacks.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from aiohttp import web

from .engine import DeckCompiler
from .paths import TYPST, VIEWER, Course
from .widgets import build_widgets, widgets_entry

SCALE = float(os.environ.get("WIDGET_SCALE", 3))  # device pixels per pt
TIMEOUT = int(os.environ.get("WIDGET_TIMEOUT", 30000))  # ms, for async widgets
WEB_ONLY = {"todo-note"}  # the widgets not drawn in print

CHROMES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
]


def sha(s: str | bytes, n: int = 16) -> str:
    return hashlib.sha1(s.encode() if isinstance(s, str) else s).hexdigest()[:n]


def _walk(d: Path, course: bool = False):
    skip = {".cache", "out", "node_modules", ".git", "dist", "slide-app"}
    if not d.is_dir():
        return
    for root, dirs, files in os.walk(d):
        if course:
            dirs[:] = [x for x in dirs if x not in skip and not x.startswith(".")]
        for f in files:
            if course and f.startswith("."):
                continue
            yield Path(root) / f


def _sources_hash(course: Course, decks: list[Path]) -> str:
    entries = []
    for f in [
        *_walk(course.src, True),
        *_walk(TYPST / "lib"),
        *_walk(TYPST / "templates"),
        *_walk(VIEWER),
    ]:
        try:
            s = f.stat()
        except OSError:
            continue
        entries.append(f"{f}:{s.st_size}:{s.st_mtime}")
    return sha("\n".join(sorted(entries)) + ",".join(map(str, decks)))


def _slots(course: Course, deck: Path) -> list[dict]:
    comp = DeckCompiler(course, deck).compile()
    # an error is reported by the compilation that follows: no pictures here
    found = comp.query("<interactive>") if comp.ok else []
    pictures = {}
    for s in found:
        if not s.get("key") or s.get("id") in WEB_ONLY:
            continue
        for shot in s.get("shots") or []:
            p = {
                **s,
                "state": shot.get("state"),
                "key": f"{s['key']}@{shot.get('tag')}",
            }
            pictures[p["key"]] = p
    return list(pictures.values())


def _find_chrome() -> str | None:
    for c in [
        os.environ.get("CHROME"),
        os.environ.get("PUPPETEER_EXECUTABLE_PATH"),
        *CHROMES,
    ]:
        if c and Path(c).exists():
            return c
    return None


async def _render(page_dir: Path, missing: list[dict], file_of) -> set[str]:
    """Render the missing pictures; the keys that failed."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print(
            "snapshots: needs Playwright (pip install 'typst-slides[browser]'): the PDFs show the widgets' fallbacks"
        )
        return {s["key"] for s in missing}

    app = web.Application()
    app.router.add_static("/", page_dir)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
    failed: set[str] = set()
    try:
        async with async_playwright() as pw:
            chrome = _find_chrome()
            try:
                browser = await pw.chromium.launch(args=["--hide-scrollbars"])
            except Exception:
                if not chrome:
                    print(
                        "snapshots: no Chromium (playwright install chromium) nor Chrome ($CHROME): the PDFs show the widgets' fallbacks"
                    )
                    return {s["key"] for s in missing}
                browser = await pw.chromium.launch(
                    executable_path=chrome, args=["--hide-scrollbars"]
                )
            try:
                failed = await _shoot(
                    browser, f"http://127.0.0.1:{port}/index.html", missing, file_of
                )
            finally:
                await browser.close()
    finally:
        await runner.cleanup()
    print(f"snapshots: {len(missing) - len(failed)} widget picture(s) rendered")
    return failed


async def _shoot(browser, url: str, missing: list[dict], file_of) -> set[str]:
    failed: set[str] = set()
    for s in missing:
        w, h = max(1, round(s["w"])), max(1, round(s["h"]))
        context = await browser.new_context(
            viewport={"width": w, "height": h}, device_scale_factor=SCALE
        )
        page = await context.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
        page.on(
            "console",
            lambda m, errors=errors: m.type == "error" and errors.append(m.text),
        )
        await page.goto(url, wait_until="load")
        await page.wait_for_function("typeof window.renderWidget === 'function'")
        status = await page.evaluate(
            "([s, w, h, t]) => window.renderWidget(s.id, s.props, s.state, s.steps ?? null, w, h, t)",
            [s, w, h, TIMEOUT],
        )
        try:  # what the widget fetched is in
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        except Exception:  # best effort
            pass
        if status == "missing":
            errors.append(f'no widget "{s["id"]}" in widgets/index.ts')
        if status == "timeout":
            print(
                f"snapshots: {s['id']}: onReady not called after {TIMEOUT} ms, taken anyway"
            )
        if errors:
            print(f"snapshots: {s['id']}: {'; '.join(errors)}")
            failed.add(s["key"])
        else:
            await page.screenshot(
                path=str(file_of(s)),
                omit_background=True,
                clip={"x": 0, "y": 0, "width": w, "height": h},
            )
        await context.close()
    return failed


def _bundle(course: Course, page_dir: Path) -> str:
    """The page that draws one widget (snapshot.js with the course's
    widgets.js); the hash of its code."""
    shutil.rmtree(page_dir, ignore_errors=True)
    page_dir.mkdir(parents=True)
    shutil.copy2(VIEWER / "snapshot.js", page_dir / "snapshot.js")
    entry = widgets_entry(course)
    version = build_widgets(course, entry, page_dir) if entry else ""
    (page_dir / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><style>html,body{margin:0;background:transparent}'
        "#slot{position:relative;overflow:hidden}</style>"
        f'<body data-widgets="{version}"><div id="slot"></div>'
        '<script type="module" src="snapshot.js"></script></body>'
    )
    return sha(
        "".join(
            f.name + sha(f.read_bytes())
            for f in sorted(page_dir.iterdir())
            if f.is_file()
        )
    )


def snapshots(course: Course, decks: list[Path]) -> None:
    cache = course.root / ".cache" / "widgets"
    cache.mkdir(parents=True, exist_ok=True)
    state_file = cache / "state.json"
    sources = _sources_hash(course, decks)
    try:
        saved = json.loads(state_file.read_text())
    except (OSError, ValueError):
        saved = None
    reuse = bool(saved and saved.get("sources") == sources)
    slots: dict[str, list] = dict(saved["slots"]) if reuse else {}
    if not reuse:
        with ThreadPoolExecutor(min(8, os.cpu_count() or 4)) as ex:
            for d, found in zip(decks, ex.map(lambda d: _slots(course, d), decks)):
                slots[str(d)] = found
    manifest = lambda d: cache / f"{Path(d).stem}.json"  # noqa: E731
    if not any(slots.values()):
        for d in decks:
            manifest(d).write_text("{}")
        _write_merged(cache, {})
        state_file.write_text(
            json.dumps({"sources": sources, "slots": list(slots.items())})
        )
        return
    page_dir = cache / "page"
    code = (
        saved.get("codeHash")
        if reuse and saved.get("codeHash") and (page_dir / "index.html").exists()
        else _bundle(course, page_dir)
    )
    state_file.write_text(
        json.dumps({"sources": sources, "slots": list(slots.items()), "codeHash": code})
    )

    def file_of(s: dict) -> Path:
        key = s["key"]
        return cache / f"{sha(f'{code}|{key}|{SCALE:g}')}.png"

    missing = list(
        {
            str(file_of(s)): s
            for lst in slots.values()
            for s in lst
            if not file_of(s).exists()
        }.values()
    )
    failed: set[str] = set()
    if missing:
        if not (page_dir / "index.html").exists():
            _bundle(course, page_dir)
        failed = asyncio.run(_render(page_dir, missing, file_of))
    merged: dict[str, str] = {}
    for d, lst in slots.items():
        m = {s["key"]: course.rooted(file_of(s)) for s in lst if s["key"] not in failed}
        manifest(d).write_text(json.dumps(m, indent=1))
        merged.update(m)
    _write_merged(cache, merged)


def _write_merged(cache: Path, merged: dict[str, str]) -> None:
    """.cache/widgets/manifest.json: the pictures of every deck (the slot
    keys do not depend on the deck: those of decks not built this time stay
    while their picture is there), rewritten only when it changes."""
    f = cache / "manifest.json"
    try:
        old = json.loads(f.read_text())
    except (OSError, ValueError):
        old = {}
    root = cache.parent.parent
    kept = {k: v for k, v in old.items() if (root / v.lstrip("/")).exists()}
    merged = {**kept, **merged}
    text = json.dumps(dict(sorted(merged.items())), indent=1)
    if not f.exists() or f.read_text() != text:
        f.write_text(text)
