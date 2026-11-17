# ruff: noqa: T201
"""Move the running deck to the slide that holds a source line.

    python -m cathedra.open_slide <file> <line> [--dir <course dir>]
    (or: make open-slide FILE=<file.typ> LINE=<n>)

Asks the deck's dev servers (`make serve`: http://127.0.0.1:$PORT, default
8000; and every Unix socket out/<deck>.sock of the course, which
`make serve-course` starts) for GET /goto?file=&line=, which moves every open
browser tab on that deck. Used by the VS Code task `install-vscode` writes;
exits 1 when no server has such a slide.
"""

from __future__ import annotations

import argparse
import http.client
import os
import socket
import sys
import urllib.parse
from pathlib import Path

TIMEOUT = 2.0


class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over a Unix socket."""

    def __init__(self, path: str, timeout: float = TIMEOUT):
        super().__init__("127.0.0.1", timeout=timeout)
        self.socket_path = path

    def connect(self) -> None:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(self.socket_path)
        except OSError:
            sock.close()
            raise
        self.sock = sock


def targets(course_dir: Path) -> list[http.client.HTTPConnection]:
    """The dev servers to ask: the TCP port, then the course's sockets."""
    port = int(os.environ.get("PORT") or 8000)
    out: list[http.client.HTTPConnection] = [
        http.client.HTTPConnection("127.0.0.1", port, timeout=TIMEOUT)
    ]
    sockets = course_dir / "out"
    if sockets.is_dir():
        for f in sorted(sockets.iterdir()):
            if f.name.endswith(".sock"):
                out.append(UnixHTTPConnection(str(f)))
    return out


def ask(conn: http.client.HTTPConnection, query: str) -> bool:
    """Whether the server moved its deck (answered 200)."""
    try:
        conn.request("GET", query)
        res = conn.getresponse()
        res.read()
        return res.status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conn.close()


def open_slide(file: str, line: str | int, course_dir: Path | str = ".") -> bool:
    """Tell every running dev server to show the slide at `file`:`line`;
    whether one of them had it."""
    quote = urllib.parse.quote
    query = (
        f"/goto?file={quote(os.path.abspath(file), safe='!~*()' + chr(39))}"
        f"&line={quote(str(line), safe='!~*()' + chr(39))}"
    )
    ok = False
    for conn in targets(Path(course_dir).resolve()):
        ok = ask(conn, query) or ok
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cathedra open-slide",
        description="Move the running deck to the slide that holds a source line.",
    )
    parser.add_argument("file", help="the source file")
    parser.add_argument("line", help="the line in it")
    parser.add_argument("--dir", default=".", help="the course directory (default: .)")
    args = parser.parse_args(argv)
    if not open_slide(args.file, args.line, args.dir):
        print(
            "open-slide: no running deck has a slide at that line "
            "(is `make serve` running?)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
