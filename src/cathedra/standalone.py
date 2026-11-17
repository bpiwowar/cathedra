"""Whether plain `typst compile` compiles a deck from a clone of the course.

The engine's Typst world is the typst CLI's (same packages, same fonts, plus
the engine's fonts/): what cathedra adds is generated data (lib/,
.cache/), read only when cathedra compiles (`generated` in
lib/slides.typ). A deck must compile without it, from the files git keeps:
`plain_problems` compiles it as the typst CLI would (no `cathedra`
input) and lists what goes wrong, an error or a file read that git ignores
(a clone would not have it). The engine itself (`cathedra`, a link or a
submodule; a Typst Universe package one day) is not the course's.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .engine import DeckCompiler
from .paths import Course, engine_dir


def ignored(root: Path, files: list[Path]) -> list[Path]:
    """The files git ignores and does not track (none outside a git work tree)."""
    if not files:
        return []
    try:
        r = subprocess.run(
            ["git", "check-ignore", "--stdin"],
            cwd=root,
            input="\n".join(str(f) for f in files),
            capture_output=True,
            text=True,
        )
    except OSError:
        return []
    if r.returncode not in (0, 1):  # 128: not a git repository
        return []
    return [Path(line) for line in r.stdout.splitlines() if line]


def plain_problems(course: Course, deck: Path) -> list[str]:
    comp = DeckCompiler(course, deck, plain=True).compile()
    name = course.rel(deck)
    if not comp.ok:
        first = next((d for d in comp.diagnostics if d.severity == "error"), None)
        msg = first.message if first else "error"
        return [f"{name}: plain `typst compile` fails: {msg}"]
    engine = engine_dir(course.root)
    mine = []
    for p in comp.dependencies:
        p = Path(p)
        if p.is_relative_to(course.root) and not p.is_relative_to(engine):
            mine.append(p.relative_to(course.root))
    return [
        f"{name}: reads {f}, which git ignores: a clone could not compile it "
        "with plain `typst compile` (commit it, or read it only when "
        "`generated`, docs/building.md)"
        for f in ignored(course.root, sorted(mine))
    ]
