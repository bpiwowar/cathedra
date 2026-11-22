"""References by portable identifier (DOI, arXiv, URL), the optional Zotero
link (lib/zotero.json, local), the migration of slide-app `zotero` fields.
All data made up."""

from __future__ import annotations

import json
from pathlib import Path

from cathedra import sync, zotero
from cathedra.engine import DeckCompiler

CASES = {
    "doi://10.1234/ABC.5": "doi:10.1234/abc.5",
    "10.1234/abc.5": "doi:10.1234/abc.5",
    "https://doi.org/10.1234/abc.5": "doi:10.1234/abc.5",
    "doi:10.1234/abc.5": "doi:10.1234/abc.5",
    "10/xyz": "doi:10/xyz",
    "doi://10.48550/arXiv.2401.00001": "arxiv:2401.00001",
    "arXiv:2401.00001v3": "arxiv:2401.00001",
    "https://arxiv.org/abs/2401.00001v2": "arxiv:2401.00001",
    "http://arxiv.org/pdf/2401.00001.pdf": "arxiv:2401.00001",
    "https://www.example.org/paper/": "url:example.org/paper",
    "https://example.org/forum?id=Ab1": "url:example.org/forum?id=ab1",
    "isbn:978-0-12-345678-9": "isbn:9780123456789",
    "ISBN: 0 12 345678 X": "isbn:012345678x",
    "SomeKey2024": None,
}

BIB = """@article{doeFirst2024,
  title = {A First Paper},
  author = {Doe, Jane},
  doi = {10.1234/ABC.5},
  file = {/home/someone/Zotero/storage/X/a.pdf},
  zotero = {user:42/AAAA1111},
  date = {2024},
}

@online{roeSecond2023,
  title = {A Second Paper},
  author = {Roe, Richard},
  eprint = {2401.00001},
  eprinttype = {arXiv},
  url = {http://arxiv.org/abs/2401.00001},
  zotero={BBBB2222},
  date = {2023},
}

@book{loeThird2020,
  title = {A Made-Up Book},
  author = {Loe, Lee},
  isbn = {978-0-12-345678-9 0-12-345678-X},
  date = {2020},
}

@inproceedings{moeFourth2021,
  title = {A Made-Up Paper},
  author = {Moe, Max},
  isbn = {978-1-11-111111-1},
  date = {2021},
}
"""


def test_canonical():
    for s, c in CASES.items():
        assert sync.canonical(s) == c, s


def test_canonical_typst_parity(course, course_dir):
    """`_canonical` (lib/slides.typ) normalises as sync.canonical."""
    doc = course_dir / "parity.typ"
    doc.write_text(
        '#import "/cathedra/lib/slides.typ": _canonical\n'
        f"#metadata({json.dumps(list(CASES))}.map(_canonical))<out>\n".replace(
            "[", "("
        ).replace("]", ",)")
    )
    comp = DeckCompiler(course, doc, plain=True).compile()
    assert comp.ok, comp.diagnostics
    assert comp.query("<out>") == [list(CASES.values())]


def test_entry_ids():
    (_, a), (_, b), (_, c), (_, d) = sync.entries(BIB)
    assert sync.entry_ids(a) == ["doi:10.1234/abc.5"]
    assert sync.entry_ids(b) == ["arxiv:2401.00001"]
    assert sync.entry_ids(c) == ["isbn:9780123456789", "isbn:012345678x"]
    assert sync.entry_ids(d) == []  # a paper: its ISBN is its proceedings'


def test_migrate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    assert sync.migrate("main.bib") == 2
    text = (tmp_path / "main.bib").read_text()
    assert "zotero" not in text and "file =" not in text
    assert "doi = {10.1234/ABC.5}" in text
    assert sync.load_cache() == {
        "doeFirst2024": "user:42/AAAA1111",
        "roeSecond2023": "library:1/BBBB2222",
    }
    assert sync.migrate("main.bib") == 0  # idempotent


def test_cited(tmp_path):
    (tmp_path / "a.typ").write_text(
        '#reference(<k>, "doi://10.1234/abc.5")\n'
        '#reference(\n  "arXiv:2401.00001v1 Roe 2023, A \\"Second\\" Paper",\n'
        '  "<k2> Doe et al. 2024, A Title",\n  "A Made-Up Book",\n)\n'
    )
    assert sync.cited(tmp_path) == [
        {
            "key": None,
            "ident": "doi:10.1234/abc.5",
            "raw": "doi://10.1234/abc.5",
            "text": "",
        },
        {
            "key": None,
            "ident": "arxiv:2401.00001",
            "raw": "arXiv:2401.00001v1",
            "text": 'Roe 2023, A "Second" Paper',
        },
        {"key": "k2", "ident": None, "raw": None, "text": "Doe et al. 2024, A Title"},
        {"key": None, "ident": None, "raw": None, "text": "A Made-Up Book"},
    ]


