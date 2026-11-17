"""The native backend: compilation, diagnostics, web pages, PDF, queries."""

from __future__ import annotations

import base64
import re
import struct
import zlib
from pathlib import Path

from cathedra.engine import DeckCompiler
from cathedra.paths import Course


def png(w: int = 2, h: int = 2) -> bytes:
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


PLAIN = """#set page(width: 200pt, height: 100pt)
= Hello <h>
#link("https://example.org")[out] and #link(<target>)[in], #link("zotero://select/x")[z]
#metadata((a: 1))<meta>
#pagebreak()
Second page #image("x.png", width: 20pt) <target>
"""


def plain(tmp_path: Path, text: str = PLAIN):
    (tmp_path / "doc.typ").write_text(text)
    (tmp_path / "x.png").write_bytes(png())
    course = Course(tmp_path, ".")
    return DeckCompiler(course, tmp_path / "doc.typ").compile()


def test_compile_and_pages(tmp_path):
    comp = plain(tmp_path)
    assert comp.ok and comp.num_pages == 2
    assert {p.name for p in comp.dependencies} == {"doc.typ", "x.png"}
    pages = comp.pages()
    assert (pages.width, pages.height) == (200, 100)
    first, second = pages.pages[0][1], pages.pages[1][1]
    # the contract of docs/viewer.md
    assert first.startswith("<svg") and 'class="typst-svg"' in first
    assert '<g class="typst-page">' in first
    assert "<symbol" not in first and "<symbol" in pages.glyphs[1]
    assert pages.glyphs[0].startswith("glyphs-")
    assert re.search(r'<div class="tsel"[^>]*>Hello</div>', first)
    assert 'target="_blank"' in first and 'href="https://example.org"' in first
    assert re.search(r'<a [^>]*xlink:href="zotero:select/x"|zotero://select/x', first)
    assert re.search(r"handleTypstLocation\(this, 2, ", first)
    # the image as a file
    (name,) = pages.images
    assert name.startswith("img-") and name.endswith(".png")
    assert f'href="svg/{name}"' in second and "data:" not in second
    # hashes name the content
    assert len({h for h, _ in pages.pages}) == 2


def test_pages_are_cached_and_stable(tmp_path):
    comp = plain(tmp_path)
    a = comp.pages()
    b = comp.pages()
    assert a.pages == b.pages


def test_query_and_labels(tmp_path):
    comp = plain(tmp_path)
    assert comp.query("<meta>") == [{"a": 1}]
    labels = comp.labels(["meta", "nothing"])
    assert labels == {"meta": [{"a": 1}], "nothing": []}


def test_pdf_and_png(tmp_path):
    comp = plain(tmp_path)
    assert comp.pdf().startswith(b"%PDF")
    pics = comp.png(36)
    assert len(pics) == 2 and pics[0].startswith(b"\x89PNG")


def test_errors_and_warnings(tmp_path):
    comp = plain(tmp_path, "#let x = 1\n#foo(x)\n")
    assert not comp.ok
    (err,) = comp.errors
    assert err.message == "unknown variable: foo"
    assert "doc.typ:2:1" in err.text and "^^^" in err.text


def test_incremental(tmp_path):
    (tmp_path / "doc.typ").write_text(PLAIN)
    (tmp_path / "x.png").write_bytes(png())
    compiler = DeckCompiler(Course(tmp_path, "."), tmp_path / "doc.typ")
    before = compiler.compile().pages().pages
    (tmp_path / "doc.typ").write_text(PLAIN.replace("Second page", "2nd page"))
    after = compiler.compile().pages().pages
    assert before[0] == after[0] and before[1] != after[1]


def test_inputs(tmp_path):
    comp = plain(tmp_path, '#metadata(sys.inputs.at("target", default: "print"))<t>')
    assert comp.query("<t>") == ["print"]
    (tmp_path / "doc.typ").write_text(
        '#metadata(sys.inputs.at("target", default: "print"))<t>'
    )
    web = DeckCompiler(
        Course(tmp_path, "."), tmp_path / "doc.typ", {"target": "web"}
    ).compile()
    assert web.query("<t>") == ["web"]


def test_base64_png_helper():
    assert base64.b64encode(png())
