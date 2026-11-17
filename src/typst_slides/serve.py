"""The dev server of one deck: build, serve, rebuild on change, live update.

The browser listens on /events (server-sent events): `hello` (the server's
identity: a page that reconnects to another server reloads), `errors`,
`update` ({version, changed pages, skeleton?, layout, outline}), `goto`
(a slide, from VS Code) and `reload` (new widget code). Other routes:

- POST /annot {page, key, values}: shift-O wrote an annotation's place;
- GET /goto?file=<path>&line=<n>: move the open decks to that slide;
- everything else: the files of out/<deck>/ (no caching).

Files are watched with watchfiles: a change to a .typ file, or to any file
the last compilation read, rebuilds the deck (in a thread: the compiler
releases the GIL); widgets/ rebuilds the widgets; the docs, the help.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import uuid
from pathlib import Path

from aiohttp import web
from watchfiles import awatch

from .build import DeckBuild, warn
from .paths import DOCS, TYPST, Course

IGNORED_DIRS = {".git", "node_modules", ".cache", "out", "dist", "__pycache__", ".venv"}


class DevServer:
    def __init__(self, course: Course, deck: Path, out: Path):
        self.course = course
        self.deck = DeckBuild(course, deck, out, dev=True, serve=True)
        self.boot = str(uuid.uuid4())
        self.clients: set[asyncio.Queue] = set()
        self.last_errors: dict | None = None
        self.lock = asyncio.Lock()

    # ---------------------------------------------------------------- events
    def send(self, msg: dict) -> None:
        for q in list(self.clients):
            q.put_nowait(msg)

    async def events(self, request: web.Request) -> web.StreamResponse:
        # no-transform: a proxy that compresses (serve-course) would
        # otherwise hold the events back
        resp = web.StreamResponse(
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
            }
        )
        await resp.prepare(request)
        q: asyncio.Queue = asyncio.Queue()
        self.clients.add(q)
        try:
            await self._write(resp, {"type": "hello", "boot": self.boot})
            if self.last_errors:
                await self._write(resp, self.last_errors)
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=25)
                except asyncio.TimeoutError:
                    await resp.write(b": keep-alive\n\n")
                    continue
                await self._write(resp, msg)
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self.clients.discard(q)
        return resp

    @staticmethod
    async def _write(resp: web.StreamResponse, msg: dict) -> None:
        await resp.write(f"data: {json.dumps(msg)}\n\n".encode())

    # ---------------------------------------------------------------- routes
    async def annot(self, request: web.Request) -> web.Response:
        try:
            body = await request.json()
            r = self.deck.move_annot(
                body.get("page"), body.get("key"), body.get("values")
            )
        except Exception as e:  # the editor shows the message
            r = {"error": str(e)}
        return web.json_response(r, status=400 if "error" in r else 200)

    async def goto(self, request: web.Request) -> web.Response:
        file = request.query.get("file", "")
        line = int(request.query.get("line", "0") or 0)
        rel = os.path.relpath((self.course.root / file).resolve(), self.course.root)
        g = self.deck.slide_at(rel, line)
        if g is None:
            return web.Response(status=404, text="no slide at that line\n")
        self.send({"type": "goto", "g": g})
        return web.Response(text=f"slide {g}\n")

    async def static(self, request: web.Request) -> web.StreamResponse:
        rel = request.match_info.get("path", "")
        if rel == "" or rel.endswith("/"):
            rel += "index.html"
        f = (self.deck.out / rel).resolve()
        if not f.is_relative_to(self.deck.out) or not f.is_file():
            return web.Response(status=404)
        return web.FileResponse(f, headers={"Cache-Control": "no-store"})

    # --------------------------------------------------------------- rebuild
    async def rebuild(self) -> None:
        async with self.lock:
            try:
                r = await asyncio.to_thread(self.deck.build)
            except Exception as e:  # keep serving
                warn(f"build failed: {e!r}")
                return
        d = self.deck
        if not r.ok:
            self.last_errors = {"type": "errors", "errors": r.errors}
            self.send(self.last_errors)
            return
        if self.last_errors:
            self.last_errors = None
            self.send({"type": "errors", "errors": []})
        if r.changed or r.skeleton or r.layout or r.outline:
            self.send(
                {
                    "type": "update",
                    "version": d.version,
                    "changed": r.changed,
                    "skeleton": r.skeleton,
                    "layout": json.loads(d.layout) if r.layout else None,
                    "outline": json.loads(d.outline_json) if r.outline else None,
                }
            )

    async def watch(self) -> None:
        roots = {self.course.root}
        engine = TYPST.resolve()
        if not engine.is_relative_to(self.course.root):
            roots.add(engine)
        roots.add(DOCS.resolve())
        widgets = (self.course.src / "widgets").resolve()

        def interesting(_change, path: str) -> bool:
            parts = Path(path).parts
            return not any(p in IGNORED_DIRS for p in parts)

        async for changes in awatch(
            *roots, watch_filter=interesting, debounce=50, step=20
        ):
            paths = {Path(p).resolve() for _, p in changes}
            deps = {p.resolve() for p in self.deck.dependencies}
            if any(p.is_relative_to(widgets) for p in paths):
                try:
                    if await asyncio.to_thread(self.deck.write_widgets):
                        self.send({"type": "reload"})
                except RuntimeError as e:
                    warn(f"widgets: {e}")
            if any(
                p.is_relative_to(DOCS.resolve()) or p.suffix == ".md" for p in paths
            ) or any(p.suffix == ".typ" and p.is_relative_to(engine) for p in paths):
                await asyncio.to_thread(self.deck.write_docs)
            if any(p.suffix == ".typ" or p in deps for p in paths):
                await self.rebuild()


async def _serve(server: DevServer, port: int | None, socket: str | None) -> None:
    app = web.Application(client_max_size=4 * 1024**2)
    app.router.add_get("/events", server.events)
    app.router.add_post("/annot", server.annot)
    app.router.add_get("/goto", server.goto)
    app.router.add_get("/{path:.*}", server.static)
    runner = web.AppRunner(app, handle_signals=False, shutdown_timeout=0.5)
    await runner.setup()
    if socket:
        Path(socket).unlink(
            missing_ok=True
        )  # left by a server that did not stop cleanly
        site: web.BaseSite = web.UnixSite(runner, socket)
    else:
        site = web.TCPSite(runner, "localhost", port)
    await site.start()
    where = f"listening on {socket}" if socket else f"http://localhost:{port}"
    print(where, flush=True)  # noqa: T201
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop.set)
    watcher = asyncio.create_task(server.watch())
    try:
        await stop.wait()
    finally:
        watcher.cancel()
        await runner.cleanup()
        if socket:
            Path(socket).unlink(missing_ok=True)


def serve(
    course: Course, deck: Path, out: Path, port: int = 8000, socket: str | None = None
) -> None:
    server = DevServer(course, deck, out)
    server.deck.build_all()
    asyncio.run(_serve(server, port, socket))
