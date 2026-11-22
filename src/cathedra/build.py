"""A Typst (Touying) deck -> a Reveal.js deck with live React widgets.

`DeckBuild(...).build()` writes out/<deck>/ (run from the course directory):

1. A warm compiler renders the deck (Touying: one page per subslide); an
   edit recompiles incrementally.
2. One query on the compiled document gives the metadata from
   lib/slides.typ: <page-marker> (page -> logical slide), <interactive>
   (widget slots), <morph>, <annot-box>, <details-ref>, the outline's labels.
3. Pages of the same logical slide are stacked in one <section>; every page
   after the first is a Reveal fragment covering the previous one.
4. Widget slots become absolutely positioned divs; the viewer mounts React.
5. Each page is an SVG file (svg/<hash>.svg, see docs/viewer.md); the
   browser mounts the pages around the current slide.
6. Live update (serve.py): each build hashes every page; the browser gets
   {version, changed pages, structure changed?, widget layout} and re-renders
   only those pages, moves widgets, or swaps the <section>s in place.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import outline as outline_mod
from .outline import slug  # noqa: F401 (re-exported)
from .apidoc import api_markdown
from .engine import Compilation, DeckCompiler, Pages
from .paths import VIEWER, Course, deck_title, doc_files
from .widgets import build_widgets, widgets_entry

# the labels the build reads, in one query
LABELS = ["page-marker", "interactive", "morph", "annot-box", "details-ref"]

STYLE = """
    .reveal .slides section[data-g] { padding: 0; height: 100%; }
    .reveal .slides section > .page { position: absolute; inset: 0; background: white; }
    /* Typst steps switch instantly (a step page is a full redraw, and a fade
       would also replay when sections are swapped by a live update) */
    .reveal .slides section > .page.fragment { transition: none; }
    /* a step page covers the previous ones: hide those so that text selection
       and find-in-page only see the visible step */
    .reveal .slides section > .page:has(~ .page.visible) { visibility: hidden; }
    .reveal .slides section > .widget { position: absolute; z-index: 10;
      /* undo Reveal's slide typography: widgets use slide units (1px = 1pt) */
      font-size: 15px; line-height: 1.3; text-align: left; color: #111; }
    .reveal .slides section > .widget svg { max-width: none; max-height: none; margin: 0; }
    /* the pages (svg-pages.ts; docs/viewer.md, "SVG pages") */
    .reveal .slides section > .page > svg.typst-svg { position: absolute; inset: 0; width: 100%; height: 100%;
      display: block; overflow: hidden; }
    svg.typst-svg { fill: none; }
    .typst-svg .tsel, .typst-svg .tsel span { left: 0; position: fixed; width: 100%; height: 100%;
      text-align: justify; text-align-last: justify; white-space: pre; color: transparent; line-height: normal; }
    .typst-svg .tsel::selection, .typst-svg .tsel span::selection { color: transparent; background: #7db9dea0; }
    .typst-svg .pseudo-link { fill: transparent; cursor: pointer; pointer-events: all; }
    /* dev server: a step that overflows (Touying's warning; extras.tsx) */
    /* a thin stripe; hovering it shows the details */
    .reveal .slides section > .page > .overflow-bar { position: absolute; inset: auto 0 0 0; z-index: 5;
      height: 6px; overflow: hidden; padding: 0 10px; cursor: help; color: transparent;
      background: repeating-linear-gradient(-45deg, #c00 0 8px, #a00 8px 16px);
      font: 600 13px/1.3 system-ui, sans-serif; text-align: right; transition: height 0.15s; }
    .reveal .slides section > .page > .overflow-bar:hover { height: auto; padding: 3px 10px; color: #fff; }
    /* work in progress (slide-app's red frame); M hides it (body.todo-masked) */
    .reveal .slides section[data-types~="todo"]::after { content: ""; position: absolute; inset: 0;
      z-index: 4; border: 3px solid #cc0000; pointer-events: none; }
    /* to check (#to-check): an amber frame */
    .reveal .slides section[data-types~="check"]:not([data-types~="todo"])::after { content: "";
      position: absolute; inset: 0; z-index: 4; border: 3px solid #d08a00; pointer-events: none; }
    body.todo-masked .reveal .slides section[data-types~="todo"]::after,
    body.todo-masked .reveal .slides section[data-types~="check"]::after,
    body.todo-masked .reveal .slides .widget[data-widget="todo-note"] { display: none; }
    #flash { position: fixed; left: 50%; bottom: 8vh; z-index: 3000; transform: translateX(-50%);
      padding: 8px 16px; border-radius: 8px; background: rgb(20 20 30 / 0.85); color: #fff;
      font: 15px system-ui, sans-serif; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
    #flash.on { opacity: 1; }
    #typst-errors { position: fixed; inset: auto 0 0 0; z-index: 1000; max-height: 45vh;
      overflow: auto; margin: 0; padding: 12px 16px; background: #2b0b0b; color: #ffd7d7;
      font: 13px/1.4 ui-monospace, monospace; white-space: pre-wrap; }
    #typst-errors:empty { display: none; }
    /* around the slide (letterboxing); a course's web.css can change it */
    html, body, .reveal-viewport { background: var(--backdrop, #000); }
  """


def log(msg: str) -> None:
    print(msg, flush=True)  # noqa: T201


def warn(msg: str) -> None:
    import sys

    print(msg, file=sys.stderr, flush=True)  # noqa: T201


def json_dump(value) -> str:
    """JSON as JavaScript's JSON.stringify writes it (compact, UTF-8)."""
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def overflows(messages: list[str], groups: list[dict]) -> list[dict]:
    """Touying's "detecting slide content overflow at page N" warnings ->
    [{g, page, message}] (g: the slide of that page)."""
    out: list[dict] = []
    for text in messages:
        m = re.search(r"slide content overflow at page (\d+)", text)
        if not m:
            continue
        page = int(m.group(1))
        g = next((i for i, x in enumerate(groups) if page in x["pages"]), -1)
        if g >= 0 and not any(o["page"] == page for o in out):
            msg = re.sub(r"^.*\[touying\] ", "", text, flags=re.S).split("\n")[0]
            out.append({"g": g, "page": page, "message": msg})
    return out


class PageWriter:
    """Writes the pages of successive builds into out/svg/ and svg.json,
    writing only the files that are new and removing the old ones."""

    def __init__(self, out: Path):
        self.out = out
        self.files: set[str] = set()

    def write(self, pages: Pages, size: tuple[float, float] | None) -> None:
        d = self.out / "svg"
        d.mkdir(parents=True, exist_ok=True)
        files: set[str] = set()

        def put(name: str, content: bytes | str) -> None:
            files.add(name)
            f = d / name
            if name not in self.files or not f.exists():
                f.write_bytes(content.encode() if isinstance(content, str) else content)

        for name, data in pages.images.items():
            put(name, data)
        put(*pages.glyphs)
        for h, svg in pages.pages:
            put(f"{h}.svg", svg)
        w, h = size or (pages.width, pages.height)
        manifest = {
            "w": w,
            "h": h,
            "glyphs": f"svg/{pages.glyphs[0]}",
            "pages": [h_ for h_, _ in pages.pages],
        }
        (self.out / "svg.json").write_text(json_dump(manifest))
        for f in d.iterdir():
            if f.name not in files:
                f.unlink(missing_ok=True)
        self.files = files


@dataclass
class BuildResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    changed: list[int] = field(default_factory=list)
    skeleton: bool = False
    layout: bool = False
    outline: bool = False


class DeckBuild:
    """The web deck of `deck` into `<out>/<deck id>/`.

    `dev`: a deck for its author (E / shift-E open the sources, references
    link to Zotero, the help H); `serve`: for the dev server (annotation
    boxes, the outline's absolute paths)."""

    def __init__(
        self,
        course: Course,
        deck: Path,
        out: Path,
        dev: bool = False,
        serve: bool = False,
    ):
        self.course = course
        self.deck = Path(deck).resolve()
        self.id = self.deck.stem
        self.out = Path(out).resolve() / self.id
        self.serve = serve
        self.dev = dev or serve
        inputs = {"target": "web"}
        if self.dev:
            inputs["dev"] = "1"
        self.compiler = DeckCompiler(course, self.deck, inputs)
        self.title = deck_title(self.id)
        self.pages = PageWriter(self.out)
        self.version = 0
        self.hashes: list[str] = []
        self.skeleton = ""
        self.layout = ""
        self.outline_json = ""
        self.outline: dict | None = None
        self.annot_boxes: list = []
        self.group_of_page: dict[int, int] = {}
        self.dependencies: list[Path] = []
        self.widgets_version: str | None = None
        self.last: Compilation | None = None

    # ------------------------------------------------------------ the build
    def build(self) -> BuildResult:
        t0 = time.perf_counter()
        comp = self.compiler.compile()
        self.last = comp
        if comp.dependencies:
            self.dependencies = comp.dependencies
        for d in comp.diagnostics:
            (warn if d.severity == "error" else warn)(d.text)
        if not comp.ok:
            return BuildResult(False, errors=[d.text for d in comp.errors])

        pages = comp.pages()
        hashes = [h for h, _ in pages.pages]
        meta = comp.labels(LABELS)
        structure = comp.query(outline_mod.SELECTOR)
        groups, outline = outline_mod.deck_structure(
            self.course, structure, meta["details-ref"], self.deck, self.title
        )
        outline["overflows"] = overflows([d.text for d in comp.warnings], groups)
        self.outline = outline

        nodes, pos, stack_of = outline_mod.layout(outline, len(groups))
        # the ids deck_structure gave: the section ids and the index's links
        # (#/<id>) come from the same place
        ids = [""] * len(groups)
        for n in nodes:
            ids[n["g"]] = n["id"]
        types_of: dict[int, list[str]] = {}
        # the heading level of the title / section pages (0 title, 1 section,
        # 2 subsection): the viewer drops the sections left empty
        level_of: dict[int, int] = {}
        for n in nodes:
            cur = types_of.setdefault(n["g"], [])
            if n.get("kind") != "slide":
                lv = outline_mod._LEVEL[n["kind"]]
                level_of[n["g"]] = min(lv, level_of.get(n["g"], lv))
            for t in n.get("types") or []:
                if t not in cur:
                    cur.append(t)
        # a content slide with no type is a "main" one (it can be left out
        # too); title and section pages are never left out
        for g, cur in types_of.items():
            if not cur and g not in level_of:
                cur.append("main")
        outline_json = json_dump(
            {**outline, "root": str(self.course.root) if self.dev else None}
        )
        widgets = meta["interactive"]
        if self.serve:
            self.annot_boxes = meta["annot-box"]
            self.group_of_page = {
                p: g for g, x in enumerate(groups) for p in x["pages"]
            }

        skeleton, layout = self._skeleton(
            groups, widgets, ids, types_of, pos, stack_of, level_of
        )
        layout_json = json_dump(layout)

        changed = [
            i + 1
            for i, h in enumerate(hashes)
            if i >= len(self.hashes) or h != self.hashes[i]
        ]
        result = BuildResult(
            True,
            changed=changed,
            skeleton=skeleton != self.skeleton,
            layout=layout_json != self.layout,
            outline=outline_json != self.outline_json,
        )
        if self.version and not (
            changed or result.skeleton or result.layout or result.outline
        ):
            log(f"no visible change ({(time.perf_counter() - t0) * 1000:.0f} ms)")
            return result
        self.version += 1
        self.hashes, self.skeleton, self.layout, self.outline_json = (
            hashes,
            skeleton,
            layout_json,
            outline_json,
        )

        self.out.mkdir(parents=True, exist_ok=True)
        t_svg = time.perf_counter()
        markers = meta["page-marker"]
        marker = markers[0] if markers else None
        size = (
            (marker["width"], marker["height"])
            if marker and marker.get("width")
            else None
        )
        self.pages.write(pages, size)
        svg_ms = (time.perf_counter() - t_svg) * 1000
        # what earlier versions wrote (the PDF the viewer rendered with PDF.js)
        for f in ("deck.pdf", "pdf.worker.mjs", "deck-bg.pdf"):
            (self.out / f).unlink(missing_ok=True)
        self._write_morph(meta["morph"])
        (self.out / "slides.html").write_text(skeleton)
        (self.out / "layout.json").write_text(layout_json)
        (self.out / "outline.json").write_text(outline_json)
        if self.serve:
            (self.out / "annots.json").write_text(json_dump(self.annot_boxes))
        self._write_index(skeleton, layout_json, outline_json)
        n_pages = comp.num_pages
        log(
            f"v{self.version}: {n_pages} pages -> {len(groups)} slides, {len(widgets)} widget(s); "
            + (
                "structure changed"
                if result.skeleton
                else f"changed pages {','.join(map(str, changed)) or '-'}"
            )
            + (", widget layout changed" if result.layout else "")
            + f" ({(time.perf_counter() - t0) * 1000:.0f} ms, SVG pages {svg_ms:.0f} ms)"
        )
        return result

    def _skeleton(self, groups, widgets, ids, types_of, pos, stack_of, level_of):
        """The <section>s: structure = sections, step pages, widget ids and
        step counts; widget geometry and props are kept apart (layout)."""
        layout: dict = {}
        seen: dict[str, int] = {}
        sections = []
        for g, grp in enumerate(groups):
            ps = grp["pages"]
            page_divs = "\n      ".join(
                f'<div class="page{" fragment" if i else ""}" data-page="{p}"></div>'
                for i, p in enumerate(ps)
            )
            drawn: set[str] = set()
            slots = []
            for w in widgets:
                if w.get("page") not in ps:
                    continue
                k = json.dumps(
                    [
                        w.get("id"),
                        w.get("key"),
                        w.get("x"),
                        w.get("y"),
                        w.get("w"),
                        w.get("h"),
                    ]
                )
                if k in drawn:
                    continue
                drawn.add(k)
                seen[w["id"]] = seen.get(w["id"], 0) + 1
                key = f"{w['id']}#{seen[w['id']]}"
                layout[key] = {
                    "x": w.get("x"),
                    "y": w.get("y"),
                    "w": w.get("w"),
                    "h": w.get("h"),
                    "props": w.get("props"),
                }
                slots.append(
                    f'<div class="widget" data-widget="{w["id"]}" data-key="{key}"></div>'
                    + f'<span class="fragment widget-step" data-for="{key}"></span>'
                    * int(w.get("steps") or 0)
                )
            types = types_of.get(g) or []
            t = f' data-types="{" ".join(types)}"' if types else ""
            if g in level_of:
                t += f' data-level="{level_of[g]}"'
            sections.append(
                f'<section id="{ids[g]}" data-g="{g}"{t}>\n      {page_divs}\n      '
                + "\n      ".join(slots)
                + "\n    </section>"
            )
        parts = []
        n = len(groups)
        for g, sec in enumerate(sections):
            in_stack = stack_of[g] is not None
            opening = in_stack and (g == 0 or pos[g - 1]["h"] != pos[g]["h"])
            closing = in_stack and (g == n - 1 or pos[g + 1]["h"] != pos[g]["h"])
            parts.append(
                ("  <section>\n" if opening else "")
                + f"    {sec}"
                + ("\n  </section>" if closing else "")
            )
        return "\n".join(parts), layout

    def _write_morph(self, morph: list) -> None:
        """Morphing figures (lib/morph.typ): per page, the box of each part."""
        boxes: dict = {}
        for m in morph:
            b = boxes.setdefault(str(m["page"]), {}).setdefault(
                m["id"], [m["x"], m["y"], m["x"], m["y"]]
            )
            b[0], b[1] = min(b[0], m["x"]), min(b[1], m["y"])
            b[2], b[3] = max(b[2], m["x"]), max(b[3], m["y"])
        (self.out / "morph.json").write_text(json_dump(boxes))

    def _course_css(self) -> bool:
        src = self.course.root / "web.css"
        if not src.exists():
            return False
        shutil.copyfile(src, self.out / "web.css")
        return True

    def _write_index(self, skeleton: str, layout_json: str, outline_json: str) -> None:
        title = html.escape(self.title or self.id, quote=False)
        css = (
            f'\n  <link rel="stylesheet" href="web.css?v={self.version}">'
            if self._course_css()
            else ""
        )
        widgets = (
            f' data-widgets="{self.widgets_version}"' if self.widgets_version else ""
        )
        # (inside a <script>: no "</script>" from the data)
        layout_script = layout_json.replace("<", "\\u003c")
        outline_script = outline_json.replace("<", "\\u003c")
        (self.out / "index.html").write_text(
            f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <link rel="stylesheet" href="main.css">{
                '''
  <link rel="stylesheet" href="widgets.css">'''
                if (self.out / "widgets.css").exists() and self.widgets_version
                else ""
            }
  <style>{STYLE}</style>{css}
</head>
<body data-version="{self.version}" data-dev="{str(self.serve).lower()}"{widgets}>
  <script type="application/json" id="widget-layout">{layout_script}</script>
  <script type="application/json" id="deck-outline">{outline_script}</script>
  <div class="reveal"><div class="slides">
{skeleton}
  </div></div>
  <pre id="typst-errors"></pre>
  <script type="module" src="main.js"></script>
</body>
</html>
"""
        )

    # ------------------------------------------------------- around the build
    def write_viewer(self) -> None:
        """The viewer's bundle (main.js, main.css, img/…), from the package."""
        if not (VIEWER / "main.js").exists():
            raise SystemExit(
                f"cathedra: the viewer bundle is missing ({VIEWER}): "
                "build it (cd viewer && pnpm install && pnpm run build)"
            )
        copy_tree(VIEWER, self.out, skip={"snapshot.js", "snapshot.css", "shims"})

    def write_widgets(self) -> bool:
        """The course's widgets (widgets/index.ts) -> widgets.js; True when
        they changed."""
        entry = widgets_entry(self.course)
        if not entry:
            self.widgets_version = None
            for f in ("widgets.js", "widgets.css"):
                (self.out / f).unlink(missing_ok=True)
            return False
        version = build_widgets(self.course, entry, self.out)
        changed = version != self.widgets_version
        self.widgets_version = version
        return changed

    def write_docs(self) -> None:
        """The help pages (H), with the API index of the engine and of the
        course's common/*.typ, into docs.json (dev decks only)."""
        if not self.dev:
            (self.out / "docs.json").unlink(missing_ok=True)
            return
        docs = {name: p.read_text() for name, p in doc_files().items() if p.exists()}
        docs["docs/api.md"] = api_markdown(
            course=self.course.src, root=self.course.root
        )
        (self.out / "docs.json").write_text(json_dump(docs))

    def build_all(self) -> bool:
        """A full build: the pages, then the viewer, widgets and docs."""
        self.out.mkdir(parents=True, exist_ok=True)
        try:
            self.write_widgets()
        except RuntimeError as e:
            warn(f"widgets: {e}")
        r = self.build()
        self.write_viewer()
        self.write_docs()
        return r.ok

    # --------------------------------------------------- dev server helpers
    def slide_at(self, file: str, line: int) -> int | None:
        """The slide (group index) whose source holds `file`:`line`."""
        best: tuple[int, int] | None = None

        def walk(n: dict) -> None:
            nonlocal best
            src = n.get("src")
            own = bool(src and src["file"] == file and src["line"] <= line)
            chain = [
                c
                for c in n.get("chain") or []
                if c["file"] == file and c["line"] <= line
            ]
            if n.get("g") is not None and (own or chain):
                at = src["line"] if own else max(c["line"] for c in chain)
                if best is None or at >= best[0]:
                    best = (at, n["g"])
            for c in n.get("children") or []:
                walk(c)

        if self.outline:
            walk(self.outline)
        return best[1] if best else None

    def slide_source(self, g: int | None) -> dict | str:
        """The source of slide `g`: {file, path, line, end} (its heading's
        line, the next outline entry's line in the same file); an error
        message otherwise."""
        if g is None:
            return "no such slide"
        nodes: list[dict] = []

        def walk(n: dict) -> None:
            if n.get("src"):
                nodes.append(n)
            for c in n.get("children") or []:
                walk(c)

        if self.outline:
            walk(self.outline)
        node = next((n for n in reversed(nodes) if n.get("g") == g), None)
        if not node:
            return "the slide has no source location"
        file, line = node["src"]["file"], node["src"]["line"]
        nxt = [
            n["src"]["line"]
            for n in nodes
            if n["src"]["file"] == file and n["src"]["line"] > line
        ]
        return {
            "file": file,
            "path": (self.course.root / file).resolve(),
            "line": line,
            "end": min(nxt) if nxt else float("inf"),
        }

    def set_work(self, g: int, state: str, note: str | None) -> dict:
        """Slide `g`'s work state ("todo", "check", "none"; `note` None
        keeps the current one) written into its source (work.py)."""
        from .work import set_work_state

        where = self.slide_source(g)
        if isinstance(where, str):
            return {"error": where}
        if note is not None and not isinstance(note, str):
            return {"error": "the note must be a string"}
        src = where["path"].read_text()
        r = set_work_state(src, where["line"], where["end"], state, note)
        if isinstance(r, str):
            return {"error": f"{r} ({where['file']})"}
        out, line = r
        if out != src:
            where["path"].write_text(out)
        return {"file": where["file"], "line": line or where["line"], "state": state}

    def move_annot(self, page: int, key: str, values: dict) -> dict:
        """shift-O: the annotation `key` of page `page` was moved: write
        `values` ({dx, dy, width?}, Typst lengths) into its #annot call."""
        from .annot import pick_annot_call, set_annot_args

        g = self.group_of_page.get(page)
        if g is None:
            return {"error": f"no slide on page {page}"}
        where = self.slide_source(g)
        if isinstance(where, str):
            return {"error": where}
        file, line, path = where["file"], where["line"], where["path"]
        src = path.read_text()
        found = pick_annot_call(src, key, line, where["end"])
        if isinstance(found, str):
            return {"error": f"{found} ({file})"}
        allowed = {
            k: v
            for k, v in (values or {}).items()
            if k in ("dx", "dy", "width")
            and isinstance(v, str)
            and re.fullmatch(r"-?\d+(\.\d+)?pt", v)
        }
        if not allowed:
            return {"error": "nothing to write"}
        out = set_annot_args(src, found, allowed)
        if out != src:
            path.write_text(out)
        return {"file": file, "line": found.line}


def copy_tree(src: Path, dst: Path, skip: set[str] = frozenset()) -> None:  # type: ignore[assignment]
    """Copy `src` into `dst`, skipping files already there and unchanged."""
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if rel.parts and rel.parts[0] in skip:
            continue
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for f in files:
            if not rel.parts and f in skip:
                continue
            s, d = Path(root) / f, dst / rel / f
            st = s.stat()
            if (
                d.exists()
                and d.stat().st_size == st.st_size
                and d.stat().st_mtime >= st.st_mtime
            ):
                continue
            shutil.copy2(s, d)
