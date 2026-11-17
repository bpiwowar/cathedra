# ruff: noqa: T201
"""Migrate a Typst course's sources to the engine's current API level.

Usage (from the course's typst directory, normally through `make migrate`):

    typst-slides migrate [--dry-run] [--course DIR]

The engine's API level is `typst/VERSION`; the level a course is migrated to
is recorded in `<course>/.slide-app-version` (missing = 1). Every pending
migration is applied to the `.typ` files of the course (not `slide-app/`,
`out/`, `.cache/`), then the version file is written. `--dry-run` prints a
unified diff and writes nothing. Idempotent. See docs/upgrading.md.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import textwrap
from pathlib import Path

ENGINE = Path(__file__).resolve().parent / "typst"  # VERSION
VERSION_FILE = ".slide-app-version"
SKIP_DIRS = {"slide-app", "out", ".cache", "node_modules", ".git"}

Skipped = list  # of (offset in the text, message)


def match(s: str, i: int) -> int:
    """Index of the bracket closing the one at s[i], skipping strings."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = [pairs[s[i]]]
    j = i + 1
    while j < len(s):
        c = s[j]
        if c == '"':
            j += 1
            while s[j] != '"':
                j += 2 if s[j] == "\\" else 1
        elif c in pairs:
            stack.append(pairs[c])
        elif c == stack[-1]:
            stack.pop()
            if not stack:
                return j
        j += 1
    raise ValueError("unbalanced")


def split_top(args: str) -> list[str]:
    """Split on top-level commas."""
    out, depth, cur, k = [], 0, "", 0
    while k < len(args):
        c = args[k]
        if c == '"':
            e = k + 1
            while args[e] != '"':
                e += 2 if args[e] == "\\" else 1
            cur += args[k : e + 1]
            k = e + 1
            continue
        if c in "([{":
            depth += 1
        if c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += c
        k += 1
    if cur.strip():
        out.append(cur)
    return out


def safe(fn):
    """A migration must not die on unbalanced input: report it as skipped."""

    def wrapper(s, path):
        try:
            return fn(s, path)
        except (ValueError, IndexError) as e:
            return s, 0, [(0, f"{fn.__name__}: could not parse ({e})")]

    wrapper.__name__ = fn.__name__
    return wrapper


# ---------------------------------------------------------------- level 2


@safe
def img_caption_to_figure(s: str, path: Path):
    """#img(…, caption: […]) -> #figure(img(…), caption: […])"""
    out, i, n = "", 0, 0
    for m in re.finditer(r"(?<![\w-])(#?)img\(", s):
        if m.start() < i:
            continue
        o = m.end() - 1
        c = match(s, o)
        args = split_top(s[o + 1 : c])
        cap = [a for a in args if re.match(r"\s*caption\s*:", a)]
        if not cap:
            continue
        rest = [a for a in args if a not in cap]
        capv = re.sub(r"^\s*caption\s*:\s*", "", cap[0]).strip()
        restv = ", ".join(a.strip() for a in rest)
        out += s[i : m.start()] + f"{m.group(1)}figure(img({restv}), caption: {capv})"
        i = c + 1
        n += 1
    return out + s[i:], n, []


def _frag_pairs(s: str):
    """#frag(N)[#dt[T]] #frag(M)[#dd[B]] -> #frag(N)[/ T: #frag(M)[B]]"""
    out, i, n = "", 0, 0
    pat = re.compile(r"(?m)^([ \t]*)#frag\(([^)]*)\)\[")
    while True:
        m = pat.search(s, i)
        if not m:
            break
        ind = m.group(1)
        o = m.end() - 1
        c = match(s, o)
        inner = s[o + 1 : c].strip()
        dm = re.fullmatch(r"#dt(?:\(above:\s*([\d.]+em)\))?\[(.*)\]", inner, re.S)
        gap = re.match(r"[ \t]*\n(?:[ \t]*\n)*", s[c + 1 :]) if dm else None
        m2 = pat.match(s, c + 1 + gap.end()) if gap else None
        if not (dm and m2):
            out += s[i : o + 1]
            i = o + 1
            continue
        o2 = m2.end() - 1
        c2 = match(s, o2)
        bm = re.fullmatch(r"#dd\[(.*)\]", s[o2 + 1 : c2].strip(), re.S)
        if not bm:
            out += s[i : o + 1]
            i = o + 1
            continue
        sp, term = dm.group(1), dm.group(2).strip().replace(":", "\\:")
        body = textwrap.dedent(bm.group(1).strip("\n")).rstrip()
        body = "\n".join(
            (ind + "      " + ln) if ln.strip() else "" for ln in body.split("\n")
        )
        # the spacing is set inside the block: a `#set` left open in a module
        # would style the rest of the file and make Touying add a page
        setrule = f"{ind}    #set terms(spacing: {sp})\n" if sp else ""
        out += (
            s[i : m.start()]
            + f"{ind}#frag({m.group(2)})[\n{setrule}{ind}  / {term}: "
            + f"#frag({m2.group(2)})[\n{body}\n{ind}  ]\n{ind}]"
        )
        i = c2 + 1
        n += 1
    return out + s[i:], n


