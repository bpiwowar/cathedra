# ruff: noqa: T201
"""Optimize a Typst course's SOURCE images in place (`make optimize-images`).

- PNG / JPEG -> WebP (resized so the longest edge is at most the cap)
- GIF -> animated WebP
- base64 PNG/JPEG embedded in *.svg -> embedded WebP data URIs
- rewrites each image reference of the text files (.typ, but also .svg,
  .css, .ts, …: `image("figures/a.png")`, src="./x.png", url(a.png) …) to the
  new `.webp` name, and (with --prune) deletes unreferenced raster leftovers.

References are resolved relative to the file they appear in — or, starting
with "/", from the course root, as Typst does — so images may live in any
directory. A zotero:// / http(s):// image naming its local copy with
`filename="…"` or in the URL fragment counts as a reference too.

The root is the course directory (minus out/, .cache/, lib/, cathedra, slide-app,
node_modules, .git; --exclude a,b replaces that list); --src <dir>: only that
part of the root is walked (the course's sources). The resolution cap is the
deck width x --scale (960 px x 2 -> 1920 px): crisp on high-DPI screens
without shipping oversized scans; --max overrides it. An image that would not
get smaller as WebP is left alone.

Idempotent: a second run finds no raster files left and does nothing.

    python -m cathedra.optimize_images [--src src] [--scale 2] [--max <px>]
        [--quality 80] [--gif-quality 70] [--no-svg] [--prune] [--dry]
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageSequence

DEFAULT_DECK_WIDTH = 960
QUALITY = 80
GIF_QUALITY = 70
EXCLUDE = "out,.cache,lib,cathedra,slide-app,node_modules,.git"

RASTER = {".png", ".jpg", ".jpeg", ".gif"}
TEXT = {
    ".typ",
    ".mdx",
    ".md",
    ".html",
    ".htm",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".scss",
    ".css",
    ".svg",
    ".json",
    ".pug",
}

# A path ending in an image extension, bounded by a quote/paren/=: catches
# image("x.png"), src="./x.png", ](z.png), url(a.png), …
RE_REF = re.compile(r"""[("'`=]\s*([^"'`()\s]+\.(?:png|jpe?g|gif))(?=["'`)\s])""", re.I)
# The local copy of a zotero:// / http(s):// asset, named by a `filename="…"`
# attribute or in the URL fragment: nothing to rewrite (the extension is
# chosen when it is fetched), but the file IS referenced, so it is converted
# and never counted as an orphan (which --prune would delete).
RE_RENAME = re.compile(r"""\bfilename\s*=\s*["']([^"'`\s]+)["']""")
RE_URL_FRAGMENT = re.compile(r"""(?:zotero|https?)://[^"'`\s]*#([^,"'`\s]+)""")
RE_DATA = re.compile(r"data:image/(png|jpe?g);base64,([A-Za-z0-9+/=]+)")


