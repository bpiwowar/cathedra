#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11,<3.14"
# dependencies = ["fonttools[woff]>=4.55"]
# ///
"""Convert the viewer's Font Awesome Free webfonts (WOFF2, OFL) to TTF for Typst.

Typst cannot read WOFF2; the TTFs go to src/cathedra/typst/fonts/
(committed: the package ships them), which every compilation gets as a font
path. Run after upgrading @fortawesome/fontawesome-free in viewer/:

    (cd viewer && pnpm install) && scripts/fonts.py
"""

import pathlib
import sys

from fontTools.ttLib import TTFont

here = pathlib.Path(__file__).resolve().parent.parent
src = here / "viewer/node_modules/@fortawesome/fontawesome-free/webfonts"
dst = here / "src/cathedra/typst/fonts"
dst.mkdir(exist_ok=True)
for name in ("fa-solid-900", "fa-regular-400"):
    font = TTFont(src / f"{name}.woff2")
    font.flavor = None
    font.save(dst / f"{name}.ttf")
    print(f"{name}.ttf", file=sys.stderr)  # noqa: T201
