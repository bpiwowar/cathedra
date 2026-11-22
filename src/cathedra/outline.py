# ruff: noqa: T201
"""The structure of a deck: sections, sub-sections (modules) and slides, each
with its source location (file:line and the #include chain that got there).

Used by the deck build (Reveal grouping, the structure browser `T`, the edit
links `E`) and by `cathedra outline` (the tree of every deck of the
schedule, with slide counts and times).

Where things come from:
- one query on the compiled document, in document order: <page-marker>
  (every page: logical slide, kind, headings in force), <synopsis>,
  <module-meta> and <slide-type> (lib/slides.typ). The metadata are placed
  just before the page they belong to: a synopsis goes with the next
  (sub)section or the title slide (deck synopsis), a module-meta with the next
  sub-section, slide types with the next slide;
- source lines: a static scan of the deck file, following #include, for its
  headings, matched in order with the compiled slides (same level).
"""

from __future__ import annotations

import os
import re
import sys
import unicodedata
from pathlib import Path

from .paths import Course

# slide-app's built-in slide types
SLIDE_TYPES = {
    "todo": {"label": "work in progress", "icon": "🚧", "time": True},
    "optional": {"label": "optional", "icon": "◇", "time": True},
    "practical": {"label": "practical", "icon": "💻", "time": False},
    "details": {"label": "in detail", "icon": "🔍", "time": False},
}

# the labels of the structure query, in document order
SELECTOR = "selector(<page-marker>).or(<synopsis>).or(<module-meta>).or(<slide-type>)"
STRUCTURE_EXPR = f"query({SELECTOR}).map(x => x.value)"

_HEADING = re.compile(r"^(=+)(?:\s+(.*))?$")
_INCLUDE = re.compile(r'^\s*#include\s+"([^"]+)"')
_TITLE = re.compile(r"^\s*#title-slide\b")
_DETAILS = re.compile(r"^\s*#details\(")
_INCLUDE_ANY = re.compile(r'#include\s+"([^"]+)"')
_STRING = re.compile(r'"(?:[^"\\]|\\.)*"')


def _target(course: Course, name: str, file: Path) -> Path:
    if name.startswith("/"):
        return course.root / name.lstrip("/")
    return (file.parent / name).resolve()


def scan(
    course: Course,
    file: Path,
    chain: list | None = None,
    out: list | None = None,
    deferred: list | None = None,
) -> list[dict]:
    """Headings of `file` and of what it includes, in document order; the
    headings inside `#details[…]` come last (in the deck, they are in the "in
    detail" appendix), each group behind a `details: True` entry."""
    chain = chain or []
    out = [] if out is None else out
    top = deferred is None
    if deferred is None:
        deferred = []
    try:
        lines = Path(file).read_text().split("\n")
    except OSError:
        return out
    raw = False
    open_groups: list[dict] = []  # [{depth, out}]

    def sink():
        return open_groups[-1]["out"] if open_groups else out

    def include(name: str, here: dict) -> None:
        scan(
            course, _target(course, name, Path(file)), [here, *chain], sink(), deferred
        )

    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            raw = not raw
        if raw or line.startswith("//"):
            continue
        here = {"file": Path(file), "line": i + 1}
        if _DETAILS.match(line):
            group = {
                "depth": 0,
                "out": [
                    {"level": 2, "text": "", "details": True, **here, "chain": chain}
                ],
            }
            deferred.append(group["out"])
            open_groups.append(group)
        m = _HEADING.match(line.lstrip() if open_groups else line)
        if m:
            sink().append(
                {
                    "level": len(m.group(1)),
                    "text": m.group(2) or "",
                    **here,
                    "chain": chain,
                }
            )
        elif _TITLE.match(line):
            sink().append({"level": 0, "text": "", **here, "chain": chain})
        elif (m := _INCLUDE.match(line)) is not None:
            include(m.group(1), here)
        elif open_groups:
            for x in _INCLUDE_ANY.finditer(line):
                include(x.group(1), here)
        if open_groups:
            g = open_groups[-1]
            for ch in _STRING.sub("", line):
                if ch in "[(":
                    g["depth"] += 1
                elif ch in "])":
                    g["depth"] -= 1
            if g["depth"] <= 0 and re.search(r"[\])]", line):
                open_groups.pop()
    if top:
        for g in deferred:
            out.extend(g)
    return out


def includes(course: Course, file: Path, out: list | None = None) -> list[dict]:
    """Every `#include` of `file` and of what it includes."""
    out = [] if out is None else out
    try:
        lines = Path(file).read_text().split("\n")
    except OSError:
        return out
    for i, line in enumerate(lines):
        m = _INCLUDE.match(line)
        if not m or line.lstrip().startswith("//"):
            continue
        target = _target(course, m.group(1), Path(file))
        out.append({"file": target, "from": {"file": Path(file), "line": i + 1}})
        includes(course, target, out)
    return out