@safe
def dt_dd_to_terms(s: str, path: Path):
    """#dt[term] #dd[desc] -> / term: desc (also split over two #frag blocks)"""
    skipped: Skipped = []
    s, n = _frag_pairs(s)
    out, i = "", 0
    group = False  # inside a `#[ #set terms(…) … ]` block
    pat = re.compile(r"(?m)^([ \t]*)#dt(\(above:\s*([\d.]+em)\))?\[")
    while True:
        m = pat.search(s, i)
        if not m:
            break
        ind, sp = m.group(1), m.group(3)
        o = m.end() - 1
        c = match(s, o)
        term = s[o + 1 : c].strip()
        m2 = re.compile(r"\s*#dd\[").match(s, c + 1)
        if not m2:
            skipped.append(
                (
                    len(out) + m.start() - i,
                    f"#dt[{term[:40]}] without a #dd right after",
                )
            )
            out += s[i : c + 1]
            i = c + 1
            continue
        o2 = m2.end() - 1
        c2 = match(s, o2)
        if re.compile(r"\s*#dd\[").match(s, c2 + 1):
            msg = f"#dt[{term[:40]}] followed by several #dd"
            skipped.append((len(out) + m.start() - i, msg))
            out += s[i : c2 + 1]
            i = c2 + 1
            continue
        body = s[o2 + 1 : c2]
        term_md = term.replace(":", "\\:")
        if "\n" in body.strip() or re.match(r"\s*([-+]|\d+\.)\s", body):
            lines = textwrap.dedent(body.strip("\n")).rstrip().split("\n")
            desc = "\n".join((ind + "  " + ln) if ln.strip() else "" for ln in lines)
            item = f"{ind}/ {term_md}:\n{desc}"
        else:
            item = f"{ind}/ {term_md}: {body.strip()}"
        # a spacing is set in a block around the group of consecutive items:
        # a `#set` left open in a module would style the rest of the file and
        # make Touying add a page
        prefix = ""
        if sp and not group:
            prefix = f"{ind}#[\n{ind}  #set terms(spacing: {sp})\n"
            group = True
        out += s[i : m.start()] + prefix + item
        if group:
            nxt = re.compile(rf"\s*#dt\(above:\s*{re.escape(sp or '')}\)\[").match(
                s, c2 + 1
            )
            if not nxt:
                out += f"\n{ind}]"
                group = False
        i = c2 + 1
        n += 1
    s = out + s[i:]
    left = len(re.findall(r"#(?:dt|dd)\b", s))
    if left:
        first = re.search(r"#(?:dt|dd)\b", s).start()
        skipped.append((first, f"{left} #dt/#dd remain in this file"))
    return s, n, skipped


@safe
def citation_to_quote(s: str, path: Path):
    """#citation(source: X)[…] -> #quote(block: true, attribution: X)[…]"""
    out, i, n = "", 0, 0
    for m in re.finditer(r"#citation(?=[(\[])", s):
        if m.start() < i:
            continue
        j = m.end()
        args = ""
        if s[j] == "(":
            c = match(s, j)
            args = s[j + 1 : c]
            j = c + 1
        if j >= len(s) or s[j] != "[":
            continue
        parts = split_top(args)
        new = ["block: true"]
        for a in parts:
            sm = re.match(r"\s*source\s*:\s*(.*)", a, re.S)
            new.append("attribution: " + sm.group(1).strip() if sm else a.strip())
        out += s[i : m.start()] + "#quote(" + ", ".join(new) + ")"
        i = j
        n += 1
    return out + s[i:], n, []


@safe
def ext_to_link(s: str, path: Path):
    """#ext(url)[…] -> #link(url)[…]"""
    return re.subn(r"#ext\(", "#link(", s) + ([],)


# ---------------------------------------------------------------- level 3

COURSE_DATA = """
// The course's generated data (typst-slides writes these files), given to
// the template: the reference links, the fetched images, the widgets'
// pictures (see `course-setup` in lib/slides.typ)
#let course-data = (
  ref-links: json("/lib/refs-links.json"),
  image-cache: json("/.cache/images/manifest.json"),
  widget-shots: json("/.cache/widgets/manifest.json"),
)
"""


