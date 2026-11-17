# ruff: noqa: T201
"""Trim each SVG's canvas to the tight bounding box of its content.

    python -m typst_slides.svg_bbox <path>...           dry run: report changes
    python -m typst_slides.svg_bbox <path>... --apply   rewrite the files
    (or: make compute-svg-bb SVG=<files or dirs> [APPLY=1])

Each <path> is an .svg file or a directory, scanned recursively for .svg
files. The SVG is rendered in headless Chromium (Playwright, the
`typst-slides[browser]` extra) and SVGGraphicsElement.getBBox() is read off
the root <svg>: the tightest rectangle enclosing all rendered geometry, in the
SVG's own (post-viewBox) coordinate system. That becomes the new viewBox;
width and height (if present) are rescaled in lockstep, through the DOM's own
SVGAnimatedLength so the original unit (mm, in, …) round-trips. Only the root
tag's attributes are rewritten: the rest of the file is left byte for byte.

Caveat: getBBox() is purely geometric — it excludes stroke width, markers and
filter bleed. A heavy stroke right at the reported edge can end up clipped by
half its width; check the result before committing.
"""

from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path

BROWSER_HINT = (
    "compute-svg-bb: needs typst-slides[browser] "
    "(pip install 'typst-slides[browser]' && playwright install chromium)"
)

# Runs in the page: the content bbox, and (if it changes) the width/height
# attribute strings the browser recomputes in their original unit.
MEASURE_JS = """() => {
  const svg = document.querySelector('svg');
  if (!svg) return { error: 'no <svg> element found' };
  const bbox = svg.getBBox();
  if (!(bbox.width > 0 && bbox.height > 0)) return { error: 'empty or unmeasurable content' };
  const hasViewBox = svg.hasAttribute('viewBox');
  const hasWidth = svg.hasAttribute('width');
  const hasHeight = svg.hasAttribute('height');
  const oldViewBox = hasViewBox
    ? { x: svg.viewBox.baseVal.x, y: svg.viewBox.baseVal.y,
        width: svg.viewBox.baseVal.width, height: svg.viewBox.baseVal.height }
    : { x: 0, y: 0, width: svg.width.baseVal.value, height: svg.height.baseVal.value };
  if (!(oldViewBox.width > 0 && oldViewBox.height > 0)) {
    return { error: 'no viewBox and no usable width/height' };
  }
  const scaleX = hasWidth ? svg.width.baseVal.value / oldViewBox.width : 1;
  const scaleY = hasHeight ? svg.height.baseVal.value / oldViewBox.height : 1;
  const result = {
    oldViewBox,
    bbox: { x: bbox.x, y: bbox.y, width: bbox.width, height: bbox.height },
    hasViewBox,
  };
  if (hasWidth) {
    svg.width.baseVal.value = bbox.width * scaleX;
    result.newWidthAttr = svg.getAttribute('width');
  }
  if (hasHeight) {
    svg.height.baseVal.value = bbox.height * scaleY;
    result.newHeightAttr = svg.getAttribute('height');
  }
  return result;
}"""


def collect_svg_files(p: Path, out: list[Path]) -> None:
    if p.is_dir():
        for entry in sorted(p.iterdir()):
            collect_svg_files(entry, out)
    elif p.is_file() and p.name.lower().endswith(".svg"):
        out.append(p)


def find_opening_tag(content: str) -> tuple[int, int, str] | None:
    """The root <svg …> tag: (start, end, text), quoted values respected (a
    stray '>' inside a style attribute does not end it)."""
    start = content.find("<svg")
    if start == -1:
        return None
    in_quote = None
    for i in range(start, len(content)):
        c = content[i]
        if in_quote:
            if c == in_quote:
                in_quote = None
        elif c in "\"'":
            in_quote = c
        elif c == ">":
            return start, i + 1, content[start : i + 1]
    return None


def get_attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\s{name}\s*=\s*"([^"]*)"', tag)
    return m.group(1) if m else None