def duplicates(course: Course, decks: list[dict]) -> list[dict]:
    """The files included more than once by `decks` ([{id, file}]), most first."""
    by: dict[Path, list] = {}
    for d in decks:
        for inc in includes(course, d["file"]):
            by.setdefault(inc["file"], []).append({"deck": d["id"], **inc["from"]})
    found = [(f, lst) for f, lst in by.items() if len(lst) > 1]
    found.sort(key=lambda x: (-len(x[1]), str(x[0])))
    return [{"file": f, "list": lst} for f, lst in found]


def _norm(s: str | None) -> str:
    """Letters and digits only: markup and plain text compare."""
    s = re.sub(r"#[\w.-]+\[", "", s or "")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isalnum()).lower()


_LEVEL = {"title": 0, "section": 1, "subsection": 2, "slide": 3}


def _title_of(m: dict, info_title: str | None) -> str | None:
    kind = m["kind"]
    if kind == "slide":
        return m.get("h3")
    if kind == "subsection":
        return m.get("h2")
    if kind == "section":
        return m.get("h1")
    return info_title or "Title"


def deck_structure(  # noqa: C901
    course: Course,
    items: list,
    details_refs: list,
    deck_path: Path,
    title: str | None = None,
) -> tuple[list[dict], dict]:
    """-> (groups, outline)

    `items`: the values of the structure query (STRUCTURE_EXPR), in document
    order; `details_refs`: the values of <details-ref>.
    groups: consecutive pages of one logical slide (one Reveal <section> each),
    [{key, kind, pages}].
    outline: {title, synopsis, file, children: [node]}, node = {kind, title,
    g (group = leaf Reveal slide), slide, page, src: {file, line}, chain, types,
    synopsis, meta, children}. Files are relative to the project root.
    """
    markers = [x for x in items if isinstance(x, dict) and "kind" in x and "page" in x]

    groups: list[dict] = []
    for m in sorted(markers, key=lambda m: m["page"]):
        last = groups[-1] if groups else None
        # the pages of an allow-breaks slide (`cont` 0, 1…) are slides of their own
        cont = m.get("cont")
        if (
            last
            and last["key"] == m["slide"]
            and last["kind"] == m["kind"]
            and last.get("cont") == cont
        ):
            if m["page"] not in last["pages"]:
                last["pages"].append(m["page"])
        else:
            groups.append(
                {
                    "key": m["slide"],
                    "kind": m["kind"],
                    "pages": [m["page"]],
                    "cont": cont,
                }
            )
    g_of_page = {p: h for h, g in enumerate(groups) for p in g["pages"]}

    def rel(f) -> str:
        return os.path.relpath(f, course.root)

    statics = scan(course, Path(deck_path).resolve())
    state = {"j": 0, "prev": None}

    def locate(m: dict):
        level = _LEVEL[m["kind"]]
        title_ = _title_of(m, None)
        k = state["j"]
        card = m["kind"] == "subsection" and m.get("details")
        while k < len(statics) and (
            not statics[k].get("details")
            if card
            else statics[k]["level"] != level or statics[k].get("details")
        ):
            k += 1
        cand = statics[k] if k < len(statics) else None
        prev = state["prev"]
        if (
            m["kind"] == "slide"
            and prev
            and title_ == prev["title"]
            and cand
            and _norm(cand["text"]) != _norm(title_)
        ):
            return prev["src"]
        if not cand:
            return None
        state["j"] = k + 1
        return {
            "file": rel(cand["file"]),
            "line": cand["line"],
            "chain": [
                {"file": rel(c["file"]), "line": c["line"]} for c in cand["chain"]
            ],
        }

    outline: dict = {
        "title": title,
        "synopsis": None,
        "file": rel(Path(deck_path).resolve()),
        "children": [],
    }
    section = subsection = None
    pending_synopsis: list[str] = []
    pending_meta = None
    pending_types: list[str] = []
    seen: set[str] = set()

    for x in items:
        if isinstance(x, list):
            for t in x:
                if t not in pending_types:
                    pending_types.append(t)
            continue
        if not isinstance(x, dict):
            continue
        if "text" in x and "body" in x:
            pending_synopsis.append(str(x["text"]).strip())
            continue
        if "prereqs" in x:
            if pending_meta is None:
                pending_meta = x  # a slide with steps repeats its content
            continue
        key = f"{x['kind']}:{x['slide']}:{g_of_page.get(x['page'])}"
        if key in seen:
            prev = state["prev"]
            if x["kind"] == "slide" and prev:
                for t in pending_types:
                    if t not in prev["types"]:
                        prev["types"].append(t)
            pending_types = []
            continue
        seen.add(key)
        src = locate(x)
        node = {
            "kind": x["kind"],
            "title": _title_of(x, title),
            "g": g_of_page.get(x["page"]),
            "slide": x["slide"],
            "page": x["page"],
            "src": src and {"file": src["file"], "line": src["line"]},
            "chain": (src or {}).get("chain", []),
            "types": ["details"] if x.get("details") is not None else [],
            "details": x.get("details"),
            "children": [],
        }
        kind = x["kind"]
        if kind == "title":
            if pending_synopsis:
                outline["synopsis"] = " ".join(pending_synopsis)
            pending_synopsis = []
            outline["children"].append(node)
        elif kind == "section":
            node["synopsis"] = " ".join(pending_synopsis) or None
            pending_synopsis = []
            outline["children"].append(node)
            section, subsection = node, None
        elif kind == "subsection":
            node["synopsis"] = " ".join(pending_synopsis) or None
            node["meta"] = pending_meta
            pending_synopsis = []
            pending_meta = None
            (section or outline)["children"].append(node)
            subsection = node
        else:
            for t in pending_types:
                if t not in node["types"]:
                    node["types"].append(t)
            (subsection or section or outline)["children"].append(node)
            state["prev"] = node
        pending_types = []

    outline["lang"] = markers[0].get("lang") if markers else None
    details: dict = {}
    for m in markers:
        if (
            m["kind"] == "subsection"
            and m.get("details")
            and m["details"] not in details
        ):
            details[m["details"]] = {"g": g_of_page.get(m["page"]), "refs": []}
    for r in details_refs:
        d = details.get(r.get("id"))
        g = g_of_page.get(r.get("page"))
        if d is not None and g not in d["refs"]:
            d["refs"].append(g)
    outline["details"] = details
    return groups, outline