@safe
def academic_package(s: str, path: Path):
    """templates/academic.typ -> templates/academic/academic.typ (the template
    is a package directory)"""
    return re.subn(r"(/templates/)academic\.typ\b", r"\1academic/academic.typ", s) + (
        [],
    )


@safe
def course_data(s: str, path: Path):
    """The course reads its generated data and gives it to the template: the
    engine no longer reads /lib/refs-links.json nor the manifests itself."""
    m = re.search(r"\bacademic\(", s)
    if not m or "course-data" in s or not re.search(r"#let[^=\n]*=\s*academic\(", s):
        return s, 0, []
    open_ = m.end() - 1
    close = match(s, open_)
    inner = s[open_ + 1 : close]
    stripped = inner.rstrip()
    sep = "" if not stripped.strip() or stripped.endswith(",") else ","
    indent = "  " if "\n" in inner else ""
    added = (
        f"{sep}\n{indent}data: course-data,\n"
        if "\n" in inner
        else f"{sep} data: course-data"
    )
    s = s[: open_ + 1] + stripped + added + s[close:]
    # the data, after the imports
    imports = list(re.finditer(r"(?m)^#import .*\n", s))
    at = imports[-1].end() if imports else 0
    s = s[:at] + COURSE_DATA + s[at:]
    return s, 1, []


# ------------------------------------------------------------ the registry
# {to_version: [(name, function(text, path) -> (text, count, skipped))]}
MIGRATIONS = {
    2: [
        ("img caption -> #figure", img_caption_to_figure),
        ("#dt/#dd -> term lists", dt_dd_to_terms),
        ("#citation -> #quote", citation_to_quote),
        ("#ext -> #link", ext_to_link),
    ],
    3: [
        ("templates/academic.typ -> templates/academic/", academic_package),
        ("course data given to the template", course_data),
    ],
}


# ------------------------------------------------------------------ driver


def course_version(course: Path) -> int:
    f = course / VERSION_FILE
    try:
        return int(f.read_text().strip())
    except (OSError, ValueError):
        return 1


def typ_files(course: Path):
    # the sources: $SLIDES_SRC, relative to the course directory
    src = course / os.environ.get("SLIDES_SRC", ".")
    for p in sorted(src.rglob("*.typ")):
        rel = p.relative_to(course).parts
        if not SKIP_DIRS.intersection(rel[:-1]):
            yield p


def line_of(s: str, off: int) -> int:
    return s.count("\n", 0, off) + 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--dry-run", action="store_true", help="print a diff, write nothing"
    )
    ap.add_argument("--course", default=".", help="the course's typst directory")
    ap.add_argument(
        "--check",
        action="store_true",
        help="only say whether the course is behind (exit 1)",
    )
    a = ap.parse_args(argv)
    course = Path(a.course).resolve()
    target = int((ENGINE / "VERSION").read_text().strip())
    have = course_version(course)
    if a.check:
        if have < target:
            print(f"course at API level {have}, engine at {target}: run `make migrate`")
        return 1 if have < target else 0
    if have > target:
        print(
            f"course is at API level {have}, newer than the engine's {target}: update slide-app"
        )
        return 1
    pending = [(v, MIGRATIONS[v]) for v in sorted(MIGRATIONS) if have < v <= target]
    if not pending:
        print(f"course already at API level {have}: nothing to migrate")
        return 0
    print(f"migrating {course.name}: API level {have} -> {target}")
    files = list(typ_files(course))
    totals: dict[str, int] = {}
    skipped_all: list[str] = []
    changed = 0
    for p in files:
        orig = text = p.read_text()
        rel = p.relative_to(course)
        notes = []
        for _v, migs in pending:
            for name, fn in migs:
                text, n, skipped = fn(text, p)
                if n:
                    notes.append(f"{name}: {n}")
                    totals[name] = totals.get(name, 0) + n
                for off, msg in skipped:
                    skipped_all.append(f"{rel}:{line_of(text, off)}: {msg}")
        if text != orig:
            changed += 1
            print(f"{rel}: " + ", ".join(notes))
            if a.dry_run:
                sys.stdout.writelines(
                    difflib.unified_diff(
                        orig.splitlines(True),
                        text.splitlines(True),
                        f"a/{rel}",
                        f"b/{rel}",
                    )
                )
            else:
                p.write_text(text)
    print(
        f"{changed} of {len(files)} files {'would change' if a.dry_run else 'changed'}"
    )
    for name, n in totals.items():
        print(f"  {name}: {n}")
    if skipped_all:
        print("skipped (left as is, the deprecated aliases still work; fix by hand):")
        for line in dict.fromkeys(skipped_all):
            print("  " + line)
    if not a.dry_run:
        (course / VERSION_FILE).write_text(f"{target}\n")
        print(
            f"wrote {VERSION_FILE} = {target}; check the decks (make check), then commit"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
