# ruff: noqa: T201
"""Images fetched at build time, downsampled; and a check for heavy images.

    python -m typst_slides.images            (from the course; `make images`)
    python -m typst_slides.images --check    (`make check-images`)

Fetch: every `#img(path("images/x.webp"), origin: "…")` call of the
course's .typ files whose file is missing: the origin (a URL, or a Zotero
annotation: the picture Zotero rendered,
~/Zotero/cache/library/<annotation>.png) is fetched once into
.cache/images/raw/, shrunk to a size cap and written to the path, in the
format of its extension (WebP: lossy; an SVG is copied). The file is then a
file of the course: commit it, so that plain `typst compile` works from a
clone (Typst itself fetches nothing). A file that exists is used as it is;
the origin is then only a link.

`#img("https://…")` (a URL as the image, API 3) is no longer fetched: an
error, saying to give a path and an origin.

Options of the call read here:

- resize: "800x" | "x300" | "500x210"   max width / height in pixels

Without `resize`, the cap is the slot: `vh: 50%` -> 50% of 700 px, `vw`
likewise (of 1244 px), else 1920 x 1400; times IMG_SCALE (default 2, the
device pixels per slide pixel are not known here, so this is the margin).
Only fetched images are rewritten; images in the course are never touched.

--check lists the course's images that are heavy (> 1 MB, or wider than
2400 px); --strict makes it exit 1 when there are some.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import shutil
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .paths import Course

SCALE = float(os.environ.get("IMG_SCALE") or 2)
PAGE_H = 700  # px: a slide's height; 16:9
PAGE_W = math.floor(PAGE_H * 16 / 9 + 0.5)
MAX_BYTES = 1_000_000
MAX_PX = 2400
QUALITY = 80
ZOTERO_CACHE = Path.home() / "Zotero" / "cache" / "library"
SKIP_DIRS = {"node_modules", ".cache", "out", "slide-app", ".git", "dist"}
USER_AGENT = "typst-slides-images/1.0"

EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}
URL_RE = re.compile(r"^(https?|zotero)://")
_STR_RE = re.compile(r'^"((?:[^"\\]|\\.)*)"$', re.S)
_PATH_RE = re.compile(r'^path\(\s*("(?:[^"\\]|\\.)*")\s*\)$', re.S)
_NAMED_RE = re.compile(r"^([\w-]+)\s*:\s*(.*)$", re.S)
_PCT_RE = re.compile(r"^[\d.]+%$")
_IMG_RE = re.compile(r"(?<![\w-])img\(")


def sha(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()[:12]


def js_round(x: float) -> int:
    """Math.round: halves go up."""
    return math.floor(x + 0.5)


def walk(d: Path):
    """The files under `d`, skipping SKIP_DIRS and hidden entries."""
    for e in sorted(os.scandir(d), key=lambda e: e.name):
        if e.name in SKIP_DIRS or e.name.startswith("."):
            continue
        if e.is_dir(follow_symlinks=False):
            yield from walk(Path(e.path))
        else:
            yield Path(e.path)


# --- the #img calls ---------------------------------------------------------


def _skip_string(src: str, i: int) -> int:
    """The index of the closing quote of the string opening at `i`."""
    i += 1
    while i < len(src) and src[i] != '"':
        if src[i] == "\\":
            i += 1
        i += 1
    return i


def balanced(src: str, open_: int) -> str | None:
    """The text of the balanced (…) starting at `open_` (an index of "("),
    strings and comments skipped; None if unbalanced."""
    depth = 0
    i = open_
    while i < len(src):
        c = src[i]
        if c == '"':
            i = _skip_string(src, i)
        elif c == "/" and src[i + 1 : i + 2] == "/":
            while i < len(src) and src[i] != "\n":
                i += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth == 0:
                return src[open_ + 1 : i]
        i += 1
    return None


def split_args(text: str) -> list[str]:
    """ "a, b: c(d, e)" -> ["a", "b: c(d, e)"]"""
    out: list[str] = []
    depth = 0
    cur = ""
    i = 0
    while i < len(text):
        c = text[i]
        if c == '"':
            end = _skip_string(text, i)
            cur += text[i : end + 1]
            i = end + 1
            continue
        if c == "/" and text[i + 1 : i + 2] == "/":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        if c in "([{":
            depth += 1
        if c in ")]}":
            depth -= 1
        if c == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += c
        i += 1
    if cur.strip():
        out.append(cur.strip())
    return out


def string_value(v: str | None) -> str | None:
    """The value of a Typst string literal, else None."""
    m = _STR_RE.match(v) if v is not None else None
    return re.sub(r"\\(.)", r"\1", m.group(1)) if m else None


def _pct(v: str | None) -> float | None:
    return float(v[:-1]) / 100 if v and _PCT_RE.match(v) else None


@dataclass
class ImgCall:
    file: Path
    key: str
    origin: str | None = None
    resize: str | None = None
    vh: float | None = None
    vw: float | None = None


def _call_key(course: Course, file: Path, first: str) -> str | None:
    p = _PATH_RE.match(first)
    if p:
        rel = string_value(p.group(1)) or ""
        if rel.startswith("/"):
            return rel
        return course.rooted(Path(os.path.normpath(file.parent / rel)))
    s = string_value(first)
    return s if s and URL_RE.match(s) else None


def img_calls(course: Course, file: Path) -> list[ImgCall]:
    src = file.read_text(encoding="utf-8")
    calls = []
    for m in _IMG_RE.finditer(src):
        text = balanced(src, m.end() - 1)
        if text is None:
            continue
        named: dict[str, str] = {}
        first = None
        for a in split_args(text):
            kv = _NAMED_RE.match(a)
            if kv:
                named[kv.group(1)] = kv.group(2)
            elif first is None:
                first = a
        if first is None:
            continue
        key = _call_key(course, file, first)
        if not key:
            continue
        calls.append(
            ImgCall(
                file,
                key,
                origin=string_value(named.get("origin")),
                resize=string_value(named.get("resize")),
                vh=_pct(named.get("vh")),
                vw=_pct(named.get("vw")),
            )
        )
    return calls


def typ_files(course: Course) -> list[Path]:
    return [f for f in walk(course.src) if f.suffix == ".typ"]


# --- fetching ---------------------------------------------------------------


def fetch_raw(url: str, raw_dir: Path) -> Path:
    """The source of an image: a file in raw_dir (downloaded once)."""
    h = sha(url)
    for f in sorted(raw_dir.iterdir()):
        if f.name.startswith(h + "."):
            return f
    base = raw_dir / h
    if url.startswith("zotero://"):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        annot = (q.get("annotation") or [None])[0]
        if not annot:
            raise ValueError(
                "no annotation= in the Zotero link "
                "(an item key names the PDF, not a region)"
            )
        f = ZOTERO_CACHE / f"{annot}.png"
        if not f.exists():
            raise ValueError(
                f"Zotero has no rendered image for annotation {annot} "
                f"(open it in Zotero; expected {f})"
            )
        out = base.with_suffix(".png")
        shutil.copyfile(f, out)
        return out
    req = urllib.request.Request(
        url.split("#", 1)[0], headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        ctype = (res.headers.get("content-type") or "").split(";")[0].strip()
        data = res.read()
    ext = EXT.get(ctype) or (
        os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower() or ".dat"
    )
    out = Path(f"{base}{ext}")
    out.write_bytes(data)
    return out


def cap(c: ImgCall) -> tuple[int | None, int | None]:
    """The size cap (w, h) in pixels of a call."""
    if c.resize:
        m = re.match(r"^(\d*)x(\d*)$", c.resize)
        if m and (m.group(1) or m.group(2)):
            return (int(m.group(1) or 0) or None, int(m.group(2) or 0) or None)
        print(
            f'images: resize "{c.resize}": expected "800x", "x300" or "500x210"',
            file=sys.stderr,
        )
    return (
        js_round(c.vw * PAGE_W * SCALE) if c.vw else 1920,
        js_round((c.vh if c.vh is not None else 1) * PAGE_H * SCALE),
    )


def _js(v: int | None) -> str:
    return "null" if v is None else str(v)


def to_webp(src: Path, out: Path, w: int | None, h: int | None) -> None:
    """`src` shrunk to fit in w x h (never enlarged), as WebP."""
    with Image.open(src) as img:
        img.seek(0)
        scale = min(
            w / img.width if w else math.inf,
            h / img.height if h else math.inf,
            1,
        )
        frame = img.convert("RGBA" if _has_alpha(img) else "RGB")
        if scale < 1:
            size = (
                max(1, js_round(img.width * scale)),
                max(1, js_round(img.height * scale)),
            )
            frame = frame.resize(size, Image.Resampling.LANCZOS)
        frame.save(out, "WEBP", quality=QUALITY)


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or "transparency" in img.info


def write_image(raw: Path, dest: Path, w: int | None, h: int | None) -> None:
    """`raw` shrunk to fit in w x h (never enlarged), as `dest`'s format."""
    if dest.suffix.lower() == ".svg" or raw.suffix.lower() in (".svg", ".dat"):
        if raw.suffix.lower() != dest.suffix.lower():
            raise ValueError(f"the origin is {raw.suffix}, cannot write {dest.suffix}")
        shutil.copyfile(raw, dest)
    elif dest.suffix.lower() == ".webp":
        to_webp(raw, dest, w, h)
    else:
        with Image.open(raw) as img:
            img.seek(0)
            scale = min(
                w / img.width if w else math.inf, h / img.height if h else math.inf, 1
            )
            frame = img.copy()
            if scale < 1:
                frame = frame.resize(
                    (
                        max(1, js_round(img.width * scale)),
                        max(1, js_round(img.height * scale)),
                    ),
                    Image.Resampling.LANCZOS,
                )
            if dest.suffix.lower() in (".jpg", ".jpeg") and frame.mode != "RGB":
                frame = frame.convert("RGB")
            frame.save(dest)


