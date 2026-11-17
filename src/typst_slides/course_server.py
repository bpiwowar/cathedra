"""The dev server of the whole course (`make serve-course`).

The index page on / (outlines recomputed when a source changed, the open
pages reloaded then, via /_events); each deck on /<id>/, served by its own
dev server (`typst-slides serve --socket=<out>/<id>.sock`), started on its
first request and proxied; other files from the static directories, in
order.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path

import aiohttp
from aiohttp import web

from .paths import Course
from .site import deck_ids, index_html, outlines, read_practicals, schedule


class CourseServer:
    def __init__(
        self,
        course: Course,
        statics: list[Path],
        practicals: Path | None,
        sockets: Path,
    ):
        self.course = course
        self.statics = [s.resolve() for s in statics]
        self.practicals = practicals
        self.sockets = sockets.resolve()
        self.children: list[subprocess.Popen] = []
        self.starting: dict[str, asyncio.Task] = {}
        self.cached: tuple[float, str] | None = None
        self.listeners: set[asyncio.Queue] = set()

    def ids(self) -> list[str]:
        return deck_ids(self.course, schedule(self.course), dev=True)

    def socket_of(self, deck: str) -> Path:
        return self.sockets / f"{deck}.sock"

    async def up(self, socket: Path) -> bool:
        if not socket.exists():
            return False
        try:
            conn = aiohttp.UnixConnector(path=str(socket))
            async with aiohttp.ClientSession(connector=conn) as s:
                async with s.get(
                    "http://deck/", timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    return r.status == 200
        except (aiohttp.ClientError, OSError, asyncio.TimeoutError):
            return False

    async def start(self, deck: str) -> None:
        socket = self.socket_of(deck)
        if await self.up(socket):
            return  # already running (started by hand, or another server)
        print(f"[site] starting the dev server of {deck}", flush=True)  # noqa: T201
        self.sockets.mkdir(parents=True, exist_ok=True)
        child = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "typst_slides",
                "serve",
                deck,
                f"--socket={socket}",
                f"--out={self.sockets}",
            ],
            cwd=self.course.root,
            start_new_session=True,  # own group: stopped as a whole
        )
        self.children.append(child)
        for _ in range(600):
            if await self.up(socket):
                return
            if child.poll() is not None:
                raise RuntimeError(f"the dev server of {deck} stopped (see above)")
            await asyncio.sleep(0.2)
        raise RuntimeError(f"the dev server of {deck} did not start")

    def newest(self) -> float:
        t = 0.0
        for d in ("lectures", "modules", "common"):
            for root, _, files in os.walk(self.course.src / d):
                for f in files:
                    if f.endswith(".typ"):
                        t = max(t, os.stat(os.path.join(root, f)).st_mtime)
        for f in (os.environ.get("SLIDES_SCHEDULE"), self.practicals):
            if f and Path(f).exists():
                t = max(t, Path(f).stat().st_mtime)
        return t

    async def index(self, request: web.Request) -> web.Response:
        t = self.newest()
        if not self.cached or t > self.cached[0]:
            sched = schedule(self.course)
            by_id, bundles = read_practicals(self.practicals)
            ids = deck_ids(self.course, sched, dev=True)
            outs = await asyncio.to_thread(
                outlines, self.course, sched, ids, self.sockets, t
            )
            page = index_html(self.course, sched, outs, True, by_id, bundles, live=True)
            self.cached = (t, page)
        return web.Response(text=self.cached[1], content_type="text/html")

    async def events(self, request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
        )
        await resp.prepare(request)
        await resp.write(b": hello\n\n")
        q: asyncio.Queue = asyncio.Queue()
        self.listeners.add(q)
        try:
            while True:
                await q.get()
                await resp.write(b"data: reload\n\n")
        except (ConnectionResetError, asyncio.CancelledError):
            pass
        finally:
            self.listeners.discard(q)
        return resp

    async def poll(self) -> None:
        """The open index pages reload when the course's sources change."""
        last = self.newest()
        while True:
            await asyncio.sleep(1)
            t = self.newest()
            if t > last:
                last = t
                for q in list(self.listeners):
                    q.put_nowait(True)

    async def handle(self, request: web.Request) -> web.StreamResponse:
        path = request.match_info.get("path", "")
        deck = path.split("/", 1)[0]
        if path in ("", "index.html"):
            return await self.index(request)
        if path == "_events":
            return await self.events(request)
        if deck and deck in self.ids():
            if path == deck:
                raise web.HTTPMovedPermanently(f"/{deck}/")
            if (
                deck not in self.starting
                or self.starting[deck].done()
                and self.starting[deck].exception()
            ):
                self.starting[deck] = asyncio.create_task(self.start(deck))
            try:
                await self.starting[deck]
                for _ in range(
                    300
                ):  # a deck server restarting has no socket for a while
                    if self.socket_of(deck).exists():
                        break
                    await asyncio.sleep(0.2)
            except RuntimeError as e:
                self.starting.pop(deck, None)
                return web.Response(status=502, text=f"{e}\n")
            return await self.proxy(
                request, deck, request.path_qs[len(deck) + 1 :] or "/"
            )
        for d in self.statics:
            f = (d / path).resolve()
            if f.is_relative_to(d) and f.is_file():
                return web.FileResponse(f)
        return web.Response(status=404, text="not found\n")

    async def proxy(
        self, request: web.Request, deck: str, path: str
    ) -> web.StreamResponse:
        conn = aiohttp.UnixConnector(path=str(self.socket_of(deck)))
        session = aiohttp.ClientSession(connector=conn, auto_decompress=False)
        try:
            headers = {
                k: v
                for k, v in request.headers.items()
                if k.lower() not in ("host", "content-length")
            }
            body = await request.read() if request.can_read_body else None
            async with session.request(
                request.method,
                f"http://deck{path}",
                headers=headers,
                data=body,
                timeout=aiohttp.ClientTimeout(total=None),
            ) as r:
                resp = web.StreamResponse(status=r.status)
                for k, v in r.headers.items():
                    if k.lower() not in (
                        "content-length",
                        "transfer-encoding",
                        "connection",
                    ):
                        resp.headers[k] = v
                await resp.prepare(request)
                async for chunk in r.content.iter_any():
                    await resp.write(chunk)
                return resp
        except (aiohttp.ClientError, OSError) as e:
            return web.Response(status=502, text=f"{e}\n")
        except (ConnectionResetError, asyncio.CancelledError):
            return web.Response(status=499)
        finally:
            await session.close()

    def stop(self) -> None:
        for c in self.children:
            try:
                os.killpg(c.pid, signal.SIGTERM)
            except OSError:
                pass


async def _run(server: CourseServer, port: int) -> None:
    app = web.Application()
    app.router.add_route("*", "/{path:.*}", server.handle)
    runner = web.AppRunner(app, handle_signals=False, shutdown_timeout=0.5)
    await runner.setup()
    await web.TCPSite(runner, "localhost", port).start()
    print(  # noqa: T201
        f"course: http://localhost:{port}/ ({len(server.ids())} decks, each started on its first request)",
        flush=True,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(sig, stop.set)
    poller = asyncio.create_task(server.poll())
    try:
        await stop.wait()
    finally:
        poller.cancel()
        server.stop()
        await runner.cleanup()


def serve_course(
    course: Course,
    port: int,
    statics: list[Path],
    practicals: Path | None,
    sockets: Path,
) -> None:
    server = CourseServer(course, statics, practicals, sockets)
    try:
        asyncio.run(_run(server, port))
    finally:
        server.stop()