def test_label_and_title_part():
    (_, a), (_, b), (_, c), _ = sync.entries(BIB)
    assert sync.label(a) == "Doe 2024, A First Paper"
    assert sync.label(c) == "Loe 2020, A Made-Up Book"
    many = "@article{x,\n  author = {Ab, A. and {Org-Name} and Cd, C.},\n"
    many += "  title = {{{RoFormer}}: A \\& B},\n  date = {2021-05-01},\n}"
    assert sync.label(many) == "Ab et al. 2021, RoFormer: A & B"
    assert sync.title_part("Doe et al. 2024, A Title, Again") == (
        "A Title, Again",
        "2024",
    )
    assert sync.title_part("Just a Title") == ("Just a Title", None)


def test_annotate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.typ").write_text(
        "#reference(<doeFirst2024>, <unknownKey>)\n"
        '#reference("https://doi.org/10.1234/abc.5", "10.9999/x")\n'
        '#reference("arXiv:2401.00001 Kept As Is")\n'
    )
    assert sync.annotate("main.bib", src) == 2
    assert (src / "a.typ").read_text() == (
        '#reference("<doeFirst2024> Doe 2024, A First Paper", <unknownKey>)\n'
        '#reference("https://doi.org/10.1234/abc.5 Doe 2024, A First Paper", '
        '"10.9999/x")\n'
        '#reference("arXiv:2401.00001 Kept As Is")\n'
    )
    assert sync.annotate("main.bib", src) == 0