def produce(course: Course, key: str, calls: list[ImgCall], raw_dir: Path) -> Path:
    c = calls[0]
    raw = fetch_raw(c.origin or "", raw_dir)
    dest = course.root / key.lstrip("/")
    dest.parent.mkdir(parents=True, exist_ok=True)
    w, h = cap(c)
    write_image(raw, dest, w, h)
    return dest


def wanted_images(course: Course) -> tuple[dict[str, list[ImgCall]], list[ImgCall]]:
    """Path -> its calls, for the images to fetch; and the calls given a URL
    as the image (no longer supported)."""
    wanted: dict[str, list[ImgCall]] = {}
    urls: list[ImgCall] = []
    for f in typ_files(course):
        for c in img_calls(course, f):
            if URL_RE.match(c.key):
                urls.append(c)
                continue
            if not c.origin or not URL_RE.match(c.origin):
                continue
            if (course.root / c.key.lstrip("/")).exists():
                continue  # the file is there
            wanted.setdefault(c.key, []).append(c)
    return wanted, urls


def fetch_all(course: Course) -> int:
    raw_dir = course.root / ".cache" / "images" / "raw"
    wanted, urls = wanted_images(course)
    failed = 0
    for c in urls:
        failed += 1
        print(
            f'images: {course.rooted(c.file)}: #img("{c.key}"): Typst cannot '
            'fetch a URL; give the file and its origin: #img(path("images/x.webp"), '
            f'origin: "{c.key}")',
            file=sys.stderr,
        )
    if wanted:
        raw_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    for key, calls in wanted.items():
        try:
            dest = produce(course, key, calls, raw_dir)
            done += 1
            print(f"images: {course.rel(dest)} (from {calls[0].origin}): commit it")
        except Exception as e:  # reported, the other images still fetched
            failed += 1
            print(
                f"images: {key}: {e} ({course.rooted(calls[0].file)})",
                file=sys.stderr,
            )
    return 1 if failed else 0


