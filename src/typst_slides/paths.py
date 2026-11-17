"""Where things are: the engine's files (package data) and the course's.

The commands run from the course directory, Typst's root (lib/, .cache/,
out/). Its sources (lectures/, modules/, common/, widgets/) are there or in
$SLIDES_SRC (relative to the root). A deck <id> is lectures/<id>.typ or
lectures/<id>/<id>.typ (a folder of its own, with what only it uses).
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parent
# lib/, templates/, fonts/, csl/, makefile.mk, VERSION
TYPST = PACKAGE / "typst"
FONTS = TYPST / "fonts"
# the built browser viewer (main.js, main.css, img/…), committed
VIEWER = PACKAGE / "data" / "viewer"


# the help pages (H): docs/*.md, with README.md and CHANGELOG.md (links to
# the repository's own in a checkout)
DOCS = PACKAGE / "docs"


def doc_files() -> dict[str, Path]:
    """{"README.md": path, "docs/x.md": path, …}, as the help names them."""
    out = {"README.md": DOCS / "README.md"}
    if (DOCS / "CHANGELOG.md").exists():
        out["CHANGELOG.md"] = DOCS / "CHANGELOG.md"
    for f in sorted(DOCS.glob("*.md")):
        if f.name not in ("README.md", "CHANGELOG.md"):
            out[f"docs/{f.name}"] = f
    return out


class Course:
    """The course: its root (the working directory) and sources."""

    def __init__(self, root: Path | None = None, src: str | None = None):
        self.root = (root or Path.cwd()).resolve()
        self.src = (self.root / (src or os.environ.get("SLIDES_SRC") or ".")).resolve()
        self.lectures = self.src / "lectures"

    def deck_path(self, deck_id: str) -> Path | None:
        """The deck's file (absolute), or None."""
        for f in (
            self.lectures / deck_id / f"{deck_id}.typ",
            self.lectures / f"{deck_id}.typ",
        ):
            if f.exists():
                return f
        return None

    def deck_file(self, deck_id: str) -> Path:
        """The deck's file, or where it would be."""
        return self.deck_path(deck_id) or self.lectures / f"{deck_id}.typ"

    def deck_ids(self) -> list[str]:
        if not self.lectures.is_dir():
            return []
        out = []
        for e in self.lectures.iterdir():
            if e.is_dir() and (e / f"{e.name}.typ").exists():
                out.append(e.name)
            elif e.is_file() and e.suffix == ".typ":
                out.append(e.stem)
        return sorted(out)

    def rel(self, path: Path | str) -> str:
        return os.path.relpath(Path(path), self.root)

    def rooted(self, path: Path) -> str:
        """A path as Typst sees it: from the root, with a leading /."""
        return "/" + Path(os.path.relpath(path, self.root)).as_posix()

    # the generated data the course's common/course.typ reads (`course-setup`
    # in lib/slides.typ): written empty when missing, so that a deck compiles
    # before the tools ran (and in an editor)
    DATA_FILES = (
        "lib/refs-links.json",
        ".cache/images/manifest.json",
        ".cache/widgets/manifest.json",
    )

    def ensure_data(self) -> None:
        for name in self.DATA_FILES:
            f = self.root / name
            if not f.exists():
                try:
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("{}\n")
                except OSError:
                    pass

    def resolve_deck(self, arg: str) -> Path:
        """A deck given as an id or a .typ file."""
        if arg.endswith(".typ"):
            return (Path.cwd() / arg).resolve()
        return self.deck_file(arg)


@cache
def _load_yaml(path: str, mtime: float):
    with open(path) as f:
        return yaml.safe_load(f) or {}


def schedule(path: str | None = None) -> dict:
    """The course schedule ($SLIDES_SCHEDULE): {lectures: [{id, title, …}]}."""
    path = path or os.environ.get("SLIDES_SCHEDULE")
    if not path:
        return {}
    p = Path(path).resolve()
    try:
        return _load_yaml(str(p), p.stat().st_mtime)
    except OSError:
        return {}


def deck_title(deck_id: str) -> str | None:
    for lec in schedule().get("lectures") or []:
        if lec.get("id") == deck_id:
            return lec.get("title")
    return None