def test_fetch_by_title(tmp_path, monkeypatch):
    """No identifier (or not in Zotero): the title of the text."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    (tmp_path / "a.typ").write_text(
        '#reference("Poe et al. 2025, A Third Paper", "A First Paper")'
    )
    seen = []

    def find_title(title, year, norm):
        seen.append((title, year))
        return "user:42/GGGG7777"

    monkeypatch.setattr(zotero, "find_title", find_title)
    monkeypatch.setattr(
        zotero,
        "biblatex",
        lambda ref: "@article{poeThird2025,\n\ttitle = {A Third Paper},\n}",
    )
    items: dict = {}
    assert sync.fetch("main.bib", tmp_path, items) == 1
    # "A First Paper": in the .bib already (by its title), not looked up
    assert seen == [("A Third Paper", "2025")]
    assert items == {"poeThird2025": "user:42/GGGG7777"}


def test_find_title_unique(monkeypatch):
    rows = {
        "/users/0": [{"data": {"key": "K1", "title": "A Title", "date": "2024-01-02"}}],
        "/groups/5": [
            {"data": {"key": "K2", "title": "A title.", "date": "2024"}},
            {"data": {"key": "K3", "title": "A Title", "date": "2019"}},
        ],
    }
    monkeypatch.setattr(
        zotero,
        "libraries",
        lambda: [("user", "42", "/users/0"), ("group", "5", "/groups/5")],
    )
    monkeypatch.setattr(
        zotero, "_json", lambda path, **p: rows[path.rsplit("/items", 1)[0]]
    )
    # My Library first; the year rules out K3
    assert zotero.find_title("A Title", "2024", sync.norm_title) == "user:42/K1"
    rows["/users/0"] = []
    assert zotero.find_title("A Title", "2024", sync.norm_title) == "group:5/K2"
    assert zotero.find_title("A Title", None, sync.norm_title) is None  # ambiguous


def test_fetch_appends_without_private_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.typ").write_text(
        '#reference("10.1234/abc.5", "https://example.org/x", "10.9999/missing")'
    )
    entry = (
        "@inproceedings{poeThird2025,\n\ttitle = {A Third Paper},\n"
        "\turl = {https://example.org/x},\n\tkeywords = {/unread},\n"
        "\tfile = {Full Text PDF:/home/someone/Zotero/storage/Y/c.pdf:application/pdf},\n}"
    )
    monkeypatch.setattr(
        zotero,
        "find",
        lambda i, canonical, written=None: (
            "user:42/CCCC3333" if i == "url:example.org/x" else None
        ),
    )
    monkeypatch.setattr(zotero, "biblatex", lambda ref: entry)
    items: dict = {}
    assert sync.fetch("main.bib", src, items) == 1
    text = (tmp_path / "main.bib").read_text()
    assert "@inproceedings{poeThird2025," in text
    assert "/unread" not in text and "c.pdf" not in text
    assert items == {"poeThird2025": "user:42/CCCC3333"}
    # cited again: in the .bib now, nothing fetched
    assert sync.fetch("main.bib", src, items) == 0


def test_fetch_refuses_a_taken_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    (tmp_path / "a.typ").write_text('#reference("https://example.org/y")')
    monkeypatch.setattr(
        zotero, "find", lambda i, canonical, written=None: "user:42/DDDD4444"
    )
    monkeypatch.setattr(zotero, "biblatex", lambda ref: "@article{doeFirst2024,\n}")
    assert sync.fetch("main.bib", tmp_path, {}) == 0
    assert (tmp_path / "main.bib").read_text() == BIB


def test_links_without_zotero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "main.bib").write_text(BIB)
    assert sync.main("main.bib") == 0
    links = json.loads((tmp_path / "lib/refs-links.json").read_text())
    assert links["doeFirst2024"]["zotero"] is None  # ZOTERO off: no Zotero link
    assert links["roeSecond2023"]["ids"] == ["arxiv:2401.00001"]


def test_reference_by_identifier(course, course_dir):
    """A DOI, a key in a string, a title cite the entry; an unknown
    identifier is a link with its text, slide `check`."""
    bib = course_dir / "main.bib"
    bib.write_text(sync.drop_fields(BIB))
    assert sync.main(str(bib)) == 0
    doc = course_dir / "refs.typ"
    doc.write_text(
        '#import "/cathedra/lib/slides.typ": *\n'
        '#course-setup(ref-links: json("/lib/refs-links.json"))\n'
        '#reference("https://doi.org/10.1234/abc.5 Doe 2024, A First Paper")\n'
        '#reference("arXiv:2401.00001v2", "isbn:0-12-345678-X")\n'
        '#reference("Moe 2021, A made-up paper", "<doeFirst2024> Doe 2024, A First Paper")\n'
        '#reference("10.9999/unknown Nobody 2020, Not There")\n'
        '#bibliography("/main.bib", title: none)\n'
    )
    comp = DeckCompiler(course, doc).compile()
    assert comp.ok, comp.diagnostics
    assert comp.query("<slide-type>") == [["check"]]
    cited = {c["key"] for c in comp.query("cite", None)}
    assert cited == {
        "<doeFirst2024>",
        "<roeSecond2023>",
        "<loeThird2020>",
        "<moeFourth2021>",
    }
    links = {
        x["dest"] for x in comp.query("link", None) if isinstance(x.get("dest"), str)
    }
    assert "https://doi.org/10.9999/unknown" in links


def test_parse_typst_parity(course, course_dir):
    """`_parse` and `_title-part` (lib/slides.typ) read as sync.parse /
    title_part."""
    cases = [
        "<k1> Doe et al. 2024, A Title",
        "doi://10.1/X Doe 2024, A Title, Again",
        "arXiv:2401.00001",
        "Just a Title",
    ]
    doc = course_dir / "parity.typ"
    doc.write_text(
        '#import "/cathedra/lib/slides.typ": _parse, _title-part, _norm-title\n'
        f"#let cases = ({', '.join(json.dumps(c) for c in cases)},)\n"
        "#metadata(cases.map(c => { let r = _parse(c); "
        "(r.key, r.ident, r.raw, r.text, _norm-title(_title-part(r.text))) }))<out>\n"
    )
    comp = DeckCompiler(course, doc, plain=True).compile()
    assert comp.ok, comp.diagnostics
    expected = []
    for c in cases:
        r = sync.parse(c)
        t = sync.norm_title(sync.title_part(r["text"])[0])
        expected.append([r["key"], r["ident"], r["raw"], r["text"], t])
    assert comp.query("<out>") == [expected]


def test_select_url(monkeypatch):
    monkeypatch.setattr(zotero, "user_id", lambda: "42")
    assert zotero.select_url("user:42/K1") == "zotero://select/library/items/K1"
    assert zotero.select_url("user:7/K1") is None  # another user's library
    assert zotero.select_url("group:5/K2") == "zotero://select/groups/5/items/K2"
    assert zotero.parse_ref("zotero://select/library/items/K3") == "library:1/K3"


def test_bib_path_is_relative(tmp_path):
    assert not Path(sync.CACHE).is_absolute()


def test_find_matches_isbn_as_written(monkeypatch):
    """Zotero stores ISBNs with hyphens: searched as written, then matched."""
    queries = []

    def fake_json(path, **params):
        queries.append(params.get("q"))
        if params.get("q") == "978-0-12-345678-9":
            return [
                # a paper of the same proceedings: the ISBN is not its own
                {
                    "data": {
                        "key": "FFFF6666",
                        "itemType": "conferencePaper",
                        "ISBN": "978-0-12-345678-9",
                    }
                },
                {
                    "data": {
                        "key": "EEEE5555",
                        "itemType": "book",
                        "ISBN": "978-0-12-345678-9",
                    }
                },
            ]
        return []

    monkeypatch.setattr(zotero, "libraries", lambda: [("user", "42", "/users/0")])
    monkeypatch.setattr(zotero, "_json", fake_json)
    ref = zotero.find("isbn:9780123456789", sync.canonical, "isbn:978-0-12-345678-9")
    assert ref == "user:42/EEEE5555"
    assert queries == ["978-0-12-345678-9"]