def human(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1048576:
        return f"{n / 1024:.0f} KB"
    return f"{n / 1048576:.1f} MB"


def webp_name(s: str) -> str:
    return re.sub(r"\.(png|jpe?g|gif)$", ".webp", s, flags=re.I)


def read_deck_width(project_dir: Path) -> int | None:
    """The deck width a build recorded in cache/deck.json, if any."""
    try:
        stamp = json.loads((project_dir / "cache" / "deck.json").read_text())
        return stamp.get("width") or None
    except (OSError, ValueError, AttributeError):
        return None


# ---- encoding ---------------------------------------------------------------


def _fit(img: Image.Image, cap: int) -> Image.Image:
    """`img` shrunk so its longest edge is at most `cap` (never enlarged)."""
    scale = min(cap / img.width, cap / img.height, 1)
    if scale >= 1:
        return img
    size = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
    return img.resize(size, Image.Resampling.LANCZOS)


def _rgb(img: Image.Image) -> Image.Image:
    alpha = img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info
    return img.convert("RGBA" if alpha else "RGB")


def encode_webp(
    data: bytes | Path, cap: int, quality: int, animated: bool = False
) -> bytes:
    """The image (a file or its bytes) as WebP, capped in size."""
    src = io.BytesIO(data) if isinstance(data, bytes) else data
    out = io.BytesIO()
    with Image.open(src) as img:
        frames = getattr(img, "n_frames", 1) if animated else 1
        if frames > 1:
            durations = []
            images = []
            for frame in ImageSequence.Iterator(img):
                durations.append(frame.info.get("duration", 100))
                images.append(_fit(frame.convert("RGBA"), cap))
            images[0].save(
                out,
                "WEBP",
                save_all=True,
                append_images=images[1:],
                duration=durations,
                loop=img.info.get("loop", 0),
                quality=quality,
            )
        else:
            _fit(_rgb(img), cap).save(out, "WEBP", quality=quality)
    return out.getvalue()


# ---- the course --------------------------------------------------------------


@dataclass
class Settings:
    root: str = "."
    src: str = "."
    exclude: set[str] = field(default_factory=lambda: set(EXCLUDE.split(",")))
    cap: int = DEFAULT_DECK_WIDTH * 2
    quality: int = QUALITY
    gif_quality: int = GIF_QUALITY
    svg: bool = True
    prune: bool = False
    dry: bool = False


def walk(d: str, exclude: set[str]):
    for e in sorted(os.scandir(d), key=lambda e: e.name):
        p = os.path.normpath(os.path.join(d, e.name))
        if e.is_dir(follow_symlinks=False):
            if e.name not in exclude:
                yield from walk(p, exclude)
        else:
            yield p


@dataclass
class References:
    referenced: set[str] = field(default_factory=set)  # absolute raster paths
    by_file: dict[str, set[str]] = field(default_factory=dict)  # file -> raw refs


def resolve_ref(s: Settings, here: str, raw: str) -> str:
    """A reference as Typst resolves it: "/x" from the root, "x" from `here`."""
    if raw.startswith("/"):
        return os.path.abspath(os.path.join(s.root, raw[1:]))
    return os.path.abspath(os.path.join(here, raw))


def scan_references(s: Settings, files: list[str], rasters: set[str]) -> References:
    refs = References()
    for p in files:
        if os.path.splitext(p)[1].lower() not in TEXT:
            continue
        try:
            text = Path(p).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        here = os.path.dirname(p)
        for m in RE_REF.finditer(text):
            raw = m.group(1)
            if resolve_ref(s, here, raw) not in rasters:
                continue  # unresolved / external / non-file
            refs.referenced.add(resolve_ref(s, here, raw))
            refs.by_file.setdefault(p, set()).add(raw)
        for regex in (RE_RENAME, RE_URL_FRAGMENT):
            for m in regex.finditer(text):
                for ext in RASTER:
                    a = os.path.abspath(os.path.join(here, m.group(1) + ext))
                    if a in rasters:
                        refs.referenced.add(a)
    return refs


@dataclass
class Report:
    converted: set[str] = field(default_factory=set)
    before: int = 0
    after: int = 0
    orphans: list[str] = field(default_factory=list)
    saved_svg: int = 0


def convert(s: Settings, rasters: list[str], refs: References, report: Report):
    """1. The referenced rasters -> WebP (when it is smaller)."""
    for p in rasters:
        a = os.path.abspath(p)
        if a not in refs.referenced:
            report.orphans.append(p)
            continue
        ext = os.path.splitext(p)[1].lower()
        animated = ext == ".gif"
        before = os.path.getsize(p)
        try:
            buf = encode_webp(
                Path(p), s.cap, s.gif_quality if animated else s.quality, animated
            )
        except Exception as e:  # unreadable image: reported, left as is
            print(f"  ! skip {p}: {e}", file=sys.stderr)
            continue
        if len(buf) >= before:
            continue  # already-tiny images can grow as WebP
        report.before += before
        report.after += len(buf)
        report.converted.add(a)
        if not s.dry:
            Path(p[: -len(ext)] + ".webp").write_bytes(buf)
            os.unlink(p)
        print(f"  {p}  {human(before)} → {human(len(buf))}")


def rewrite(s: Settings, refs: References, converted: set[str]) -> None:
    """2. The references to the converted images -> their .webp name."""
    for p, raws in refs.by_file.items():
        here = os.path.dirname(p)
        path = Path(p)
        text = path.read_text(encoding="utf-8")
        changed = False
        for raw in raws:
            if resolve_ref(s, here, raw) not in converted:
                continue
            new = webp_name(raw)
            if new != raw and raw in text:
                text = text.replace(raw, new)
                changed = True
        if changed:
            path.write_text(text, encoding="utf-8")


def svg_embedded(s: Settings, files: list[str], report: Report) -> None:
    """3. Base64 rasters embedded in SVGs, re-encoded as WebP."""
    for p in files:
        if os.path.splitext(p)[1].lower() != ".svg":
            continue
        path = Path(p)
        text = path.read_text(encoding="utf-8", errors="surrogateescape")
        if not RE_DATA.search(text):
            continue

        def repl(m: re.Match) -> str:
            try:
                data = base64.b64decode(m.group(2))
                w = base64.b64encode(encode_webp(data, s.cap, s.quality)).decode()
            except Exception:  # undecodable: kept as it is
                return m.group(0)
            return (
                f"data:image/webp;base64,{w}"
                if len(w) < len(m.group(2))
                else m.group(0)
            )

        new = RE_DATA.sub(repl, text)
        before = len(text.encode(errors="surrogateescape"))
        after = len(new.encode(errors="surrogateescape"))
        if after < before:
            report.saved_svg += before - after
            if not s.dry:
                path.write_text(new, encoding="utf-8", errors="surrogateescape")
            print(f"  {p} (embedded)  {human(before)} → {human(after)}")


def optimize(s: Settings, cap_note: str = "") -> Report:
    files = list(walk(s.src, s.exclude))
    rasters = [p for p in files if os.path.splitext(p)[1].lower() in RASTER]
    refs = scan_references(s, files, {os.path.abspath(p) for p in rasters})
    print(
        f"Cap {s.cap}px{f' ({cap_note})' if cap_note else ''} · root {s.root} · "
        f"{len(rasters)} raster(s), {len(refs.referenced)} referenced\n"
    )
    report = Report()
    convert(s, rasters, refs, report)
    if not s.dry:
        rewrite(s, refs, report.converted)
    if s.svg:
        svg_embedded(s, files, report)
    # 4. unreferenced raster leftovers
    pruned = sum(os.path.getsize(p) for p in report.orphans)
    if s.prune and not s.dry:
        for p in report.orphans:
            os.unlink(p)

    dry = "[dry-run] " if s.dry else ""
    msg = (
        f"\n{dry}converted {len(report.converted)} image(s): "
        f"{human(report.before)} → {human(report.after)}"
    )
    if report.saved_svg:
        msg += f", {human(report.saved_svg)} saved in SVGs"
    if report.orphans:
        what = (
            ("[dry-run] would delete" if s.dry else "deleted")
            if s.prune
            else "unreferenced (use --prune to delete)"
        )
        msg += f"\n{what}: {len(report.orphans)} image(s), {human(pruned)}"
    print(msg)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cathedra optimize-images",
        description="PNG/JPEG/GIF -> WebP, capped in size, references rewritten.",
    )
    parser.add_argument("--root", default=".", help="the course root (default: .)")
    parser.add_argument(
        "--src", help="only walk this part of the root (default: the root)"
    )
    parser.add_argument(
        "--exclude", default=EXCLUDE, help=f"directories skipped (default: {EXCLUDE})"
    )
    parser.add_argument(
        "--scale", type=float, default=2.0, help="cap = deck width x scale"
    )
    parser.add_argument(
        "--config",
        default="webpack.config.js",
        help="its directory's cache/deck.json gives the deck width, if any",
    )
    parser.add_argument(
        "--max", type=int, help="the cap in pixels (overrides the scale)"
    )
    parser.add_argument("--quality", type=int, default=QUALITY)
    parser.add_argument("--gif-quality", type=int, default=GIF_QUALITY)
    parser.add_argument(
        "--no-svg", action="store_true", help="leave the rasters embedded in SVGs"
    )
    parser.add_argument(
        "--prune", action="store_true", help="delete the unreferenced rasters"
    )
    parser.add_argument("--dry", action="store_true", help="change nothing")
    parser.add_argument(
        "--typst", action="store_true", help="(accepted; always a Typst course)"
    )
    args = parser.parse_args(argv)

    deck_width = read_deck_width(Path(args.config).resolve().parent)
    scale = args.scale
    cap = args.max or round((deck_width or DEFAULT_DECK_WIDTH) * scale)
    assumed = "" if deck_width else " (assumed)"
    cap_note = f"{deck_width or DEFAULT_DECK_WIDTH}px deck{assumed} × {scale:g}"
    settings = Settings(
        root=args.root,
        src=args.src or args.root,
        exclude={x for x in args.exclude.split(",") if x},
        cap=cap,
        quality=args.quality,
        gif_quality=args.gif_quality,
        svg=not args.no_svg,
        prune=args.prune,
        dry=args.dry,
    )
    optimize(settings, cap_note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