# ------------------------------------------------------------- statistics
def stats(node: dict) -> dict:
    """Slides, timed slides and per-type counts below `node` (slides only)."""
    s = {"slides": 0, "timed": 0, "types": {}}

    def walk(n: dict) -> None:
        if n.get("kind") == "slide":
            s["slides"] += 1
            if all(SLIDE_TYPES.get(t, {}).get("time") is not False for t in n["types"]):
                s["timed"] += 1
            for t in n["types"]:
                s["types"][t] = s["types"].get(t, 0) + 1
        for c in n.get("children") or []:
            walk(c)

    walk(node)
    return s


def parse_duration(d) -> int | None:
    """ "2h", "2h30", "150", "150m", 150 -> minutes."""
    if d is None:
        return None
    if isinstance(d, (int, float)):
        return int(d)
    m = re.match(r"^\s*(?:(\d+)\s*h\s*(\d+)?|(\d+)\s*m?)\s*$", str(d))
    if not m:
        return None
    if m.group(3):
        return int(m.group(3))
    return int(m.group(1)) * 60 + (int(m.group(2)) if m.group(2) else 0)


def _js_num(v: float) -> str:
    """A number as JavaScript prints it (7, 7.5)."""
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def fmt_minutes(minutes: float) -> str:
    if minutes >= 60:
        rest = _js_num(minutes % 60)
        return f"{int(minutes // 60)}h{rest.rjust(2, '0')}"
    return f"{_js_num(minutes)} min"


# -------------------------------------------------------------------- CLI
def compile_outlines(course: Course, decks: list[dict], jobs: int = 0) -> list[tuple]:
    """The outlines of `decks` ([{id, file, title?…}]), compiled as handouts
    (`handout=1`: one page per slide instead of one per step, the same
    structure for a fraction of the layout), in parallel threads (typst
    releases the GIL; its memoization is shared, so common modules are laid
    out once). -> [(deck, outline)] in `decks` order (failed decks left out)."""
    from concurrent.futures import ThreadPoolExecutor

    from .engine import DeckCompiler

    def one(d: dict):
        comp = DeckCompiler(course, d["file"], {"handout": "1"}).compile()
        if not comp.ok:
            print(
                f"{d['id']}: does not compile (`cathedra build {course.rel(d['file'])}` shows why)",
                file=sys.stderr,
            )
            return None
        _, outline = deck_structure(
            course,
            comp.query(SELECTOR),
            comp.query("<details-ref>"),
            d["file"],
            d.get("title"),
        )
        return (d, outline)

    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        results = list(ex.map(one, decks))
    return [r for r in results if r]


def schedule_decks(course: Course, args: list[str]) -> list[dict]:
    """The decks of the schedule ($SLIDES_SCHEDULE) that have a file, or every
    deck; `args` (ids or .typ files) select some."""
    from .paths import schedule

    sched = schedule()
    lectures = sched.get("lectures") if sched else None
    if lectures is None:
        lectures = [{"id": i} for i in course.deck_ids()]
    decks = [
        {**lec, "file": course.deck_path(lec["id"])}
        for lec in lectures
        if lec.get("id") and course.deck_path(lec["id"])
    ]
    if args:
        decks = []
        for a in args:
            f = course.resolve_deck(a)
            i = f.stem
            lec = next((x for x in lectures if x.get("id") == i), {"id": i})
            decks.append({**lec, "file": f})
    return decks


