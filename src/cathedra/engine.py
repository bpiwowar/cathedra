"""The Typst backend, behind a narrow interface.

Everything typst-specific goes through here (the native module,
cathedra._native, built from rust/):

- `DeckCompiler(course, deck, inputs).compile()` -> `Compilation`: its
  diagnostics (formatted as the typst CLI does), the files it read, and, when
  it succeeded, the document;
- `Compilation.pages()` -> `Pages`: the web pages of the deck, following the
  contract of docs/viewer.md ("SVG pages"): per-page SVG files, a shared
  glyph file, image files;
- `Compilation.pdf()`, `Compilation.query(selector, field)`,
  `Compilation.labels([...])` (several label queries in one pass).

Compilers are warm: compiling again after an edit only redoes what changed
(typst's memoization is shared by every compiler of the process). The GIL is
released while compiling, so decks compile in parallel in threads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import _native
from .paths import FONTS, Course

TYPST_VERSION = _native.typst_version()


@dataclass
class Diagnostic:
    severity: str  # "error" | "warning"
    message: str
    text: str  # as the typst CLI prints it


@dataclass
class Pages:
    """The web pages of a document (docs/viewer.md, "SVG pages")."""

    width: float
    height: float
    # [(hash, svg)] in page order: svg/<hash>.svg
    pages: list[tuple[str, str]]
    # (file name, content) of the shared glyph definitions
    glyphs: tuple[str, str]
    # file name -> bytes (svg/img-<hash>.<ext>)
    images: dict[str, bytes]


def _clean(text: str) -> str:
    # Touying's warnings go through a font-family trick (uniwarn) that leaves
    # backspaces in the message
    return text.replace("\x08", "")


@dataclass
class Compilation:
    diagnostics: list[Diagnostic]
    dependencies: list[Path]
    _doc: object | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self._doc is not None

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "warning"]

    @property
    def num_pages(self) -> int:
        return self._doc.num_pages if self._doc else 0  # type: ignore[attr-defined]

    def pages(self) -> Pages:
        p = self._doc.pages()  # type: ignore[attr-defined]
        return Pages(
            p["width"], p["height"], p["pages"], tuple(p["glyphs"]), p["images"]
        )

    def pdf(self, tagged: bool = True) -> bytes:
        return self._doc.pdf(tagged)  # type: ignore[attr-defined]

    def png(self, ppi: float = 144, pages: list[int] | None = None) -> list[bytes]:
        """PNG pictures of the pages (all, or the 0-based `pages`)."""
        return self._doc.png(ppi, pages)  # type: ignore[attr-defined]

    def query(self, selector: str, field: str | None = "value") -> list:
        """The values (`field`) of the elements matching `selector`."""
        return json.loads(self._doc.query(selector, field))  # type: ignore[attr-defined]

    def labels(self, labels: list[str]) -> dict[str, list]:
        """The values of several labels' metadata, in one pass: {label: [...]}."""
        out: dict[str, list] = {label: [] for label in labels}
        if not labels:
            return out
        selector = "selector(" + ").or(".join(f"<{lab}>" for lab in labels) + ")"
        for el in json.loads(self._doc.query(selector, None)):  # type: ignore[attr-defined]
            label = (el.get("label") or "").strip("<>")
            if label in out:
                out[label].append(el.get("value"))
        return out


class DeckCompiler:
    """A warm compiler for one deck (`deck`: its .typ file)."""

    def __init__(
        self,
        course: Course,
        deck: Path,
        inputs: dict[str, str] | None = None,
        plain: bool = False,
    ):
        """`plain`: as plain `typst compile` would, without the course's
        generated files (no `cathedra` input: lib/slides.typ `generated`)."""
        self.course = course
        self.deck = Path(deck)
        self.inputs = dict(inputs or {})
        if not plain:
            self.inputs.setdefault("cathedra", "1")
            course.ensure_data()
        self._compiler = _native.Compiler(
            str(course.root), str(self.deck), [str(FONTS)], self.inputs
        )

    def compile(self) -> Compilation:
        r = self._compiler.compile()
        diags = [
            Diagnostic(d.severity, _clean(d.message), _clean(d.text))
            for d in r.diagnostics
        ]
        return Compilation(diags, [Path(p) for p in r.dependencies], r.document)


def evict_cache(max_age: int = 10) -> None:
    """Drop the memoized results unused for `max_age` compilations."""
    _native.evict_cache(max_age)
