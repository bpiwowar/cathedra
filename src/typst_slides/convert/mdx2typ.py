# ruff: noqa: T201, C901, E741
"""Convert a slide-app MDX module to a Typst module (lib/slides.typ).

    typst-slides convert [--src DIR] [--macros FILE]
        [--notation FILE] <module-id> [<module-id>...]

run from the course directory: reads <src>/<id>/<id>.mdx (default
../src/modules), writes modules/<id>/<id>.typ (+ figures/), under $SLIDES_SRC.
--backup DIR: then moves the .mdx to DIR/modules/<id>/<id>.mdx (decks:
DIR/lectures/…), e.g. to convert in place, the MDX and Typst sources in the
same folders. --macros: the
MathJax macros of the MDX decks (default ../src/lectures/common/macros.tex),
expanded before the maths is converted. --notation (default
common/mdx-notation.json, if present): [regex, replacement] pairs applied to
the Typst maths, to use the course's notation (`upright(t f)` -> `tf`).
A one-shot migration aid: the output is meant to be reviewed and then edited
by hand, not regenerated.

1. JSX -> pandoc markdown: <SubSection>/<Slide> become ##/### headings,
   blocks and <Columns>/<div> become fenced divs, <Cite> is resolved to a
   bib key (doi:// or zotero:// against the course's .bib), inline <svg> is
   extracted to figures/, inline HTML tags become markdown.
2. pandoc (markdown -> typst, LaTeX maths -> Typst maths, with the shared
   macros expanded) + mdx2typ.lua (next to this file).

Needs pandoc, and json5 (`typst-slides[convert]`).
"""

import argparse
import textwrap
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from ..spacing import space_slides

HERE = pathlib.Path(__file__).resolve().parent  # mdx2typ.lua
TYPST = pathlib.Path.cwd()  # the course (Typst's root: lib/)
# its sources (lectures/, modules/, common/): $SLIDES_SRC, relative to TYPST,
# and the root-absolute prefix of their paths ("/" or "/src/")
SRC = TYPST / os.environ.get("SLIDES_SRC", ".")
SRC_PREFIX = "/" + "".join(
    p + "/"
    for p in pathlib.PurePosixPath(os.path.relpath(SRC, TYPST)).parts
    if p != "."
)
BLOCKS = {
    "Definition": "definition",
    "Observation": "observation",
    "Alert": "alert",
    "Idea": "idea",
    "Remark": "remark",
    "Comment": "remark",
    "Goal": "goal",
    "Motivation": "motivation",
    "Question": "question",
    "Problem": "problem",
    "Solution": "solution",
    "Theorem": "theorem",
    "Example": "example",
}


def course_bib() -> str:
    """The course's .bib, relative to its directory ($SLIDES_BIB: the
    Makefile's BIB)."""
    bib = os.environ.get("SLIDES_BIB")
    if not bib:
        raise SystemExit("convert: SLIDES_BIB (the course's .bib) is not set")
    return bib.removeprefix("./").lstrip("/")


def bib_index():
    """doi / zotero item key (lower case) -> bib key."""
    index = {}
    text = (TYPST / course_bib()).read_text()
    for chunk in re.split(r"(?m)^(?=@)", text):
        m = re.match(r"@\w+\{([^,\s]+),", chunk)
        if not m:
            continue
        key = m.group(1)
        index["key:" + key] = key
        if d := re.search(r"(?im)^\s*doi\s*=\s*\{([^}]+)\}", chunk):
            index["doi://" + d.group(1).strip().lower()] = key
        # `zotero={user:ID/KEY}` (scoped) or `zotero = {KEY}` (bare key)
        if z := re.search(
            r"zotero\s*=\s*\{(?:(?:library|user|group):\d+/)?(\w+)", chunk
        ):
            index["zotero://select/library/items/" + z.group(1).lower()] = key
    return index


BIB = None


def cite_key(entry: str) -> str | None:
    """The bib key of a <Cite> entry; None (with a warning) when not in the course's .bib."""
    if entry.startswith("doi://") or entry.startswith("zotero://"):
        key = BIB.get(entry.lower())
    else:
        key = entry if ("key:" + entry) in BIB else None
    if not key:
        print(
            f"citation not found in the course's .bib (left as TODO-REVIEW): {entry}",
            file=sys.stderr,
        )
    return key


def attr(attrs: str, name: str):
    m = re.search(rf'\b{name}=(?:"([^"]*)"|\{{"([^"]*)"\}})', attrs)
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None


SVG_CAMEL = {
    "viewBox",
    "preserveAspectRatio",
    "markerWidth",
    "markerHeight",
    "markerUnits",
    "refX",
    "refY",
    "gradientUnits",
    "gradientTransform",
    "patternUnits",
    "textLength",
    "lengthAdjust",
    "stdDeviation",
}


def jsx_svg_to_svg(svg: str) -> str:
    """JSX inline SVG -> standalone SVG file."""
    svg = re.sub(r"\s*style=\{\{[^}]*\}\}", "", svg)
    svg = re.sub(r"\s*className=(\"[^\"]*\"|\{[^}]*\})", "", svg)
    # JSX camelCase -> SVG attributes (strokeWidth -> stroke-width), except
    # those SVG spells in camelCase
    svg = re.sub(
        r"\b([a-z]+)([A-Z][a-z]+)=",
        lambda m: (
            m.group(0)
            if m.group(0)[:-1] in SVG_CAMEL
            else f"{m.group(1)}-{m.group(2).lower()}="
        ),
        svg,
    )
    svg = re.sub(r"=\{(\d+(?:\.\d+)?)\}", r'="\1"', svg)
    svg = svg.replace('"currentColor"', '"black"')
    if "xmlns=" not in svg:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg + "\n"


