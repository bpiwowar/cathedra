# ruff: noqa: T201
"""Media files of a Typst course that no .typ file references.

    python -m typst_slides.unused_media [--clean] [--root <dir>]
    (or: make unused-media [CLEAN=1])

run from the course directory. Every string literal of every .typ file that
names an existing file counts as a reference — `image("figures/a.png")`,
`read("/common/background.svg", encoding: none)`, `path("…")`, a
`#let img = "x.png"` used later — resolved like Typst does: "/x" from the
course root, "x" from the .typ file. A file that is never named is reported;
--clean deletes them.

Limits: a name assembled at run time (`"fig-" + str(i) + ".png"`) is not seen
— such files show up here, so check the list before --clean — and references
from outside the .typ files (the widgets' TypeScript, web.css) are not looked
at.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .paths import Course

SKIP = {"out", ".cache", "lib", "slide-app", "node_modules", ".git", ".vscode"}
MEDIA = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".mp4",
    ".webm",
    ".mov",
    ".mp3",
    ".ogg",
    ".wav",
}
# Every "…" literal (with escapes) of a .typ file, comments included: a
# commented-out image is still a file one means to keep.
STRING = re.compile(r'"((?:[^"\\\n]|\\.)*)"')


def scan(src: Path) -> tuple[list[str], list[str]]:
    """The media files and the .typ files under `src` (absolute paths)."""
    media: list[str] = []
    typ: list[str] = []

    def walk(d: str) -> None:
        for e in os.scandir(d):
            if e.is_dir(follow_symlinks=False):
                if e.name not in SKIP:
                    walk(e.path)
            elif e.is_file(follow_symlinks=False):
                ext = os.path.splitext(e.name)[1].lower()
                if ext == ".typ":
                    typ.append(e.path)
                elif ext in MEDIA:
                    media.append(e.path)

    walk(str(src))
    return media, typ


def referenced(root: Path, typ: list[str]) -> set[str]:
    """Every path a string literal of the .typ files could name."""
    used = set()
    for file in typ:
        text = Path(file).read_text(encoding="utf-8", errors="replace")
        for m in STRING.finditer(text):
            s = m.group(1)
            if not s:
                continue
            base = str(root) if s.startswith("/") else os.path.dirname(file)
            used.add(os.path.normpath(base + "/" + s))
    return used


def unused_media(course: Course) -> tuple[list[str], int]:
    """The unreferenced media files (absolute, sorted), and the media count."""
    media, typ = scan(course.src)
    used = referenced(course.root, typ)
    return sorted(p for p in media if os.path.normpath(p) not in used), len(media)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="typst-slides unused-media",
        description="Lists the media files (images, videos, audio, PDFs) of the "
        "Typst course in the current directory that no .typ file references.",
    )
    parser.add_argument("--clean", action="store_true", help="delete them")
    parser.add_argument("--root", default=".", help="the course directory")
    args = parser.parse_args(argv)

    course = Course(root=Path(args.root))
    unused, total = unused_media(course)
    size = 0
    for p in unused:
        size += os.path.getsize(p)
        print(course.rel(p))
        if args.clean:
            os.unlink(p)
    if unused:
        done = ", removed" if args.clean else " — --clean removes them"
        print(
            f"\n{len(unused)} of {total} media file(s) unused "
            f"({size / 1024:.0f} KB){done}"
        )
    else:
        print(f"all {total} media file(s) are referenced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
