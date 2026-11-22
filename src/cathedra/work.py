"""Writes a slide's work state (`#todo(…)` / `#to-check(…)` / none) into
its Typst source.

Used by the dev server (POST /work, from the viewer: a click on the note,
shift-W, or S in the W list; see docs/slide-types.md). The slide is the
lines from its heading (the outline's `src.line`) to the next outline entry
of the same file:

- a marker there is replaced (its note kept unless a new one is given), or
  removed (state "none", with its line when it is alone on it);
- with none, the new marker goes on the line after the heading.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .annot import _parse_args

STATES = {"todo": "todo", "check": "to-check"}
_MARKER = re.compile(r"#(todo|to-check)\s*\(")


@dataclass
class Marker:
    start: int  # the `#`
    end: int  # after the `)`
    line: int  # 1-based
    kind: str  # "todo" / "check"
    arg: str  # the argument's source text, stripped ("" when none)


def find_markers(src: str) -> list[Marker]:
    """Every `#todo(…)` / `#to-check(…)` call of `src`."""
    out = []
    for m in _MARKER.finditer(src):
        parsed = _parse_args(src, m.end() - 1)
        if not parsed:
            continue
        _, close = parsed
        out.append(
            Marker(
                m.start(),
                close + 1,
                src.count("\n", 0, m.start()) + 1,
                "todo" if m.group(1) == "todo" else "check",
                src[m.end() : close].strip().rstrip(",").strip(),
            )
        )
    return out


def _string(note: str) -> str:
    return '"' + note.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _line_span(src: str, start: int, end: int) -> tuple[int, int]:
    """[start, end) widened to whole lines when nothing else is on them."""
    a = src.rfind("\n", 0, start) + 1
    b = src.find("\n", end)
    b = len(src) if b < 0 else b + 1
    if src[a:start].strip() == "" and src[end:b].strip() == "":
        return a, b
    return start, end


def set_work_state(
    src: str, start: int, end: float, state: str, note: str | None = None
) -> tuple[str, int | None] | str:
    """`src` with the slide of lines [`start`, `end`) set to `state`
    ("todo", "check" or "none") and the line of its marker (None when
    removed); `note` None keeps the current one. An error message otherwise."""
    if state not in STATES and state != "none":
        return f"unknown state {state!r}"
    markers = [m for m in find_markers(src) if start <= m.line < end]
    if state == "none":
        if not markers:
            return src, None
        for m in sorted(markers, key=lambda m: -m.start):
            a, b = _line_span(src, m.start, m.end)
            src = src[:a] + src[b:]
        return src, None
    arg = _string(note) if note else ("" if note == "" else None)
    if markers:
        first, rest = markers[0], markers[1:]
        if arg is None:
            arg = first.arg
        for m in sorted(rest, key=lambda m: -m.start):
            a, b = _line_span(src, m.start, m.end)
            src = src[:a] + src[b:]
        text = f"#{STATES[state]}({arg})"
        return src[: first.start] + text + src[first.end :], first.line
    # no marker: after the heading line
    lines = src.split("\n")
    if start > len(lines):
        return f"line {start} is past the end of the file"
    lines.insert(start, f"#{STATES[state]}({arg or ''})")
    return "\n".join(lines), start + 1
