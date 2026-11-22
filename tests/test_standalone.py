"""Plain `typst compile` works from a clone: the generated files are
optional, `make check` fails when a deck needs a file git ignores."""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from cathedra import images, migrate, sync
from cathedra.engine import TYPST_VERSION, DeckCompiler
from cathedra.standalone import plain_problems


def test_plain_compile_reads_no_generated_file(course, course_dir):
    shutil.rmtree(course_dir / "lib")
    comp = DeckCompiler(course, course.deck_file("demo"), plain=True).compile()
    assert comp.ok
    read = {
        p.relative_to(course_dir).parts[0]
        for p in comp.dependencies
        if p.is_relative_to(course_dir)
    }
    assert not read & {"lib", ".cache"}
    assert not (course_dir / "lib").exists()  # nothing written either


def _git(d, *args):
    subprocess.run(["git", *args], cwd=d, check=True, capture_output=True)


def test_check_flags_ignored_files(course, course_dir):
    _git(course_dir, "init", "-q")
    (course_dir / ".gitignore").write_text("lib/\n.cache/\ncathedra\n")
    deck = course.deck_file("demo")
    assert plain_problems(course, deck) == []
    # a deck reading a generated file whatever the mode: a clone fails
    deck.write_text(deck.read_text() + '\n#json("/lib/refs-links.json").len()\n')
    (problem,) = plain_problems(course, deck)
    assert "lib/refs-links.json" in problem and "git ignores" in problem
    # tracked, it is in every clone
    _git(course_dir, "add", "-f", "lib/refs-links.json")
    assert plain_problems(course, deck) == []


def _typst_cli() -> bool:
    if shutil.which("typst") is None:
        return False
    v = subprocess.run(["typst", "--version"], capture_output=True, text=True)
    return TYPST_VERSION in v.stdout


@pytest.mark.skipif(not _typst_cli(), reason=f"no typst {TYPST_VERSION} CLI")
def test_typst_cli_compiles_a_clone(course_dir):
    shutil.rmtree(course_dir / "lib")
    r = subprocess.run(
        [
            "typst",
            "compile",
            "--root",
            ".",
            "--font-path",
            "cathedra/fonts",
            "lectures/demo/demo.typ",
            "demo.pdf",
        ],
        cwd=course_dir,
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr
    assert (course_dir / "demo.pdf").stat().st_size > 0


def test_sync_fails_on_duplicate_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bib = tmp_path / "main.bib"
    bib.write_text("@article{a,\n title={A}\n}\n@article{b,\n title={B}\n}\n")
    assert sync.main(str(bib)) == 0
    assert set(json.loads((tmp_path / "lib/refs-links.json").read_text())) == {"a", "b"}
    assert not (tmp_path / "lib/refs.bib").exists()
    bib.write_text(bib.read_text() + "@book{a,\n title={A again}\n}\n")
    assert sync.main(str(bib)) == 1
    assert sync.duplicates(bib.read_text()) == {"a": [1, 7]}


def test_images_written_to_their_path(course, course_dir, monkeypatch):
    from PIL import Image

    raw = course_dir / "raw.png"
    Image.new("RGB", (4000, 100), "red").save(raw)
    monkeypatch.setattr(images, "fetch_raw", lambda url, d: raw)
    mod = course_dir / "modules/intro/intro.typ"
    mod.write_text(
        mod.read_text()
        + '\n#img(path("images/x.webp"), origin: "https://example.org/x.png")\n'
        + '#img("https://example.org/y.png")\n'
    )
    assert images.fetch_all(course) == 1  # the URL-only image: an error
    out = course_dir / "modules/intro/images/x.webp"
    with Image.open(out) as img:
        assert img.format == "WEBP" and img.width <= 1920
    assert not (course_dir / ".cache/images/manifest.json").exists()


OLD = """#import "/slide-app/lib/slides.typ": *

// The course's generated data (typst-slides writes these files), given to
// the template: the reference links, the fetched images, the widgets'
// pictures (see `course-setup` in lib/slides.typ)
#let course-data = (
  ref-links: json("/lib/refs-links.json"),
  image-cache: json("/.cache/images/manifest.json"),
  widget-shots: json("/.cache/widgets/manifest.json"),
)
#place(hide(bibliography("/lib/refs.bib", style: "/lib/refs.csl", title: none)))
#img("https://example.org/a.png")
"""


def test_migration_4(tmp_path, monkeypatch):
    monkeypatch.setenv("SLIDES_BIB", "src/main.bib")
    s = OLD
    skipped = []
    for _, fn in migrate.MIGRATIONS[4]:
        s, _, sk = fn(s, tmp_path / "x.typ")
        skipped += sk
    assert "#let course-data = if generated {\n  (\n    ref-links" in s
    assert "  )\n} else { (:) }" in s
    assert "image-cache" not in s and "Read only when cathedra compiles" in s
    assert 'bibliography("/src/main.bib", style: bib-style' in s
    assert len(skipped) == 1 and "origin" in skipped[0][1]
    again = s
    for _, fn in migrate.MIGRATIONS[4]:
        again, n, _ = fn(again, tmp_path / "x.typ")
    assert again == s  # idempotent