# ----------------------------------------------------- HTML / JSX elements
# slide-app decks also write their content as HTML (<ul><li>, <dl>, <h1>,
# <div className="hand fragment">…) and layout components (<Grid>, <Frame>…).
# block_tags() turns each element into a pandoc fenced div whose classes say
# what it was (`.ul`, `.li`, `.cols`, `.frame`…) plus its className; the Lua
# filter (mdx2typ.lua) turns them into lib/slides.typ calls.

ATTRS = r"((?:[^>\"{]|\"[^\"]*\"|\{\{[^}]*\}\}|\{[^}]*\})*?)"
FRAMED = {
    "Frame": None,
    "Card": "card",
    "Algorithm": "algorithm",
    "Soa": "soa",
    "Paper": "soa",
    "Limitations": "limitations",
}
BLOCK_TAGS = (
    [
        "ul",
        "ol",
        "li",
        "dl",
        "dt",
        "dd",
        "h1",
        "h2",
        "h3",
        "h4",
        "p",
        "div",
        "Cell",
        "Grid",
        "Columns",
        "Box",
        "Focus",
        "RFragment",
        "Synopsis",
        "Citation",
        "IMG",
        "figure",
        "figcaption",
    ]
    + list(FRAMED)
    + list(BLOCKS)
)
TAG = re.compile(rf"<(/?)({'|'.join(BLOCK_TAGS)})\b{ATTRS}(/?)>")


def fence(classes: list[str], **attrs) -> str:
    kv = "".join(
        f' {k}="' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'
        for k, v in attrs.items()
        if v
    )
    return "\n\n::: {" + " ".join("." + c for c in classes) + kv + "}\n\n"


CLOSE = "\n\n:::\n\n"


def element_div(name: str, attrs: str, stack: list) -> str:
    """The fenced div opening an element `name` with JSX `attrs`."""
    cls = (attr(attrs, "className") or "").split()
    if re.search(r"(?<![\w-])fragment(?![\w=-])", re.sub(r'"[^"]*"', "", attrs)):
        cls.append("fragment")  # Framed components' boolean `fragment` prop
    title = attr(attrs, "title")
    if name in ("ul", "ol"):
        depth = sum(1 for n, _ in stack if n in ("ul", "ol")) + 1
        return fence([name] + cls, depth=depth, start=attr(attrs, "start"))
    if name in ("li", "dl", "dt", "dd", "p", "figure", "figcaption"):
        return fence([name] + cls)
    if name[0] == "h" and name[1:].isdigit():
        return fence(["h"] + cls, level=name[1:])
    if name == "Cell":  # a cell of a <Grid> (a span to redo with grid.cell)
        in_grid = bool(stack) and stack[-1][0] in ("Grid", "Columns")
        return fence(["cell"] if in_grid else ["div"])
    if name == "div":
        in_grid = bool(stack) and stack[-1][0] in ("Grid", "Columns")
        return fence(["cell"] if in_grid and not cls else (cls or ["div"]))
    if name in ("Grid", "Columns"):
        return fence(["cols"] + cls, widths=attr(attrs, "columns"))
    if name in FRAMED:
        kind = FRAMED[name] or attr(attrs, "type") or "block"
        return fence(["frame"] + cls, kind=kind, title=title)
    if name == "Box":
        return fence(
            ["boxbox"] + cls + (["center"] if re.search(r"\bcentered\b", attrs) else [])
        )
    if name == "Focus":
        return fence(["focus", "fragment"] + cls, width=attr(attrs, "width"))
    if name == "RFragment":
        return fence(["fragment"] + cls)
    if name == "Synopsis":
        return fence(["synopsis"])
    if name == "Citation":
        return fence(["citation"], source=attr(attrs, "source"))
    return fence([BLOCKS[name]] + cls, title=title)


def block_tags(mdx: str, img_typst) -> str:
    out, pos, stack = [], 0, []  # stack: (name, wrapped in a grid cell)
    for m in TAG.finditer(mdx):
        out.append(mdx[pos : m.start()])
        pos = m.end()
        closing, name, attrs, selfclosing = m.groups()
        in_grid = bool(stack) and stack[-1][0] in ("Grid", "Columns")
        if closing:
            if not stack:
                print(f"unbalanced </{name}>", file=sys.stderr)
                continue
            top, cell = stack.pop()
            if top != name:
                print(f"</{name}> closes <{top}>", file=sys.stderr)
            out.append(CLOSE + (CLOSE if cell else ""))
            continue
        # a grid's children are its cells: each one in a `.cell` div
        cell = in_grid and not (
            name in ("div", "Cell") and not attr(attrs, "className")
        )
        if cell:
            out.append(fence(["cell"]))
        if name == "IMG":
            typ, cls = img_typst(int(attrs.strip()))
            raw = f"\n\n```{{=typst}}\n{typ}\n```\n\n"
            out.append(fence(cls) + raw + CLOSE if cls else raw)
            if cell:
                out.append(CLOSE)
            continue
        if selfclosing:  # <div/>: nothing to show
            if cell:
                out.append(CLOSE)
            continue
        out.append(element_div(name, attrs, stack))
        stack.append((name, cell))
    out.append(mdx[pos:])
    if stack:
        print(f"unclosed: {[n for n, _ in stack]}", file=sys.stderr)
    return "".join(out)


def css_length(v: str) -> str:
    """A CSS length -> Typst: % as is, px at the MDX deck's scale (700 px tall)."""
    v = v.strip()
    if v.endswith("%") or v.endswith("em"):
        return v
    if m := re.fullmatch(r"([\d.]+)(vh|vw)", v):  # of the (16:9) page
        return f"{float(m.group(1)) * (473.56 if m.group(2) == 'vh' else 841.89) / 100:.0f}pt"
    n = float(re.sub(r"px$", "", v))
    return f"{n * 473.56 / 700:.0f}pt"


