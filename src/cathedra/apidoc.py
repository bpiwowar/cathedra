"""The API index of the engine's Typst files (docs/api.md in the help, H).

Every top-level `#let` of lib/*.typ and templates/*.typ, its signature and
the comment block right above it (no blank line in between). A banner comment
(`// ---- name`) starts a group; the first comment block of a file, followed
by a blank line, describes the file. Names starting with `_` are private.

Doc comments in tidy's style (`///`, as tinymist shows them on hover) are
parsed by tidy itself (apidoc.typ, compiled in-process): a description, one
`///` comment above each parameter, `-> type` for the types; they give the
parameter list. Plain `//` comments are the description alone. Without tidy
(e.g. offline on the first build), every comment is read as plain text.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from .paths import TYPST

TIDY_DRIVER = Path(__file__).with_name("apidoc.typ")

API_SOURCES = ["lib", "templates"]
_BANNER = re.compile(r"^//\s*-{4,}\s*(.*)$")
_LET = re.compile(r"^#let\s+([\w-]+)(\(|\s*=)")


def api_files(engine: Path = TYPST) -> list[str]:
    """The Typst files documented, relative to the engine."""
    out = [f"lib/{f.name}" for f in sorted((engine / "lib").glob("*.typ"))]
    # the templates: one directory (a package) each
    for d in sorted(p for p in (engine / "templates").iterdir() if p.is_dir()):
        out += [f"templates/{d.name}/{f.name}" for f in sorted(d.glob("*.typ"))]
    return out


def _closing(text: str, i: int) -> int:
    """From text[i] == "(", the index after the matching ")"."""
    depth = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            i += 1
            while i < len(text) and text[i] != '"':
                if text[i] == "\\":
                    i += 1
                i += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def _prose(lines: list[str]) -> str:
    """Comment lines -> markdown: prose joined into paragraphs, lines indented
    after `//` kept as a code block, except a list item's continuation lines
    (indented by two spaces right below it)."""
    out = []
    code = False
    item = False
    for raw in lines:
        line = re.sub(r"^///? ?", "", raw)
        if line.strip() == "":
            item = False
        elif not code and re.match(r"^\s?[-+] \S", line):
            item = True
        indented = bool(re.match(r"^\s{2,}\S", line)) and not (
            item and re.match(r"^ {2}\S", line)
        )
        if indented != code:
            out.append("\n```\n" if indented else "```\n")
            code = indented
        if not code and re.match(r"^\s?[-+] \S", line):
            out.append("\n")
        if code:
            out.append(line + "\n")
        elif line.strip() == "":
            out.append("\n\n")
        else:
            out.append(line.strip() + " ")
    if code:
        out.append("```\n")
    return re.sub(r" +\n", "\n", "".join(out)).strip()


def tidy_docs(sources: dict[str, str]) -> dict[str, dict[str, dict]]:
    """{file: {name: tidy's entry of that function or variable}} for the
    `///` doc comments of `sources` ({file: its text}); {} (with a warning)
    if tidy cannot run."""
    from .engine import query_file

    try:
        modules = query_file(TIDY_DRIVER, "<api>", sources)
    except Exception as e:  # no network for the package, a parse error…
        print(f"API index: tidy failed, plain comments only ({e})", file=sys.stderr)  # noqa: T201
        return {}
    out: dict[str, dict[str, dict]] = {}
    for m in modules:
        mod = m["module"]
        entries = {v["name"]: v for v in mod.get("variables", [])}
        entries.update({f["name"]: f for f in mod.get("functions", [])})
        out[m["file"]] = entries
    return out


def _types(types: list[str] | None) -> str:
    return " | ".join(types or [])


def _tidy_text(text: str) -> str:
    """A tidy description (lines as written after `///`) -> markdown."""
    return _prose(["//" + line for line in text.split("\n")])


def _tidy_api(entry: dict) -> list[str]:
    """The description, parameters and result of a tidy entry."""
    out = []
    if entry.get("description", "").strip():
        out.append(_tidy_text(entry["description"]))
    params = []
    for name, arg in (entry.get("args") or {}).items():
        desc = arg.get("description", "").strip()
        types = _types(arg.get("types"))
        if not desc and not types:
            continue
        head = f"- `{name}`"
        if types:
            head += f" `{types}`"
        if "default" in arg:
            head += f" (default `{arg['default']}`)"
        params.append(head + (": " + _tidy_text(desc) if desc else ""))
    if params:
        out.append("**Parameters**\n\n" + "\n".join(params))
    result = _types(
        entry.get("return-types") or ([entry["type"]] if entry.get("type") else None)
    )
    if result:
        out.append(f"**Result** `{result}`")
    return out


def _signature(name: str, text: str) -> str:
    """`name(…)` from the source from its "(", on one line, without the
    comments (the `///` of the parameters)."""
    start = text.index("(")
    params = text[start : _closing(text, start)]
    params = re.sub(r"(?m)^\s*//.*\n?", "", params)
    sig = re.sub(r"\s*\n\s*", " ", params)
    return name + re.sub(r",\s*\)$", ")", re.sub(r"^\(\s+", "(", sig))


def _file_api(
    rel: str, src: str, heading: str | None = None, tidy: dict | None = None
) -> str:
    tidy = tidy or {}
    lines = src.split("\n")
    out = [f"## {heading or rel}"]
    comment: list[str] = []
    intro = True
    for i, line in enumerate(lines):
        m = _BANNER.match(line)
        if m:
            comment = []
            intro = False
            if m.group(1).strip():
                out.append(f"### {m.group(1).strip()}")
            continue
        if line.startswith("//"):
            comment.append(line)
            continue
        if line.strip() == "":
            if intro and comment:
                out.append(_prose(comment))
            intro = False
            comment = []
            continue
        m = _LET.match(line)
        if m and not m.group(1).startswith("_"):
            intro = False
            name = m.group(1)
            if m.group(2) == "(":
                sig = _signature(name, "\n".join(lines[i:]))
            else:
                value = line[line.index("=") + 1 :].strip()
                short = len(value) <= 70 and not value.endswith(("(", "{"))
                sig = f"{name} = {value}" if short else name
            out += [f"#### {name}", "```typst\n#" + sig + "\n```"]
            if name in tidy and any(c.startswith("///") for c in comment):
                out += _tidy_api(tidy[name])
            elif comment:
                # (without tidy, `///` comments as text, less the `-> type`)
                out.append(
                    _prose([c for c in comment if not re.match(r"^///\s*->", c)])
                )
            out.append(f"*{rel}:{i + 1}*")
            comment = []
            continue
        intro = False
        comment = []
    return "\n\n".join(out)


def api_markdown(
    engine: Path = TYPST, course: Path | None = None, root: Path | None = None
) -> str:
    """docs/api.md: the API index of the engine's Typst files, then of the
    course's common/*.typ when `course` (its sources' directory) is given."""
    root = root or course
    common = course / "common" if course else None
    if root and common:
        course_typ = "/" + Path(os.path.relpath(common / "course.typ", root)).as_posix()
    else:
        course_typ = "/common/course.typ"
    own = (
        sorted(p.name for p in common.glob("*.typ"))
        if common and common.is_dir()
        else []
    )
    sources = {f: (engine / f).read_text() for f in api_files(engine)}
    sources.update({f"common/{f}": (common / f).read_text() for f in own})  # type: ignore[operator]
    tidy = tidy_docs(sources)
    parts = [
        "# API index",
        f'Everything the engine\'s Typst files define (`#import "{course_typ}": *` '
        "brings it in scope), generated from the comments above each `#let`"
        + (", then what the course's `common/` adds" if own else "")
        + ". Type a name in the search box (/) to find it.",
        *(_file_api(f, sources[f], tidy=tidy.get(f)) for f in api_files(engine)),
        *(
            _file_api(
                f"common/{f}",
                sources[f"common/{f}"],
                f"common/{f} (the course)",
                tidy.get(f"common/{f}"),
            )
            for f in own
        ),
    ]
    return "\n\n".join(parts) + "\n"
