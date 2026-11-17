"""The source tools: annotations, API index, spacing, outline helpers."""

from __future__ import annotations

from cathedra.annot import find_annot_calls, pick_annot_call, set_annot_args
from cathedra.apidoc import api_markdown
from cathedra.outline import fmt_minutes, parse_duration
from cathedra.spacing import space_slides


def test_annot_rewrite():
    src = '#annot("x", dx: 1pt)[a]\n// annot("y")\n#annot("y", id: "z",\n  width: 3pt,\n)[b]\n'
    calls = find_annot_calls(src)
    assert [c.key for c in calls] == ["x", "y", "z"]  # (comments are not skipped)
    out = set_annot_args(src, calls[0], {"dx": "5pt", "dy": "2pt"})
    assert out.startswith('#annot("x", dx: 5pt, dy: 2pt)[a]')
    call = pick_annot_call(out, "z")
    out = set_annot_args(out, call, {"dx": "1.5pt"})
    assert "width: 3pt, dx: 1.5pt,\n)" in out
    assert "no annot" in pick_annot_call(src, "nope")


def test_api_index():
    md = api_markdown()
    assert md.startswith("# API index")
    assert "## lib/slides.typ" in md and "#### interactive" in md


def test_spacing_idempotent():
    src = "= A\n=== B\ntext\n=== C\n"
    once = space_slides(src)
    assert space_slides(once) == once
    assert "\n\n\n=== C" in once


def test_durations():
    assert parse_duration("2h30") == 150
    assert parse_duration("90") == 90
    assert fmt_minutes(150) == "2h30"
    assert fmt_minutes(45) == "45 min"
    assert fmt_minutes(7.5) == "7.5 min"