def copy_image(src: str, src_dir: pathlib.Path, module_dir: pathlib.Path) -> str:
    """Copy an image of the MDX module into the Typst one: its path there."""
    path = (src_dir / src).resolve()
    if not path.suffix:  # <Image src="./images/x"> (the build picks the format)
        found = sorted(path.parent.glob(path.name + ".*"))
        path = found[0] if found else path
    if not path.exists():
        print(f"image not found: {src}", file=sys.stderr)
        return src
    name = path.name
    head = path.read_bytes()[:12]
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP" and path.suffix != ".webp":
        name = path.stem + ".webp"  # served as .png by the browser, not by Typst
    dest = module_dir / "images" / name
    if path.is_relative_to(module_dir.resolve()):  # converted in place: already there
        return path.relative_to(module_dir.resolve()).as_posix()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, dest)
    return f"images/{name}"


def html_table(m) -> str:
    html = re.sub(r"className=", "class=", m.group(0))
    # the cells' tags were turned into markdown already: back to HTML, for
    # pandoc to write them itself (escaped, they would show as text)
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    html = re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"<i>\1</i>", html)
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
    html = re.sub(r"\[([^\]]*)\]\{\.([\w-]+)\}", r'<span class="\2">\1</span>', html)
    # maths stays maths (tex_math_dollars), with its `<` and `&` escaped for
    # the HTML parser: escaped as text, it would also cut the columns wrong
    html = re.sub(
        r"(?<![\\$])\$([^$]+)\$",
        lambda x: "$" + x.group(1).replace("&", "&amp;").replace("<", "&lt;") + "$",
        html,
    )
    md = subprocess.run(
        [
            "pandoc",
            "-f",
            "html+tex_math_dollars",
            "-t",
            "markdown-raw_html-native_divs-native_spans-simple_tables-multiline_tables",
        ],
        input=html,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    # pandoc indents its simple tables, whose columns are character positions:
    # the dedent below would strip the rows but not the `---` rulers
    md = textwrap.dedent(md)
    return "\n\n" + md + "\n\n"


def number_steps(typ: str) -> str:
    """Number the step markers (`«F»`, `«O»`) in document order, as Reveal
    numbers fragments, slide by slide; a slide with steps gets `#steps(n)`."""
    parts = re.split(r"(?m)(^={1,3} .*$)", typ)
    for i in range(0, len(parts), 2):
        n = 1

        def sub(m):
            nonlocal n
            n += 1
            return str(n)

        parts[i] = re.sub(r"«F»|«O»", sub, parts[i])
        if n > 1 and i > 0:
            parts[i - 1] += f"\n#steps({n})"
    return "".join(parts)


def preprocess(
    mdx: str, module_dir: pathlib.Path, mid: str, src_dir: pathlib.Path
) -> tuple[dict, str]:
    meta = {}
    if m := re.search(r"export const meta = (\{.*?\n\});?\n", mdx, re.S):
        import json5

        meta = json5.loads(m.group(1))
        mdx = mdx.replace(m.group(0), "")

    # comments
    mdx = re.sub(
        r"\{/\*\s*(.*?)\s*\*/\}",
        lambda m: f"\n<!-- {m.group(1)} -->\n",
        mdx,
        flags=re.S,
    )

    # remark directives: `:::name{.cls attrs}` … `:::` (a container; more
    # colons for one that holds others),
    # `::name[text]` (a block), `:name[text]` (inline) -> pandoc divs / spans
    # whose first class is the name (e.g. :::fragment{.exclusive}: one step,
    # shown alone; ::comment[…]; :red[…])
    mdx = re.sub(
        r"(?m)^(\s*)(:{3,})([A-Za-z][\w-]*)(?:\{([^}]*)\})?\s*$",
        lambda m: f"{m.group(1)}{m.group(2)} {{.{m.group(3)} {m.group(4) or ''}}}",
        mdx,
    )
    mdx = re.sub(
        r"(?m)^(\s*)::([A-Za-z][\w-]*)\[(.*)\](?:\{([^}]*)\})?\s*$",
        lambda m: (
            f"\n{m.group(1)}::: {{.{m.group(2)} {m.group(4) or ''}}}\n\n{m.group(3)}\n\n:::\n"
        ),
        mdx,
    )
    mdx = re.sub(r"(?<![\w:/]):([A-Za-z][\w-]*)\[([^\]\n]*)\]", r"[\2]{.\1}", mdx)

    # decks: imported MDX files -> #include of their Typst port (an MDX file
    # <dir>/<name>.mdx, module or lecture-local, becomes /modules/<dir>/<name>.typ),
    # <MainSection> -> a main section, <TitleSlide> -> #title-slide()
    includes = {}

    def import_sub(m):
        path = (src_dir / m.group(2)).resolve()
        # a deck's own file already ported into its folder: lectures/<dir>/
        local = SRC / "lectures" / path.parent.name / f"{path.stem}.typ"
        kind = "lectures" if local.exists() else "modules"
        includes[m.group(1)] = f"{SRC_PREFIX}{kind}/{path.parent.name}/{path.stem}.typ"
        return ""

    mdx = re.sub(r'(?m)^import\s+(\w+)\s+from\s+"([^"]+\.mdx)";?\s*$', import_sub, mdx)

    # imported images (`import fig from "./figures/x.svg"`, used as
    # <object data={fig}> or <img src={fig}>) -> <img data-src="…">; a .drawio
    # file is shown through the .svg exported next to it
    assets = {}

    def asset_sub(m):
        src = m.group(2)
        if src.endswith(".drawio"):
            src = src[: -len(".drawio")] + ".svg"
        assets[m.group(1)] = src
        return ""

    mdx = re.sub(
        r'(?m)^import\s+(\w+)\s+from\s+"([^"]+\.(?:svg|png|jpe?g|webp|gif|drawio))";?\s*$',
        asset_sub,
        mdx,
    )

    def object_sub(m):
        var = re.search(r"(?:data|src)=\{(\w+)\}", m.group(2))
        if not var or var.group(1) not in assets:
            return m.group(0)
        cls = attr(m.group(2), "className")
        return (
            f'<img data-src="{assets[var.group(1)]}"'
            + (f' className="{cls}"' if cls else "")
            + " />"
        )

    mdx = re.sub(
        r"<(object|img)\b((?:[^>\"{]|\"[^\"]*\"|\{[^}]*\})*?)/?>(?:\s*</object>)?",
        object_sub,
        mdx,
    )
    # other imports and exports (React components, figure loaders): see the leftovers
    mdx = re.sub(
        r"(?m)^(import\b.*|export const \w+ = .*)$",
        lambda m: f"\n<!-- TODO-REVIEW: {m.group(1)} -->\n",
        mdx,
    )
    mdx = re.sub(
        r"<(\w+)\s*/>",
        lambda m: (
            f'\n```{{=typst}}\n#include "{includes[m.group(1)]}"\n```\n'
            if m.group(1) in includes
            else m.group(0)
        ),
        mdx,
    )
    mdx = re.sub(
        r"<MainSection\b([^>]*)>", lambda m: f"\n# {attr(m.group(1), 'title')}\n", mdx
    )
    mdx = re.sub(r"</MainSection>", "\n", mdx)
    mdx = re.sub(
        r"<TitleSlide\b(.*?)/>", "\n```{=typst}\n#title-slide()\n```\n", mdx, flags=re.S
    )

    # inline svg -> figures/
    n = 0

    def svg_sub(m):
        nonlocal n
        n += 1
        (module_dir / "figures").mkdir(parents=True, exist_ok=True)
        name = f"{mid}-{n}.svg"
        (module_dir / "figures" / name).write_text(jsx_svg_to_svg(m.group(0)))
        # its size and placement: style={{ width: … }}, className="centered"
        head = m.group(0)[: m.group(0).index(">")]
        w = re.search(r"\bwidth\s*:\s*[\"']([^\"']+)[\"']", head)
        img = (
            f'image("figures/{name}", width: {css_length(w.group(1)) if w else "100%"})'
        )
        if re.search(r"\bcenter(ed)?\b", attr(head, "className") or ""):
            img = f"align(center, {img})"
        return f"\n```{{=typst}}\n#{img}\n```\n"

    mdx = re.sub(r"<svg\b.*?</svg>", svg_sub, mdx, flags=re.S)

    # citations
    def cite_sub(m):
        attrs = m.group(1)
        entry = attr(attrs, "entry")
        if entry is None and (arr := re.search(r"entry=\{\[(.*?)\]\}", attrs, re.S)):
            entries = re.findall(r'"([^"]+)"', arr.group(1))
        else:
            entries = [entry]
        found = [k for e in entries if (k := cite_key(e))]
        missing = "".join(
            f"// TODO-REVIEW: citation not in the bibliography: {e}\n"
            for e in entries
            if not cite_key(e)
        )
        if not found:
            return f"\n```{{=typst}}\n{missing}```\n"
        # `<key>`, or label("key") for keys a Typst label cannot spell
        keys = ", ".join(
            f"<{k}>" if re.fullmatch(r"[\w:.-]+", k) else f"label({json.dumps(k)})"
            for k in found
        )
        if missing:
            print(f"(partly) unresolved <Cite>: {entries}", file=sys.stderr)
        if re.search(r"\binline\b", attrs):
            # label("…"): `<key>` would be read as an HTML tag in a table cell
            return (
                "`#cite("
                + ", ".join(f"label({json.dumps(k)})" for k in found)
                + ")`{=typst}"
            )
        return f"\n```{{=typst}}\n#reference({keys})\n```\n"

    mdx = re.sub(r"<Cite\b(.*?)/>", cite_sub, mdx, flags=re.S)

    # markdown headings inside a <Slide>: the first one, when the slide has
    # no title, is its title (slide-app shows it as such); the others are
    # headings within the slide, not Typst sections
    def slide_headings(m):
        attrs, body = m.group(1), m.group(2)
        h = re.match(r"\s*#{1,6}[ \t]+([^\n\"]+?)[ \t]*\n", body)
        if h and not attr(attrs, "title"):
            attrs += f' title="{h.group(1)}"'
            body = body[h.end() :]
        # (not in code blocks, where # starts a comment)
        parts = re.split(r"(```.*?```)", body, flags=re.S)
        for i in range(0, len(parts), 2):
            parts[i] = re.sub(
                r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$",
                lambda h: (
                    f"<h{min(len(h.group(1)) + 1, 4)}>{h.group(2)}</h{min(len(h.group(1)) + 1, 4)}>"
                ),
                parts[i],
            )
        return f"<Slide{attrs}>{''.join(parts)}</Slide>"

    mdx = re.sub(r"<Slide\b([^>]*)>(.*?)</Slide>", slide_headings, mdx, flags=re.S)

    # `#` right after an opening tag is text (`<div># Tools<br/>…`), not a
    # heading once the element is on lines of its own
    mdx = re.sub(r"(<[a-z][\w-]*\b[^>]*>)#", r"\1\\#", mdx)

    # sections and slides
    mdx = re.sub(
        r"<SubSection\b([^>]*)>", lambda m: f"\n## {attr(m.group(1), 'title')}\n", mdx
    )
    mdx = re.sub(r"</SubSection>", "", mdx)

    def slide_sub(m):
        attrs = m.group(1)
        title = attr(attrs, "title") or ""
        out = f"\n### {title}\n"
        # slide types (className="optional todo"…) -> #slide-type(…)
        if cls := attr(attrs, "className"):
            names = ", ".join(json.dumps(c) for c in cls.split())
            out += f"\n```{{=typst}}\n#slide-type({names})\n```\n"
        return out

    mdx = re.sub(r"<Slide\b([^>]*)>", slide_sub, mdx)
    # work-in-progress notes -> #todo("…")
    mdx = re.sub(
        r"<[Tt]odo\b([^>]*?)/>",
        lambda m: (
            f"\n```{{=typst}}\n#todo({json.dumps(attr(m.group(1), 'title') or '')})\n```\n"
        ),
        mdx,
    )
    mdx = re.sub(r"</Slide>", "", mdx)

    # <M>{String.raw`latex`}</M> -> display maths; <Code language title>{`…`}</Code> -> a code block
    mdx = re.sub(
        r"<M>\{String\.raw`(.*?)`\}</M>",
        lambda m: f"\n$${m.group(1)}$$\n",
        mdx,
        flags=re.S,
    )

    def code_sub(m):
        lang, title = attr(m.group(1), "language") or "", attr(m.group(1), "title")
        head = f"\n**{title}**\n" if title else ""
        return f"\n{head}\n```{lang}\n{m.group(2).strip()}\n```\n"

    mdx = re.sub(r"<Code\b([^>]*)>\{`(.*?)`\}</Code>", code_sub, mdx, flags=re.S)

    # images -> placeholders (<IMG n/>), turned into #img(…) by the block pass
    images = []

    def img_sub(m):
        attrs = m.group(2)
        src = attr(attrs, "data-src") or attr(attrs, "src")
        if not src:
            return m.group(0)
        images.append((src, attrs))
        return f"<IMG {len(images) - 1}/>"

    mdx = re.sub(
        r"<(img|Image)\b((?:[^>\"{]|\"[^\"]*\"|\{\{[^}]*\}\}|\{[^}]*\})*?)/?>",
        img_sub,
        mdx,
    )
    mdx = re.sub(r"</Image>", "", mdx)

    def img_typst(n):
        src, attrs = images[n]
        path = copy_image(src, src_dir, module_dir)
        args = [f"path({json.dumps(path)})"]  # relative to the module
        # width= / height=, or in style={{ … }}
        style = dict(re.findall(r"\b(width|height)\s*:\s*[\"']([^\"']+)[\"']", attrs))
        if w := attr(attrs, "width") or style.get("width"):
            args.append(f"width: {css_length(w)}")
        if h := attr(attrs, "height") or style.get("height"):
            args.append(f"height: {css_length(h)}")
        if z := re.search(r"zoom:\s*[\"']?([\d.]+)(%?)", attrs):
            args.append(f"zoom: {float(z.group(1)) / (100 if z.group(2) else 1):g}")
        if origin := attr(attrs, "origin"):
            args.append(f"origin: {json.dumps(origin)}")
        cls = (attr(attrs, "className") or "").split()
        if "centered" in cls or "center" in cls:
            args.append("center: true")
        rest = [c for c in cls if c not in ("centered", "center")]
        return f"#img({', '.join(args)})", rest

    mdx = block_tags(mdx, img_typst)

    # inline html / jsx
    mdx = re.sub(
        r"<Ext\s+href=\"([^\"]+)\"\s*>(.*?)</Ext>", r"[\2](\1)", mdx, flags=re.S
    )
    mdx = re.sub(r"<a\s+href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"[\2](\1)", mdx, flags=re.S)
    mdx = re.sub(
        r"<WikiRef\b([^>]*?)/>",
        lambda m: f"`#wikiref({json.dumps(attr(m.group(1), 'name'))})`{{=typst}}",
        mdx,
    )
    mdx = re.sub(
        r"<WikiRef\b([^>]*?)>(.*?)</WikiRef>",
        lambda m: (
            f"`#wikiref({json.dumps(attr(m.group(1), 'name') or m.group(2))})`{{=typst}}"
        ),
        mdx,
        flags=re.S,
    )
    mdx = re.sub(
        r"<SelfLink\b([^>]*?)/>",
        lambda m: f"`#selflink({json.dumps(attr(m.group(1), 'href'))})`{{=typst}}",
        mdx,
    )
    for tag, md in (("b", "**"), ("strong", "**"), ("em", "*"), ("i", "*")):
        mdx = re.sub(rf"<{tag}>(.*?)</{tag}>", rf"{md}\1{md}", mdx, flags=re.S)

    def verbatim(s):  # JSX text in <code>: {"{q}"} -> {q}, &lt; -> <
        return html.unescape(re.sub(r'\{"([^"]*)"\}', r"\1", s))

    # <code> holding markup (styled <span>s…) is monospaced text, not verbatim
    mdx = re.sub(
        r"<code>(.*?)</code>",
        lambda m: (
            f"[{m.group(1)}]{{.code}}"
            if "<" in m.group(1)
            else f"`{verbatim(m.group(1))}`"
        ),
        mdx,
        flags=re.S,
    )
    mdx = re.sub(r"<br\s*/?>", "\\\n", mdx)
    mdx = re.sub(r"<sup>(.*?)</sup>", r"[\1]{.sup}", mdx, flags=re.S)
    mdx = re.sub(r"<sub>(.*?)</sub>", r"[\1]{.sub}", mdx, flags=re.S)
    # spans, innermost first: classes -> [text]{.class}, none -> the text
    span = re.compile(r"<span\b([^>]*)>((?:(?!<span\b).)*?)</span>", re.S)
    while span.search(mdx):
        mdx = span.sub(
            lambda m: (
                "[" + m.group(2) + "]{" + " ".join("." + c for c in cls.split()) + "}"
                if (cls := attr(m.group(1), "className"))
                else m.group(2)
            ),
            mdx,
        )
    mdx = re.sub(r"(?m)^[ \t]*<table\b.*?</table>", html_table, mdx, flags=re.S)
    mdx = re.sub(r"\{\s*\"\s*\"\s*\}", " ", mdx)  # JSX {" "}

    # block content was indented inside JSX tags: dedent (4 spaces = code!),
    # but keep the indentation of nested list items
    parts = re.split(r"(?ms)(^```.*?^```)", mdx)  # leave fenced code alone
    mdx = "".join(
        p
        if p.startswith("```")
        else re.sub(r"(?m)^ {2,}(?=(?![-*+]\s|\d+[.)]\s)\S)", "", p)
        for p in parts
    )
    # a list right after a paragraph line needs a blank line in pandoc markdown
    mdx = re.sub(
        r"(?m)^((?![ \t]*(?:[-*]|\d+\.)\s)[^\n|]*\S[^\n]*)\n(?=(?:[-*]|\d+\.)\s)",
        r"\1\n\n",
        mdx,
    )

    # `$\approx $`: a space after the opening $ or before the closing one is
    # not maths in pandoc markdown (MathJax takes it): the formula would be
    # text. The inline $…$ of each line, paired left to right, are trimmed
    # (not `$5 and $10`: currency).
    def trim_math(m):
        return m.group(0) if m.group(1)[:1].isdigit() else f"${m.group(1).strip()}$"

    parts = re.split(r"(?ms)(^```.*?^```|\$\$.*?\$\$)", mdx)
    mdx = "".join(
        p if i % 2 else re.sub(r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$", trim_math, p)
        for i, p in enumerate(parts)
    )
    # `$\sim$1000`: a closing $ before a digit is not maths in markdown
    # (formulas paired left to right: not `$–$` in `$a$–$b$`; not `$5 and $10`)
    mdx = "".join(
        p
        if i % 2
        else re.sub(
            r"(?<![\\$])\$(?!\$)([^$\n]+?)(?<!\\)\$(\d?)",
            lambda x: (
                x.group(0)[:-1] + " " + x.group(2)
                if x.group(2) and not x.group(1)[:1].isdigit()
                else x.group(0)
            ),
            p,
        )
        for i, p in enumerate(re.split(r"(?ms)(^```.*?^```|\$\$.*?\$\$)", mdx))
    )

    # what is left of the JSX (React components, figures): a comment to review,
    # so that the module compiles (raw Typst, e.g. a <label>, is left alone)
    parts = re.split(r"(?ms)(^```\{=typst\}.*?^```|`[^`\n]*`\{=typst\})", mdx)
    leftovers = set()

    def jsx_sub(m):
        leftovers.add(re.match(r"</?\w+", m.group(0)).group(0))
        return (
            "\n```{=typst}\n// TODO-REVIEW: " + " ".join(m.group(0).split()) + "\n```\n"
        )

    mdx = "".join(
        p if i % 2 else re.sub(rf"</?[A-Z][A-Za-z0-9]*\b{ATTRS}/?>", jsx_sub, p)
        for i, p in enumerate(parts)
    )
    if leftovers:
        print(
            f"{mid}: unconverted JSX (left as TODO-REVIEW comments): {sorted(leftovers)}",
            file=sys.stderr,
        )
    return meta, mdx


# pandoc's Typst maths is correct but defensive; make it read like hand-written
# Typst, using the course's notation (--notation).
# set from --notation; `upright("…")` -> `"…"` holds for any course
# set from --classes: the course's own CSS classes -> the function of
# common/course.typ that renders them (e.g. {"llm-prompt": "llm-prompt"})
CLASSES = {}
NOTATION = [(r"upright\(\"([^\"]+)\"\)", r'"\1"')]


def unescape(math: str) -> str:
    """Drop pandoc's `\\(`, `\\)`, `\\[`, `\\]` and `\\,` escapes where it is safe.

    A comma stays escaped when its innermost parenthesis opens the argument
    list of a real call (`underbrace(a\\, b, "x")`): there an unescaped comma
    would separate arguments. Inside a literal group (`\\(…\\)`, which becomes
    `(…)` displayed as is) or at the top level it is plain punctuation.
    """
    out, stack, i = [], [], 0
    while i < len(math):
        two = math[i : i + 2]
        if two in ("\\(", "\\["):
            stack.append("lit")
            # `p_theta\(x\)` -> `p_theta (x)`: without the space, Typst
            # reads `theta(x)` as the subscript (a call)
            if re.search(r"[_^][A-Za-z][\w.]*$", "".join(out[-24:])):
                out.append(" ")
            out.append(two[1])
            i += 2
        elif two in ("\\)", "\\]"):
            if stack:
                stack.pop()
            out.append(two[1])
            i += 2
        elif two == "\\,":
            out.append(", " if not stack or stack[-1] == "lit" else "\\, ")
            i += 2
            while i < len(math) and math[i] == " ":
                i += 1
        else:
            c = math[i]
            if c == "(":
                stack.append("call")
            elif c == ")" and stack:
                stack.pop()
            out.append(c)
            i += 1
    return "".join(out)


CARRIER = re.compile(r',\s*upright\("@(color|size):([^"]*)"\)\)')


def math_carriers(typ: str) -> str:
    """The Lua filter's carriers, `overbrace(x, upright("@color:red"))` (what
    pandoc writes for `\\overbrace{x}^{\\text{@color:red}}`: MathJax's colours
    and sizes, which texmath cannot convert) -> `#text(fill: red, $x$)`,
    `script(x)`, `#text(size: 0.9em, $x$)`. Innermost first."""
    while m := CARRIER.search(typ):
        depth, i = 0, m.start() - 1
        while i >= 0:  # the `overbrace(` the marker closes (escaped parens are text)
            c = typ[i]
            if c == '"':  # a string (`delim: "("`): skipped
                i = typ.rfind('"', 0, i) - 1
                continue
            if c in "()" and not (i > 0 and typ[i - 1] == "\\"):
                if c == ")":
                    depth += 1
                elif depth == 0:
                    break
                else:
                    depth -= 1
            i -= 1
        start = i - len("overbrace")
        if i < 0 or typ[start:i] != "overbrace":
            print(f"maths carrier without its overbrace: {m.group(0)}", file=sys.stderr)
            typ = typ[: m.start()] + ")" + typ[m.end() :]
            continue
        body, (kind, arg) = typ[i + 1 : m.start()].strip(), m.groups()
        if kind == "size" and arg == "script":
            new = f"script({body})"
        elif kind == "size":
            new = f"#text(size: {arg}, ${body}$)"
        else:
            color = arg if re.fullmatch(r"[a-z]+", arg) else f'rgb("{arg}")'
            new = f"#text(fill: {color}, ${body}$)"
        typ = typ[:start] + new + typ[m.end() :]
    return typ


def _group_end(s: str, i: int) -> int:
    """Index of the `)` matching the `(` at s[i] (strings skipped), or -1."""
    depth = 0
    while i < len(s):
        c = s[i]
        if c == "\\":
            i += 1
        elif c == '"':
            i = s.find('"', i + 1)
            if i < 0:
                return -1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _bold_arg(s: str, pat: str) -> str:
    """Rewrite `bold(A)` (also under `upright(…)`) with `vv(A)` / `mm(A)`
    (capital): the course's upright bold vectors and matrices. A string
    (`bold("sa")`) is a text label and stays."""
    out, i = [], 0
    for m in re.finditer(pat, s):
        if m.start() < i:
            continue
        o = m.end() - 1
        c = _group_end(s, o)
        if c < 0:
            continue
        inner = s[o + 1 : c]
        # `upright(bold(A))`: the closing paren of upright
        wrapped = m.group(0).startswith("upright")
        if wrapped:
            c2 = _group_end(s, m.start() + len("upright"))
            if c2 != c + 1:
                continue
            c = c2
        if inner.startswith('"'):
            continue
        out.append(s[i : m.start()])
        out.append(("mm(" if inner[:1].isupper() else "vv(") + inner + ")")
        i = c + 1
    out.append(s[i:])
    return "".join(out)


def course_macros() -> set:
    """The notation macros the course defines in common/course.typ
    (`#let vv(`, `#let mm(`, `#let softmax`): the converter emits them only
    where the course has them."""
    path = SRC / "common" / "course.typ"
    text = path.read_text() if path.exists() else ""
    return set(re.findall(r"^#let (vv|mm|softmax)\b", text, flags=re.M))


def notation_macros(s: str, macros: set) -> str:
    """Course notation in one formula: `bb(E)` -> `EE` (Typst built-ins);
    with the course macros: bold vectors/matrices -> `vv(x)` / `mm(X)`,
    `"softmax"` -> `softmax`; and, with vv or mm, a transpose `^T` / `^(⊺)`
    of a bold symbol or a parenthesised group -> `^top` (a `^T` after a
    subscript group, as in `sum_(t = 1)^T`, is a bound and stays)."""
    s = re.sub(r"\bbb\(([EPR])\)", lambda m: m.group(1) * 2, s)
    if {"vv", "mm"} & macros:
        s = _bold_arg(s, r"upright\(bold\(|(?<![\w.])bold\(")
        s = s.replace("^(⊺)", "^top").replace("^⊺", "^top")
        out, i = [], 0
        for m in re.finditer(r"\)\^T(?![\w(])", s):
            if m.start() < i:
                continue
            # find the `(` of the group this `)` closes
            depth, j = 0, m.start()
            while j >= 0:
                if s[j] == ")":
                    depth += 1
                elif s[j] == "(":
                    depth -= 1
                    if depth == 0:
                        break
                j -= 1
            before = s[:j].rstrip(" ")
            if j >= 0 and before.endswith("_"):
                continue  # a subscript group: `^T` is a bound
            out.append(s[i : m.start() + 1])
            out.append("^top")
            i = m.end()
        out.append(s[i:])
        s = "".join(out)
    if "softmax" in macros:
        s = re.sub(r'upright\("softmax"\)|op\("softmax"\)|"softmax"', "softmax", s)
    return s


def tidy_math(typ: str) -> str:
    macros = course_macros()

    def fix(m):
        s = notation_macros(m.group(0), macros)
        for pat, rep in NOTATION:
            s = re.sub(pat, rep, s)
        s = unescape(s)
        # \big( … (pandoc: #scale(…)[(]): a plain delimiter, which Typst sizes
        # itself when it is paired; `#scale(…)[[]` would not even parse
        s = re.sub(
            r"#scale\(x: \d+%, y: \d+%\)\[(\\?[()\[\]|]|\w+)\]",
            lambda d: {"\\|": "||"}.get(d.group(1), d.group(1)).lstrip("\\"),
            s,
        )
        s = re.sub(r"\)(?=[A-Za-z0-9\"])", ") ", s)  # `)thin` -> `) thin`
        s = re.sub(r"\{ (.*?) \}", r"{\1}", s)
        s = re.sub(r"(?<=[\w)])\s*=\s*(?=\S)", " = ", s)
        return s

    return re.sub(r"(?<!\\)\$[^$]+\$", fix, typ)


def dashes(typ: str) -> str:
    """`---`/`--` -> `—`/`–` outside code and maths: Touying reads a top-level
    `---` as a slide separator."""
    parts = re.split(
        r"(```.*?```|`[^`\n]*`|(?<!\\)\$[^$]*\$|(?m:^//[^\n]*$))", typ, flags=re.S
    )
    return "".join(
        p if i % 2 else p.replace("---", "\u2014").replace("--", "\u2013")
        for i, p in enumerate(parts)
    )


def meta_typst(mid: str, meta: dict) -> str:
    def val(v):
        if isinstance(v, str):
            return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(v, list):
            return (
                "(" + ", ".join(val(x) for x in v) + ("," if len(v) == 1 else "") + ")"
            )
        return str(v)

    fields = [f"  id: {val(mid)},"] + [f"  {k}: {val(v)}," for k, v in meta.items()]
    return "#module-meta(\n" + "\n".join(fields) + "\n)\n"


def convert(
    mid: str,
    src_dir: pathlib.Path,
    macros: str,
    deck: bool = False,
    backup: pathlib.Path | None = None,
):
    """Port module `mid` (<src>/<mid>/<mid>.mdx, or <src>/<dir>/<name>.mdx for
    `<dir>/<name>`) to modules/…; with `deck`, the lecture <src>/<mid>/<mid>.mdx
    to lectures/<mid>/<mid>.typ (lectures/<mid>.typ if it has no folder).
    With `backup`, the .mdx is then moved to <backup>/<modules|lectures>/…"""
    folder, name = mid.split("/") if "/" in mid else (mid, mid)
    src = src_dir / folder / f"{name}.mdx"
    if not src.exists():
        sys.exit(f"{mid}: no {src}")
    kind = "lectures" if deck else "modules"
    saved = backup / kind / folder / f"{name}.mdx" if backup else None
    if saved and saved.exists():
        sys.exit(f"{mid}: {saved} exists already (the backup is not overwritten)")
    # a deck with a folder of its own: its images go there too
    deck_dir = SRC / "lectures" / mid
    out_dir = deck_dir if deck and deck_dir.is_dir() else SRC / "modules" / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    meta, md = preprocess(src.read_text(), out_dir, name, src.parent)
    run = subprocess.run(
        [
            "pandoc",
            "-f",
            "markdown-auto_identifiers+latex_macros+raw_attribute",
            "-t",
            "typst",
            "--wrap=preserve",
            "--lua-filter",
            str(HERE / "mdx2typ.lua"),
        ],
        input=macros + "\n\n" + md,
        env={**os.environ, "MDX_CLASSES": json.dumps(CLASSES), "MDX_MACROS": macros},
        capture_output=True,
        text=True,
    )
    if run.returncode:
        sys.exit(f"{mid}: pandoc failed:\n{run.stderr}")
    if "Could not convert TeX math" in run.stderr:
        print(f"{mid}: {run.stderr.strip()}", file=sys.stderr)
    typ = number_steps(run.stdout)
    typ = math_carriers(typ)
    typ = tidy_math(typ)
    typ = dashes(typ)
    typ = space_slides(typ)
    typ = re.sub(r"\n\n+\]", "\n]", typ)  # no blank line before a closing ]
    # a wrapper around one short line of text on one line: #dt[term]
    typ = re.sub(
        r"(#[\w.-]+(?:\([^()\n]*\))?)\[\n([^\n\[\]]*)\n\]",
        lambda m: (
            f"{m.group(1)}[{m.group(2)}]"
            if len(m.group(1)) + len(m.group(2)) < 78
            else m.group(0)
        ),
        typ,
    )
    origin = f"// Ported from {src} by tools/mdx2typ.py.\n"
    if deck:

        def info(key):
            return f"  {key}: [{meta[key]}],\n" if key in meta else ""

        out = (
            origin + f'#import "{SRC_PREFIX}common/course.typ": *\n\n'
            "#show: course-theme.with(config-info(\n"
            + info("title")
            + info("author")
            + info("date")
            + "))\n\n"
            + typ.lstrip()
            + f'\n#place(hide(bibliography("/{course_bib()}", style: bib-style, title: none)))\n'
        )
        # lectures/<mid>/<mid>.typ when the deck has a folder, else lectures/<mid>.typ
        if out_dir == deck_dir:
            path = deck_dir / f"{mid}.typ"
        else:
            path = SRC / "lectures" / f"{mid}.typ"
            path.parent.mkdir(exist_ok=True)
            if not any(out_dir.iterdir()):
                out_dir.rmdir()
    else:
        out = (
            origin
            + f'#import "{SRC_PREFIX}common/course.typ": *\n\n'
            + meta_typst(name, meta)
            + "\n"
            + typ
        )
        path = out_dir / f"{name}.typ"
    path.write_text(out)
    # indented by typstyle (the Typst formatter), when installed
    if shutil.which("typstyle"):
        subprocess.run(["typstyle", "-i", str(path)], check=False)
    print(f"{mid}: {path}", file=sys.stderr)
    if saved:
        saved.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, saved)
        print(f"{mid}: {src} -> {saved}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    global BIB
    try:
        import json5  # noqa: F401
    except ImportError:
        sys.exit(
            "typst-slides convert: needs json5 (pip install 'typst-slides[convert]')"
        )
    if not shutil.which("pandoc"):
        sys.exit(
            "typst-slides convert: needs pandoc (https://pandoc.org/installing.html)"
        )
    ap = argparse.ArgumentParser(description="Port slide-app MDX modules to Typst.")
    ap.add_argument("--src", type=pathlib.Path)
    ap.add_argument(
        "--macros",
        type=pathlib.Path,
        default=pathlib.Path("../src/lectures/common/macros.tex"),
    )
    ap.add_argument(
        "--notation", type=pathlib.Path, default=SRC / "common/mdx-notation.json"
    )
    ap.add_argument(
        "--classes", type=pathlib.Path, default=SRC / "common/mdx-classes.json"
    )
    ap.add_argument(
        "--deck",
        action="store_true",
        help="convert lectures (default --src ../src/lectures)",
    )
    ap.add_argument(
        "--backup",
        type=pathlib.Path,
        help="move each converted .mdx there (<backup>/modules/… or <backup>/lectures/…)",
    )
    ap.add_argument("modules", nargs="+")
    args = ap.parse_args(argv)
    macros = ""
    if args.macros.exists():
        macros = "\n".join(
            line
            for line in args.macros.read_text().splitlines()
            if not line.lstrip().startswith("%")
        )
        # a macro that is one command and its argument (\vd = \mathbf{d}), as
        # a group: `\hat\vd` expands to `\hat{\mathbf{d}}`, which texmath reads
        macros = re.sub(
            r"(\\newcommand\{\\\w+\})\{(\\[A-Za-z]+\{[^{}]*\})\}", r"\1{{\2}}", macros
        )
    if args.notation.exists():
        NOTATION[:0] = [tuple(pair) for pair in json.loads(args.notation.read_text())]
    if args.classes.exists():
        CLASSES.update(json.loads(args.classes.read_text()))
    BIB = bib_index()
    src = args.src or pathlib.Path("../src/lectures" if args.deck else "../src/modules")
    for mid in args.modules:
        convert(mid, src, macros, deck=args.deck, backup=args.backup)
    return 0
