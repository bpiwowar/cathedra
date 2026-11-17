"""Contact sheets of a compiled deck: every page (50 ppi) tiled 4 per row
with its number, `per` pages a sheet (`typst-slides contact`)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw

from .engine import DeckCompiler
from .paths import Course


def contact_sheets(course: Course, deck: Path, outdir: Path, per: int = 20) -> int:
    comp = DeckCompiler(course, deck).compile()
    if not comp.ok:
        raise SystemExit("\n".join(d.text for d in comp.errors))
    pages = [Image.open(io.BytesIO(b)) for b in comp.png(50)]
    outdir.mkdir(parents=True, exist_ok=True)
    for s in range(0, len(pages), per):
        ims = pages[s : s + per]
        w, h = ims[0].size
        sheet = Image.new("RGB", (4 * (w + 6), ((len(ims) + 3) // 4) * (h + 6)), "#888")
        d = ImageDraw.Draw(sheet)
        for i, im in enumerate(ims):
            x, y = (i % 4) * (w + 6), (i // 4) * (h + 6)
            sheet.paste(im, (x, y))
            d.rectangle([x, y, x + 28, y + 14], fill="black")
            d.text((x + 3, y + 2), str(s + i + 1), fill="white")
        sheet.save(outdir / f"sheet-{s // per + 1}.png")
    return len(pages)
