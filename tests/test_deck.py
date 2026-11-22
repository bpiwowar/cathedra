"""A deck of the made-up course: the web build, the outline, the site."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from cathedra.build import DeckBuild, slug
from cathedra.cli import app
from cathedra.site import index_html


def test_web_deck(course, course_dir):
    deck = DeckBuild(course, course.deck_file("demo"), course_dir / "out", dev=True)
    assert deck.build_all()
    out = course_dir / "out" / "demo"
    for f in (
        "index.html",
        "main.js",
        "main.css",
        "svg.json",
        "slides.html",
        "layout.json",
        "outline.json",
        "morph.json",
        "docs.json",
    ):
        assert (out / f).exists(), f
    manifest = json.loads((out / "svg.json").read_text())
    assert len(manifest["pages"]) == deck.last.num_pages
    assert all((out / "svg" / f"{h}.svg").exists() for h in manifest["pages"])
    outline = json.loads((out / "outline.json").read_text())
    titles = []

    def walk(n):
        titles.append((n.get("kind"), n.get("title")))
        for c in n.get("children") or []:
            walk(c)

    walk(outline)
    assert ("section", "First part") in titles
    assert ("subsection", "Introduction") in titles
    assert ("slide", "A slide with steps") in titles
    intro = next(
        c
        for s in outline["children"]
        for c in s.get("children", [])
        if c.get("title") == "Introduction"
    )
    assert intro["synopsis"] == "What this part is about."
    assert intro["src"] == {"file": "modules/intro/intro.typ", "line": 3}
    assert "more" in outline["details"]
    skeleton = (out / "slides.html").read_text()
    assert 'id="a-slide-with-steps"' in skeleton and 'class="page fragment"' in skeleton
    docs = json.loads((out / "docs.json").read_text())
    assert "README.md" in docs and "#### details-link" in docs["docs/api.md"]


def test_rebuild_reports_changes(course, course_dir):
    deck = DeckBuild(course, course.deck_file("demo"), course_dir / "out", serve=True)
    deck.build_all()
    module = course_dir / "modules" / "intro" / "intro.typ"
    module.write_text(module.read_text().replace("Some *text*", "Other *text*"))
    r = deck.build()
    assert r.ok and r.changed and not r.skeleton
    assert deck.slide_at("modules/intro/intro.typ", 8) is not None


def test_slug():
    assert slug("Élan & Co: 2nd try!") == "elan-co-2nd-try"


def test_cli_check_and_outline(course_dir):
    runner = CliRunner()
    r = runner.invoke(app, ["check", "--out", "out"])
    assert r.exit_code == 0, r.output
    assert "check: all decks compile (also as plain typst), no overflow" in r.output
    assert (course_dir / "out" / "demo.pdf").read_bytes().startswith(b"%PDF")
    r = runner.invoke(app, ["outline", "--slides"])
    assert r.exit_code == 0, r.output
    assert "§ First part" in r.output and "A slide with steps" in r.output


def test_index_page(course, course_dir):
    sched = {
        "lectures": [
            {"id": "demo", "title": "The demo", "pdf": True, "practicals": ["tp1"]}
        ]
    }
    page = index_html(
        course,
        sched,
        {},
        practicals={
            "tp1": {
                "name": "First practical",
                "files": [{"label": "notebook", "url": "tp1.ipynb", "solution": False}],
            }
        },
    )
    assert '<a href="demo/">The demo</a>' in page
    assert 'href="pdf/demo.pdf"' in page and "First practical" in page


def test_outline_sources_after_untitled_slide(course, course_dir):
    """Content between the theme and the title slide opens a slide with no
    heading: it must not take the first `===` as its source (shifting every
    slide after it)."""
    from cathedra.outline import compile_outlines

    deck = course.deck_file("demo")
    src = deck.read_text()
    deck.write_text(src.replace("#title-slide()", "#synopsis[About.]\n#title-slide()"))
    [(_, outline)] = compile_outlines(course, [{"id": "demo", "file": deck}])
    lines = deck.read_text().split("\n")

    def walk(n):
        for c in n.get("children") or []:
            yield c
            yield from walk(c)

    slides = {n["title"]: n["src"] for n in walk(outline) if n["kind"] == "slide"}
    steps = slides["A slide with steps"]
    assert lines[steps["line"] - 1] == "=== A slide with steps"