def print_duplicates(course: Course, decks: list[dict]) -> None:
    found = duplicates(course, decks)
    out = [
        f"Files included more than once ({len(found)}), in "
        + ", ".join(d["id"] for d in decks)
    ]
    if not found:
        out.append("  none: every file is included once")
    for item in found:
        ds = {i["deck"] for i in item["list"]}
        where = f"in {next(iter(ds))}" if len(ds) == 1 else f"across {len(ds)} decks"
        out.append(f"\n{course.rel(item['file'])}  ({len(item['list'])}× {where})")
        for i in item["list"]:
            out.append(f"  {i['deck']:<14} {course.rel(i['file'])}:{i['line']}")
    print("\n".join(out))


def _row(label: str, node: dict, rate: float, width: int = 64) -> str:
    s = stats(node)
    time = s["timed"] * rate
    label = label[: width - 1] + "…" if len(label) > width else label.ljust(width)
    badges = " ".join(
        f"{SLIDE_TYPES.get(t, {}).get('icon', '•')}{n}" for t, n in s["types"].items()
    )
    return f"{label}{s['slides']:>4}  {fmt_minutes(time):>7}  {badges}".rstrip()


def print_outlines(results: list[tuple], rate: float, show_slides: bool) -> None:  # noqa: C901
    w = 64
    print(f"Deck outline (Typst) — {len(results)} deck(s), in course.yaml order")
    print(
        f"Legend: § section · sub-section (+ its file)   right: slides, time at {rate:g} min/slide,"
    )
    print(
        "        "
        + ", ".join(
            f"{v['icon']}N {v['label']}{'' if v['time'] else ' (not timed)'}"
            for v in SLIDE_TYPES.values()
        )
    )
    total = 0

    def loc(n: dict) -> str:
        return f"{n['src']['file']}:{n['src']['line']}" if n.get("src") else "?"

    def slide_rows(n: dict, indent: str) -> None:
        if not show_slides:
            return
        for c in n["children"]:
            if c["kind"] != "slide":
                continue
            badges = "".join(
                SLIDE_TYPES.get(t, {}).get("icon", "•") for t in c["types"]
            )
            title = (c.get("title") or "(untitled)")[:46]
            print(f"{indent}{c['g']:>3}  {title:<47}{badges:<3} {loc(c)}")

    for deck, outline in results:
        s = stats(outline)
        time = s["timed"] * rate
        total += time
        print("\n" + "─" * (w + 16))
        print(
            f"{deck['id']}{'  (dev only)' if deck.get('dev') else ''} — {deck.get('title') or ''}"
        )
        print(f"  {outline['file']}")
        todo = (
            f" · 🚧 {s['types']['todo']} still marked todo"
            if s["types"].get("todo")
            else ""
        )
        untimed = (
            f" · {s['slides'] - s['timed']} more not timed"
            if s["slides"] - s["timed"]
            else ""
        )
        print(
            f"  {s['timed']} slides in the linear flow ({fmt_minutes(time)}){untimed}{todo}"
        )
        target = parse_duration(deck.get("target"))
        if target is not None:
            gap = time - target
            state = "over" if gap > 0 else "under" if gap < 0 else "on target"
            print(
                f"  target {deck['target']} — main flow {'+' if gap > 0 else ''}{_js_num(gap)} min ({state})"
            )
        syn = " ".join((outline.get("synopsis") or "").split())
        if syn:
            print(f"  {syn[: 2 * w]}{'…' if len(syn) > 2 * w else ''}")
        print("")
        top = {
            "kind": "deck",
            "children": [n for n in outline["children"] if n["kind"] == "slide"],
            "types": [],
        }
        if top["children"]:
            print(_row("  (deck level, outside any section)", top, rate))
        slide_rows(top, "      ")
        for sec in (n for n in outline["children"] if n["kind"] == "section"):
            print(_row(f"  § {sec['title']}", sec, rate))
            slide_rows(sec, "        ")
            for sub in (n for n in sec["children"] if n["kind"] == "subsection"):
                meta = sub.get("meta") or {}
                declared = (
                    f"  (module says {meta['minutes']} min)"
                    if meta.get("minutes") is not None
                    else ""
                )
                print(_row(f"     · {sub['title']}", sub, rate) + declared)
                print(f"        + {(sub.get('src') or {}).get('file', '?')}")
                slide_rows(sub, "          ")
    if len(results) > 1:
        print(f"\nTotal: {fmt_minutes(total)}")
