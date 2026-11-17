"""Fixtures: a small made-up course (tests/fixtures/course), copied into a
temporary directory with its `slide-app` link to the engine."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from typst_slides.paths import TYPST, Course

FIXTURE = Path(__file__).parent / "fixtures" / "course"


@pytest.fixture
def course_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    d = tmp_path / "course"
    shutil.copytree(FIXTURE, d)
    (d / "slide-app").symlink_to(TYPST)
    monkeypatch.chdir(d)
    monkeypatch.delenv("SLIDES_SRC", raising=False)
    monkeypatch.delenv("SLIDES_SCHEDULE", raising=False)
    return d


@pytest.fixture
def course(course_dir: Path) -> Course:
    return Course(course_dir)