def num(n: float) -> str:
    """n rounded to 3 decimals, written as JavaScript would."""
    r = math.floor(n * 1000 + 0.5) / 1000
    return str(int(r)) if r == int(r) else repr(r)


def _set_attr(tag: str, name: str, value: str) -> str:
    return re.sub(
        rf'(\s{name}\s*=\s*)"[^"]*"', lambda m: f'{m.group(1)}"{value}"', tag, count=1
    )


def new_tag(tag: str, info: dict) -> tuple[str, list[str]]:
    """The rewritten root tag, and the lines describing the change."""
    bbox, old = info["bbox"], info["oldViewBox"]
    view_box = " ".join(num(bbox[k]) for k in ("x", "y", "width", "height"))
    old_attr = (
        get_attr(tag, "viewBox") or f"0 0 {num(old['width'])} {num(old['height'])}"
    )
    lines = [f'      viewBox  "{old_attr}" -> "{view_box}"']
    if info.get("hasViewBox"):
        tag = _set_attr(tag, "viewBox", view_box)
    else:
        tag = re.sub(r"^<svg", lambda _: f'<svg\n   viewBox="{view_box}"', tag)
    for name, key in (("width", "newWidthAttr"), ("height", "newHeightAttr")):
        old_value, value = get_attr(tag, name), info.get(key)
        if old_value is not None and value is not None:
            lines.append(f'      {name:<8} "{old_value}" -> "{value}"')
            tag = _set_attr(tag, name, value)
    return tag, lines


def unchanged(info: dict, eps: float = 0.01) -> bool:
    bbox, old = info["bbox"], info["oldViewBox"]
    return all(abs(bbox[k] - old[k]) < eps for k in ("x", "y", "width", "height"))


def measure(browser, content: str) -> dict:
    page = browser.new_page()
    try:
        page.set_content(
            f"<!doctype html><html><body>{content}</body></html>", wait_until="load"
        )
        return page.evaluate(MEASURE_JS)
    finally:
        page.close()


def process_file(browser, file: Path, apply: bool) -> None:
    content = file.read_text(encoding="utf-8")
    tag = find_opening_tag(content)
    if not tag:
        print(f"skip  {file}  (no <svg> tag found)")
        return
    info = measure(browser, content)
    if info.get("error"):
        print(f"skip  {file}  ({info['error']})")
        return
    if unchanged(info):
        print(f"ok    {file}")
        return
    start, end, text = tag
    tag_text, lines = new_tag(text, info)
    print(f"{'apply' if apply else 'diff '} {file}")
    for line in lines:
        print(line)
    if apply:
        file.write_text(content[:start] + tag_text + content[end:], encoding="utf-8")


def compute_svg_bb(files: list[Path], apply: bool = False) -> None:
    """Trim `files` (dry run unless `apply`). Raises ImportError without
    Playwright."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for file in files:
                process_file(browser, file, apply)
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="typst-slides compute-svg-bb",
        description="Recompute each SVG's viewBox (and width/height) to the tight "
        "bounding box of its rendered content, trimming excess canvas.",
    )
    parser.add_argument(
        "paths", nargs="*", help=".svg files and/or directories (scanned recursively)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="rewrite the files (default: dry run, just report the changes)",
    )
    args = parser.parse_args(argv)
    if not args.paths:
        parser.print_usage()
        return 1

    files: list[Path] = []
    for p in args.paths:
        if not os.path.exists(p):
            print(f"compute-svg-bb: no such file or directory: {p}", file=sys.stderr)
            return 1
        collect_svg_files(Path(p).resolve(), files)
    if not files:
        print("No .svg files found.")
        return 0

    try:
        compute_svg_bb(files, args.apply)
    except ImportError:
        print(BROWSER_HINT, file=sys.stderr)
        return 1
    except Exception as e:  # e.g. Chromium not installed
        print(f"compute-svg-bb: {e}", file=sys.stderr)
        return 1
    if not args.apply:
        print("\nDry run — pass --apply to rewrite these files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
