"""Writes a moved element annotation back into its Typst source.

Sets (or adds) `dx:`, `dy:`, `width:` on the `annot("<target>", …)` call.
Used by the dev server (POST /annot, from the viewer's shift-O editor; see
docs/annotations.md).

The call is found by its key, the target id (first argument) or its `id:`
when it has one, between the lines of its slide (from the outline); a small
scanner reads the arguments (strings, comments, nested brackets), so a call
written over several lines, or with other arguments, is fine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_IDENT = re.compile(r"[\w.-]")
_NAMED = re.compile(r"^([^\W\d][\w-]*)\s*:")
_STRING = re.compile(r'^"((?:[^"\\]|\\.)*)"$', re.S)


@dataclass
class Arg:
    start: int
    end: int
    name: str | None
    value_start: int


@dataclass
class Call:
    open: int
    close: int
    line: int
    target: str
    id: str | None
    key: str
    args: list[Arg] = field(default_factory=list)


def _skip_string(src: str, i: int) -> int:
    i += 1
    while i < len(src):
        if src[i] == "\\":
            i += 1
        elif src[i] == '"':
            return i + 1
        i += 1
    return i


def _skip_markup(src: str, i: int) -> int:
    depth = 0
    while i < len(src):
        c = src[i]
        if c == "\\":
            i += 1
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def _parse_args(src: str, open_: int) -> tuple[list[Arg], int] | None:
    args: list[Arg] = []
    depth = 0
    start = open_ + 1

    def push(end: int) -> None:
        s, e = start, end
        while True:
            while s < e and src[s].isspace():
                s += 1
            if src.startswith("//", s):
                while s < e and src[s] != "\n":
                    s += 1
            elif src.startswith("/*", s):
                k = src.find("*/", s)
                s = e if k < 0 else min(e, k + 2)
            else:
                break
        while e > s and src[e - 1].isspace():
            e -= 1
        if s < e:
            m = _NAMED.match(src[s:e])
            args.append(Arg(s, e, m.group(1) if m else None, s + m.end() if m else s))

    i = open_ + 1
    while i < len(src):
        c = src[i]
        if c == '"':
            i = _skip_string(src, i) - 1
        elif c == "/" and src[i + 1 : i + 2] == "/":
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c == "/" and src[i + 1 : i + 2] == "*":
            e = src.find("*/", i + 2)
            i = len(src) if e < 0 else e + 1
        elif c == "[":
            i = _skip_markup(src, i) - 1
        elif c in "({":
            depth += 1
        elif c in ")}":
            if depth == 0:
                push(i)
                return args, i
            depth -= 1
        elif c == "," and depth == 0:
            push(i)
            start = i + 1
        i += 1
    return None


def _string_value(src: str, a: Arg) -> str | None:
    m = _STRING.match(src[a.value_start : a.end].strip())
    return re.sub(r"\\(.)", r"\1", m.group(1)) if m else None


def find_annot_calls(src: str) -> list[Call]:
    """Every `annot(…)` call of `src` (`line` is 1-based; `key` = id or
    target, as in lib/slides.typ)."""
    calls = []
    for m in re.finditer(r"annot\s*\(", src):
        if m.start() > 0 and _IDENT.match(src[m.start() - 1]):
            continue  # my-annot(, annot-layer…
        open_ = m.end() - 1
        parsed = _parse_args(src, open_)
        if not parsed:
            continue
        args, close = parsed
        positional = [a for a in args if not a.name]
        target = _string_value(src, positional[0]) if positional else None
        id_arg = next((a for a in args if a.name == "id"), None)
        id_ = _string_value(src, id_arg) if id_arg else None
        if target is None:
            continue
        line = src.count("\n", 0, m.start()) + 1
        calls.append(Call(open_, close, line, target, id_, id_ or target, args))
    return calls


def set_annot_args(src: str, call: Call, values: dict[str, str]) -> str:
    """`src` with the named arguments `values` ({"dx": "12pt", …}) set on
    `call` (replaced where present, added at the end otherwise)."""
    edits: list[tuple[int, int, str]] = []
    added = []
    for name, value in values.items():
        a = next((x for x in call.args if x.name == name), None)
        if a:
            edits.append((a.value_start, a.end, " " + value))
        else:
            added.append(f"{name}: {value}")
    if added:
        i = call.close
        while i > call.open + 1 and src[i - 1].isspace():
            i -= 1
        comma = src[i - 1] == ","
        text = (" " + ", ".join(added) + ",") if comma else (", " + ", ".join(added))
        edits.append((i, i, text))
    for start, end, text in sorted(edits, key=lambda e: -e[0]):
        src = src[:start] + text + src[end:]
    return src


def pick_annot_call(
    src: str, key: str, start: int = 1, end: float = float("inf")
) -> Call | str:
    """The call with key `key` between lines `start` (inclusive) and `end`
    (exclusive), else the only one of the file; an error message otherwise."""
    every = [c for c in find_annot_calls(src) if c.key == key]
    in_slide = [c for c in every if start <= c.line < end]
    pool = in_slide or every
    if len(pool) == 1:
        return pool[0]
    if not pool:
        return f'no annot("{key}") call found'
    return (
        f'{len(pool)} annot calls with the key "{key}" on this slide: '
        'give them an id: (id: "…")'
    )