# --- check ------------------------------------------------------------------


def check(course: Course, strict: bool = False) -> int:
    heavy = 0
    for f in walk(course.src):
        if not re.search(r"\.(png|jpe?g|gif|webp)$", f.name, re.I):
            continue
        size_bytes = f.stat().st_size
        size = ""
        wide = False
        try:
            with Image.open(f) as img:
                size = f" {img.width}x{img.height}"
                wide = max(img.width, img.height) > MAX_PX
        except Exception:  # unreadable: judged on its size alone
            pass
        if size_bytes > MAX_BYTES or wide:
            heavy += 1
            print(
                f"heavy: {course.rel(f)}  {size_bytes / 1e6:.1f} MB{size}",
            )
    print(
        f"check-images: {heavy} heavy image(s) (> {MAX_BYTES // 1_000_000} MB or "
        f"> {MAX_PX} px): shrink them"
        if heavy
        else "check-images: no heavy image"
    )
    return 1 if heavy and strict else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="typst-slides images",
        description="Fetch the missing images given by an origin, to their path.",
    )
    parser.add_argument(
        "--check", action="store_true", help="list the heavy images of the course"
    )
    parser.add_argument(
        "--strict", action="store_true", help="--check: exit 1 if there are some"
    )
    args = parser.parse_args(argv)
    course = Course()
    if args.check:
        return check(course, args.strict)
    return fetch_all(course)


if __name__ == "__main__":
    sys.exit(main())
