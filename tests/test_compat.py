"""Templates and the engine API; migrations."""

from __future__ import annotations

import re

from cathedra.compat import api_problems, engine_api, satisfies
from cathedra.migrate import academic_package, course_data
from cathedra.paths import TYPST


def test_api_version_matches():
    lib = (TYPST / "lib" / "slides.typ").read_text()
    assert f"#let api-version = {engine_api()}" in lib


def test_ranges():
    assert satisfies(3, ">=3, <4")
    assert not satisfies(4, ">=3, <4")
    assert satisfies(3, "3")


def test_template_range(tmp_path):
    t = tmp_path / "tpl"
    t.mkdir()
    (t / "typst.toml").write_text(
        '[package]\nname = "x"\nversion = "1.0.0"\n[tool.cathedra]\napi = ">=1, <2"\n'
    )
    (t / "x.typ").write_text("")
    (problem,) = api_problems([t / "x.typ"])
    assert "x 1.0.0 needs the cathedra API >=1, <2" in problem
    academic = TYPST / "templates" / "academic" / "academic.typ"
    assert api_problems([academic]) == []


def test_migrate_course_data():
    src = (
        '#import "/slide-app/typst/lib/slides.typ": *\n'
        '#import "/slide-app/typst/templates/academic.typ": academic\n\n'
        "#let (theme: course-theme, title-slide: title-slide) = academic(\n"
        "  course: [X],\n"
        ")\n"
    )
    s, n, _ = academic_package(src, None)
    assert n == 1 and "/templates/academic/academic.typ" in s
    s, n, _ = course_data(s, None)
    assert n == 1
    assert re.search(r"course: \[X\],\n  data: course-data,\n\)", s)
    assert s.index("#let course-data") < s.index("= academic(")
    # idempotent
    assert course_data(s, None)[1] == 0
