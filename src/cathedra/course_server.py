"""The dev server of the whole course (`make serve-course` / `make serve-dev`).

`dev=False` shows what the production site lists (no `dev: true` decks or
practicals), `dev=True` the dev site.

The index page on / (outlines recomputed when a source changed, the open
pages reloaded then, via /_events); each deck on /<id>/, served by its own
dev server (`cathedra serve --socket=<out>/<id>.sock`), started on its
first request and proxied; other files from the static directories, in
order.

When cathedra's own code changes, the server restarts (with the deck servers
it started): a long-running server would otherwise keep serving what the old
code computed (say, links in an older format).
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import aiohttp
from aiohttp import web

from .paths import Course
from .site import deck_ids, index_html, outlines, read_practicals, schedule

PACKAGE = Path(__file__).resolve().parent


def code_mtime() -> float:
    """When cathedra's Python code last changed."""
    return max((f.stat().st_mtime for f in PACKAGE.rglob("*.py")), default=0.0)


def code_ok() -> bool:
    """Whether the (changed) code imports, before restarting on it."""
    r = subprocess.run(
        [sys.executable, "-c", "import cathedra.cli, cathedra.course_server"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(  # noqa: T201
            f"[site] cathedra's code changed but does not import, not restarting:\n{r.stderr}",
            flush=True,
        )
    return r.returncode == 0


class CourseServer:
    def __init__(
        self,
        course: Course,
        statics: list[Path],
        practicals: Path | None,
        sockets: Path,
        dev: bool = False,
    ):
        self.course = course
        self.dev = dev
        self.statics = [s.resolve() for s in statics]
        self.practicals = practicals
        self.sockets = sockets.resolve()
        self.children: list[subprocess.Popen] = []
        self.starting: dict[str, asyncio.Task] = {}
        self.cached: tuple[float, str] | None = None
        self.listeners: set[asyncio.Queue] = set()
        self.code = code_mtime()
        self.restart = False
        self.boot = f"{os.getpid()}-{time.time()}"

    def ids(self) -> list[str]:
        return deck_ids(self.course, schedule(self.course), dev=self.dev)

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
                "cathedra",
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
            ids = deck_ids(self.course, sched, dev=self.dev)
            outs = await asyncio.to_thread(
                outlines, self.course, sched, ids, self.sockets, t
            )
            page = index_html(
                self.course, sched, outs, self.dev, by_id, bundles, live=True
            )
            self.cached = (t, page)
        return web.Response(text=self.cached[1], content_type="text/html")

    async def events(self, request: web.Request) -> web.StreamResponse:
        resp = web.StreamResponse(
            headers={"Content-Type": "text/event-stream", "Cache-Control": "no-cache"}
        )
        await resp.prepare(request)
        # the client reloads when it reconnects to a restarted server
        await resp.write(f"data: boot:{self.boot}\n\n".encode())
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

    async def poll(self, stop: asyncio.Event) -> None:
        """The open index pages reload when the course's sources change; the
        server restarts when cathedra's code does."""
        last = self.newest()
        while True:
            await asyncio.sleep(1)
            code = code_mtime()
            if code > self.code:
                self.code = code
                if await asyncio.to_thread(code_ok):
                    print("[site] cathedra's code changed: restarting", flush=True)  # noqa: T201
                    self.restart = True
                    stop.set()
                    return
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
        for c in self.children:  # gone (and their sockets) before a restart
            try:
                c.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        self.children = []


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
    poller = asyncio.create_task(server.poll(stop))
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
    dev: bool = False,
) -> None:
    server = CourseServer(course, statics, practicals, sockets, dev)
    try:
        asyncio.run(_run(server, port))
    finally:
        server.stop()
    if server.restart:
        # the same command, on the new code (the deck servers start again on
        # their first request)
        os.execv(sys.executable, sys.orig_argv)
