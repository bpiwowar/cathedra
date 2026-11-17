"""The course's React widgets: widgets/index.ts -> out/<deck>/widgets.js.

`export default { id: {component, steps?, async?} }`, bundled with esbuild
(esbuild.py finds or fetches the binary: no Node needed). React is not
bundled: `react`, `react-dom` and `react/jsx-runtime` are aliased to shims
(data/viewer-shims/) reading the viewer's own copy from a global (the viewer's
course-widgets.ts), so that there is one React. Other packages the widgets
import come from the course's node_modules.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .esbuild import esbuild
from .paths import PACKAGE, Course

SHIMS = PACKAGE / "data" / "viewer-shims"
LOADERS = {
    ".svg": "dataurl",
    ".png": "dataurl",
    ".gif": "dataurl",
    ".woff": "file",
    ".woff2": "file",
    ".ttf": "file",
    ".eot": "file",
}


def widgets_entry(course: Course) -> Path | None:
    for name in ("index.ts", "index.tsx", "index.js", "index.jsx"):
        f = course.src / "widgets" / name
        if f.exists():
            return f
    return None


def widget_sources(course: Course) -> list[Path]:
    d = course.src / "widgets"
    return sorted(p for p in d.rglob("*") if p.is_file()) if d.is_dir() else []


def build_widgets(
    course: Course, entry: Path, out: Path, outfile: str = "widgets.js"
) -> str:
    """Bundle the widgets into `out`/`outfile`; returns a version (hash of the
    bundle)."""
    out.mkdir(parents=True, exist_ok=True)
    args = [
        esbuild(course.root),
        str(entry),
        "--bundle",
        "--format=esm",
        "--jsx=automatic",
        "--log-level=warning",
        f"--outfile={out / outfile}",
        f"--alias:react={SHIMS / 'react'}",
        f"--alias:react-dom={SHIMS / 'react-dom'}",
        *(f"--loader:{ext}={kind}" for ext, kind in LOADERS.items()),
    ]
    run = subprocess.run(args, cwd=course.root, capture_output=True, text=True)
    if run.returncode:
        raise RuntimeError(run.stderr.strip() or "esbuild failed")
    if run.stderr.strip():
        print(run.stderr.strip())  # noqa: T201
    js = (out / outfile).read_bytes()
    return hashlib.sha1(js).hexdigest()[:12]
