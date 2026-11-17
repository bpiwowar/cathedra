# ruff: noqa: T201
"""Space out the slides of Typst deck/module files for human readers.

Two blank lines before a slide (`===`), three before a section or sub-section
(`=`, `==`), one after any heading. `//` comment lines right above a heading
move with it. Raw blocks (```) are left alone. Idempotent.

    typst-slides space modules/*/*.typ lectures/*.typ

Also used by `typst-slides convert` on its output.
"""

import re
import sys
from pathlib import Path

HEADING = re.compile(r"^(=+)\s")
BEFORE = {1: 3, 2: 3, 3: 2}


def space_slides(typ: str) -> str:
    lines = typ.split("\n")
    out: list[str] = []
    in_raw = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_raw = not in_raw
        m = None if in_raw else HEADING.match(line)
        if not m:
            # one blank line after a heading
            if out and HEADING.match(out[-1]) and line.strip() and not in_raw:
                out.append("")
            out.append(line)
            continue
        # the heading's attached comments, then the blank lines before them
        attached = []
        while out and out[-1].startswith("//"):
            attached.insert(0, out.pop())
        while out and not out[-1].strip():
            out.pop()
        if out:  # not at the start of the file
            out.extend([""] * BEFORE.get(len(m.group(1)), 2))
        out.extend(attached)
        out.append(line)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    for name in sys.argv[1:] if argv is None else argv:
        path = Path(name)
        src = path.read_text()
        new = space_slides(src)
        if new != src:
            path.write_text(new)
            print(f"spaced {path}")


if __name__ == "__main__":
    main()
