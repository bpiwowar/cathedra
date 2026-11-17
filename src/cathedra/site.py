# ruff: noqa: T201
"""The course site: every deck of the schedule, its PDF, and the index page
that lists them (deck list, synopsis, outline, PDF and practical links). Run
from the course directory (makefile.mk does: `make site`, `site-pdf`,
`serve-course`, `deploy`…).

    cathedra site decks [--dev] [--pdf]       ids of the decks to build
    cathedra site build --out=DIR [--dev] [--static=DIR] [--practicals=FILE]
         the decks (DIR/<id>/), the static files, DIR/index.html
    cathedra site index --out=DIR [--dev] [--practicals=FILE]
         DIR/index.html alone (the decks' outlines from DIR/<id>/outline.json)
    cathedra site pdf --out=DIR [--dev] [--force]
         DIR/<id>.pdf of the decks with `pdf: true`, compiled again only when
         the MD5 of what they read changed (.cache/pdf/)
    cathedra site check --out=DIR    no local absolute path in DIR
    cathedra site serve [--port=9010] [--static=DIR …] [--practicals=FILE]
         dev server of the whole course: the index on /, each deck on /<id>/
         (its own dev server, started on the first request), DIR files else

The schedule is $SLIDES_SCHEDULE (YAML): `lectures: [{id, title, dev, pdf,
externalPdf, practicals, summary, target, timePerSlide}]`, plus optional
top-level `lang` (en, fr), `index` (wording overrides, e.g. `{practicals:
TP}`) and `timePerSlide` (minutes, 2 by default). A lecture is a deck when
lectures/<id>.typ exists; `externalPdf` (a path in the site) is only linked;
`dev: true` decks and practicals are in the dev site only. Without a
schedule, every lectures/*.typ is a deck. The practicals manifest: {baseUrl,
practicals: [{id, name, files: [{label, path, solution}]}], bundles: [{id,
path}]}.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .outline import compile_outlines, fmt_minutes, stats
from .paths import TYPST, Course, schedule as load_schedule

# ---------------------------------------------------------------- schedule


def schedule(course: Course) -> dict:
    sched = load_schedule()
    if not os.environ.get("SLIDES_SCHEDULE"):
        return {"lectures": [{"id": i, "title": i} for i in course.deck_ids()]}
    return {**sched, "lectures": sched.get("lectures") or []}


def is_deck(course: Course, lec: dict) -> bool:
    return (
        bool(lec.get("id"))
        and not lec.get("externalPdf")
        and course.deck_path(lec["id"]) is not None
    )


def entries(sched: dict, dev: bool = False) -> list[dict]:
    """The lectures the site lists (dev ones only in the dev site)."""
    return [lec for lec in sched["lectures"] if dev or not lec.get("dev")]


def deck_ids(
    course: Course, sched: dict, dev: bool = False, pdf: bool = False
) -> list[str]:
    out = []
    for lec in entries(sched, dev):
        if lec.get("id") and not lec.get("externalPdf") and not is_deck(course, lec):
            print(
                f"[site] {lec['id']}: no lectures/{lec['id']}.typ, left out",
                file=sys.stderr,
            )
        if is_deck(course, lec) and (not pdf or lec.get("pdf") is True):
            out.append(lec["id"])
    return out


# ------------------------------------------------------------------ wording
STRINGS = {
    "en": {
        "title": "Lectures & Practicals",
        "lectures": "Lectures",
        "practicals": "Practicals",
        "optional": "optional",
        "outline": "Outline",
        "expandAll": "Show the full synopsis",
        "collapseAll": "Hide the synopsis",
    },
    "fr": {
        "title": "Cours et travaux pratiques",
        "lectures": "Cours",
        "practicals": "Travaux pratiques",
        "optional": "optionnel",
        "outline": "Plan",
        "expandAll": "Afficher le synopsis complet",
        "collapseAll": "Masquer le synopsis",
    },
}


def esc(t) -> str:
    return html.escape("" if t is None else str(t), quote=True).replace("&#x27;", "'")


# ---------------------------------------------------------------- practicals
def read_practicals(file: Path | None) -> tuple[dict, list]:
    """id -> practical (links resolved against the manifest's baseUrl), and
    the bundles."""
    if not file:
        return {}, []
    if not file.exists():
        print(
            f"[site] no practicals manifest at {file}: run 'make practical-manifest'",
            file=sys.stderr,
        )
        return {}, []
    manifest = json.loads(file.read_text())
    base = manifest.get("baseUrl") or ""
    if base and not base.endswith("/"):
        base += "/"
    by_id = {
        p["id"]: {
            "name": p.get("name") or p["id"],
            "files": [
                {
                    "label": f.get("label"),
                    "url": base + f["path"],
                    "solution": bool(f.get("solution")),
                }
                for f in p.get("files") or []
            ],
        }
        for p in manifest.get("practicals") or []
    }
    bundles = [
        {"url": base + b["path"], "label": os.path.basename(b["path"])}
        for b in manifest.get("bundles") or []
    ]
    return by_id, bundles


# ------------------------------------------------------------------ outlines
def outlines(
    course: Course,
    sched: dict,
    ids: list[str],
    directory: Path | None,
    newer: float = 0,
) -> dict:
    """Deck outlines by id: `<dir>/<id>/outline.json` when there is one (what
    the build, or a deck's dev server, wrote) not older than `newer`, else
    computed (compiled as handouts, in parallel)."""
    result: dict = {}
    missing = []
    for i in ids:
        f = directory / i / "outline.json" if directory else None
        if f and f.exists() and f.stat().st_mtime >= newer:
            result[i] = json.loads(f.read_text())
        else:
            missing.append(i)
    if missing:
        lectures = {lec.get("id"): lec for lec in sched["lectures"]}
        decks = [
            {**lectures.get(i, {"id": i}), "id": i, "file": course.deck_file(i)}
            for i in missing
        ]
        for deck, outline in compile_outlines(course, decks):
            result[deck["id"]] = outline
    return result


# --------------------------------------------------------------- index page
INDEX_STYLE = """
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.6;
    }
    h1 { color: #333; margin-top: 2rem; }
    ul { list-style-type: none; padding: 0; }
    li { padding: 0.75rem 0; border-bottom: 1px solid #eee; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .pdf-link { color: #cc0000; font-size: 0.85em; margin-left: 0.5rem; }
    .practical-link { color: #009900; font-size: 0.85em; margin-left: 0.5rem; }
    .practical-list { margin-top: 0.5rem; margin-left: 1.5rem; }
    .practical-item { font-size: 0.85em; color: #555; margin-bottom: 0.25rem; }
    .practical-optional { color: #888; font-style: italic; }
    .dev-badge { color: #ff6600; font-size: 0.75em; margin-left: 0.5rem; }
    .practical-bundle {
      margin: 1rem 0; padding: 0.75rem 1rem; background: #f3f8f3;
      border-left: 4px solid #009900; font-size: 0.9em; color: #333;
    }
    .practical-bundle a { font-weight: 600; }
    .deck-summary { color: #444; font-size: 0.9em; margin-top: 0.25rem; }
    details.outline { margin-top: 0.4rem; font-size: 0.88em; }
    details.outline > summary { cursor: pointer; color: #666; }
    details.outline ul { list-style: none; padding-left: 1.1rem; margin: 0.3rem 0; }
    details.outline > ul { padding-left: 0.4rem; }
    details.outline li { border: none; padding: 0.15rem 0; }
    .outline-section > .outline-title { font-weight: 600; color: #333; }
    .outline-subsection > .outline-title { color: #333; }
    .outline-time { color: #999; font-size: 0.85em; margin-left: 0.4rem; }
    .outline-summary { color: #555; font-size: 0.95em; line-height: 1.4; }
    .synopsis-toggle { font-size: 0.8rem; font-weight: normal; vertical-align: middle; margin-left: 1rem; cursor: pointer;
      background: none; border: 1px solid #ccc; border-radius: 4px; padding: 0.1rem 0.6rem; color: #555; }
    @media print { details.outline > summary { display: none; } }
"""

TOGGLE_SCRIPT = """
  <script>
    (function () {
      var button = document.querySelector('.synopsis-toggle');
      var outlines = document.querySelectorAll('details.outline');
      var sync = function () {
        var allOpen = Array.prototype.every.call(outlines, function (d) { return d.open; });
        button.textContent = allOpen ? button.dataset.collapse : button.dataset.expand;
      };
      button.addEventListener('click', function () {
        var open = !Array.prototype.every.call(outlines, function (d) { return d.open; });
        outlines.forEach(function (d) { d.open = open; });
        sync();
      });
      outlines.forEach(function (d) { d.addEventListener('toggle', sync); });
      window.addEventListener('beforeprint', function () { outlines.forEach(function (d) { d.open = true; }); });
    })();
  </script>"""


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def index_html(  # noqa: C901
    course: Course,
    sched: dict,
    outline_of: dict,
    dev: bool = False,
    practicals: dict | None = None,
    bundles: list | None = None,
    live: bool = False,
) -> str:
    """The index page, from the schedule, the outlines and the practicals."""
    practicals = practicals or {}
    bundles = bundles or []
    lang = str(sched.get("lang") or "en").lower().split("-")[0]
    strings = {**STRINGS["en"], **STRINGS.get(lang, {}), **(sched.get("index") or {})}

    def t(k: str) -> str:
        return esc(strings[k])

    default_rate = (
        sched.get("timePerSlide") if _number(sched.get("timePerSlide")) else 2
    )

    def minutes(node: dict, rate: float) -> float:
        return stats(node)["timed"] * rate

    def outline_items(node: dict, rate: float) -> list[str]:
        out = []
        for c in node.get("children") or []:
            if c["kind"] not in ("section", "subsection"):
                continue
            m = minutes(c, rate)
            time = (
                f' <span class="outline-time">{esc(fmt_minutes(m))}</span>' if m else ""
            )
            summary = (
                f'<div class="outline-summary">{esc(c["synopsis"])}</div>'
                if c.get("synopsis")
                else ""
            )
            sub = outline_items(c, rate)
            subs = f"<ul>{''.join(sub)}</ul>" if sub else ""
            out.append(
                f'<li class="outline-{c["kind"]}"><span class="outline-title">{esc(c["title"])}</span>{time}{summary}{subs}</li>'
            )
        return out

    def synopsis(lec: dict) -> str:
        root = outline_of.get(lec.get("id")) if lec.get("id") else None
        text = (root or {}).get("synopsis") or lec.get("summary")
        summary = (
            f'\n        <div class="deck-summary">{esc(text)}</div>' if text else ""
        )
        if not root:
            return summary
        rate = lec["timePerSlide"] if _number(lec.get("timePerSlide")) else default_rate
        items = outline_items(root, rate)
        if not items:
            return summary
        m = minutes(root, rate)
        total = f" · {esc(fmt_minutes(m))}" if m else ""
        return (
            f'{summary}\n        <details class="outline"><summary>{t("outline")}{total}</summary>'
            f"<ul>{''.join(items)}</ul></details>"
        )

    dev_badge = ' <span class="dev-badge">[dev]</span>'

    def practical_list(lec: dict) -> str:
        divs = []
        for entry in lec.get("practicals") or lec.get("practical") or []:
            e = {"id": entry} if isinstance(entry, str) else entry
            pid, optional, pdev = (
                e.get("id"),
                e.get("optional", False),
                e.get("dev", False),
            )
            if pdev and not dev:
                continue
            p = practicals.get(pid)
            if not p:
                if practicals:
                    print(
                        f'[site] {lec.get("id") or lec.get("title")}: no practical "{pid}" in the manifest',
                        file=sys.stderr,
                    )
                continue
            links = " ".join(
                f'<a href="{esc(f["url"])}" class="practical-link{" practical-solution" if f["solution"] else ""}">[{esc(f["label"])}]</a>'
                for f in p["files"]
            )
            opt = (
                f' <span class="practical-optional">({t("optional")})</span>'
                if optional
                else ""
            )
            divs.append(
                f'<div class="practical-item">{esc(p["name"])}{opt}{dev_badge if pdev else ""}: {links}</div>'
            )
        if not divs:
            return ""
        return (
            '\n        <div class="practical-list">\n          '
            + "\n          ".join(divs)
            + "\n        </div>"
        )

    def item(lec: dict) -> str:
        title = esc(lec.get("title") or lec.get("id"))
        if lec.get("externalPdf"):
            main = f'<a href="{esc(lec["externalPdf"])}">{title}</a>'
        else:
            main = f'<a href="{esc(lec["id"])}/">{title}</a>'
        pdf = (
            f' <a href="pdf/{esc(lec["id"])}.pdf" class="pdf-link">[PDF]</a>'
            if not lec.get("externalPdf") and lec.get("pdf")
            else ""
        )
        return f"      <li>{main}{pdf}{dev_badge if lec.get('dev') else ''}{synopsis(lec)}{practical_list(lec)}</li>"

    listed = [
        lec
        for lec in entries(sched, dev)
        if lec.get("externalPdf") or is_deck(course, lec)
    ]
    has_outline = any(lec.get("id") in outline_of for lec in listed)
    toggle = (
        f' <button type="button" class="synopsis-toggle" data-expand="{t("expandAll")}" '
        f'data-collapse="{t("collapseAll")}">{t("expandAll")}</button>'
        if has_outline
        else ""
    )
    bundle_html = "".join(
        f'\n  <p class="practical-bundle">\n    <a href="{esc(b["url"])}" download>{esc(b["label"])}</a>\n  </p>\n'
        for b in bundles
    )
    script = TOGGLE_SCRIPT if has_outline else ""
    live_script = (
        "\n  <script>new EventSource('/_events').onmessage = function () { location.reload(); };</script>"
        if live
        else ""
    )
    items = "\n".join(item(lec) for lec in listed)
    return f"""<!DOCTYPE html>
<html lang="{esc(lang)}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{t("title")}</title>
  <style>{INDEX_STYLE}  </style>
</head>
<body>
  <h1>{t("lectures")}{toggle}</h1>
  <ul>
{items}
  </ul>
{bundle_html}{script}{live_script}
</body>
</html>
"""


def write_index(
    course: Course, sched: dict, out: Path, dev: bool, practicals_file: Path | None
) -> None:
    by_id, bundles = read_practicals(practicals_file)
    ids = deck_ids(course, sched, dev)
    page = index_html(
        course, sched, outlines(course, sched, ids, out), dev, by_id, bundles
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page)
    print(f"{course.rel(out / 'index.html')}: {len(ids)} deck(s)")


# ---------------------------------------------------------------- the site
def copy_static(src: Path, dest: Path) -> None:
    """Copies `src` into `dest`, recursively (dotfiles left out)."""
    for e in src.iterdir():
        if e.name.startswith("."):
            continue
        to = dest / e.name
        if e.is_dir():
            to.mkdir(parents=True, exist_ok=True)
            copy_static(e, to)
        else:
            s = e.stat()
            if (
                not to.exists()
                or to.stat().st_size != s.st_size
                or to.stat().st_mtime < s.st_mtime
            ):
                shutil.copy2(e, to)


def build_site(
    course: Course,
    sched: dict,
    out: Path,
    dev: bool,
    statics: list[Path],
    practicals_file: Path | None,
    jobs: int = 0,
) -> bool:
    from .build import DeckBuild

    ids = deck_ids(course, sched, dev)
    out.mkdir(parents=True, exist_ok=True)
    # a deck that left the site (removed, or now `dev: true`) goes too
    for e in out.iterdir():
        if e.is_dir() and e.name not in ids and (e / "slides.html").exists():
            print(f"[site] removing {e.name}/ (no longer in the site)")
            shutil.rmtree(e)

    def one(i: str) -> bool:
        return DeckBuild(course, course.deck_file(i), out).build_all()

    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        ok = all(list(ex.map(one, ids)))
    for d in statics:
        if d.exists():
            copy_static(d, out)
    write_index(course, sched, out, dev, practicals_file)
    check_paths(course, out)
    return ok


# ---------------------------------------------------------------- PDFs
def _md5(data: bytes | str) -> str:
    return hashlib.md5(data.encode() if isinstance(data, str) else data).hexdigest()


def build_pdfs(
    course: Course, ids: list[str], out: Path, force: bool = False, jobs: int = 0
) -> bool:
    """The PDF of each deck, unless the MD5 of everything its last compilation
    read (and of its inputs) is unchanged and the PDF is there. The cache
    (.cache/pdf/) is per output directory."""
    from .engine import DeckCompiler

    cache = course.root / ".cache" / "pdf" / _md5(str(out.resolve()))[:8]
    cache.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    def key(i: str) -> str | None:
        try:
            deps = json.loads((cache / f"{i}.deps.json").read_text())["inputs"]
        except (OSError, ValueError, KeyError):
            return None
        h = hashlib.md5(b"cathedra pdf")
        for f in sorted(deps):
            h.update(f.encode())
            try:
                h.update((course.root / f).read_bytes())
            except OSError:
                return None
        return h.hexdigest()

    def one(i: str) -> bool:
        pdf = out / f"{i}.pdf"
        stamp = cache / f"{i}.md5"
        before = key(i)
        if (
            not force
            and before
            and pdf.exists()
            and stamp.exists()
            and stamp.read_text() == before
        ):
            print(f"{course.rel(pdf)}: up to date")
            return True
        print(course.rel(pdf))
        comp = DeckCompiler(course, course.deck_file(i)).compile()
        for d in comp.diagnostics:
            print(d.text, file=sys.stderr)
        if not comp.ok:
            return False
        pdf.write_bytes(comp.pdf())
        deps = [os.path.relpath(p, course.root) for p in comp.dependencies]
        (cache / f"{i}.deps.json").write_text(json.dumps({"inputs": deps}))
        stamp.write_text(key(i) or "")
        return True

    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        return all(list(ex.map(one, ids)))


# ------------------------------------------------------- absolute paths
def check_paths(course: Course, out: Path) -> bool:
    """Fails when a text file of the site holds a local absolute path (the
    course's directory, the engine's, or the home directory)."""
    needles = {str(course.root), str(TYPST.parent), os.environ.get("HOME", "")}
    needles = {n for n in needles if n and len(n) > 1}
    bad = []
    for root, _, files in os.walk(out):
        for f in files:
            if not f.endswith(
                (".html", ".json", ".mjs", ".js", ".css", ".svg", ".txt")
            ):
                continue
            p = Path(root) / f
            text = p.read_text(errors="replace")
            hit = next((n for n in needles if n in text), None)
            if hit:
                bad.append(f"{course.rel(p)}: {hit}")
    if bad:
        print(
            f"[site] local absolute paths in {course.rel(out)} (not publishable):\n  "
            + "\n  ".join(bad),
            file=sys.stderr,
        )
        return False
    return True
