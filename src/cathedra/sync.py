# ruff: noqa: T201
"""The course's references: lib/refs-links.json, and (optional) Zotero.

    cathedra sync <main.bib> [--zotero] [--src DIR] [--refresh]
    cathedra sync <main.bib> --migrate

run from the course directory. Writes lib/refs-links.json (generated,
gitignored): bib key -> {zotero, doi, url, ids}, read by `#reference` (its
link: the Zotero item in dev builds, else the DOI, else the URL; `ids`: the
entry's identifiers, so that `#reference("doi://…")` finds it).

A reference is cited by its bib key or by a portable identifier: a DOI
(`doi://10.…`, `10.…`, `https://doi.org/…`), an arXiv id or link, a URL.
`canonical()` normalises them; `#reference` (lib/slides.typ) does the same.

With --zotero (the course's ZOTERO option), the local Zotero app:
- the identifiers cited in the sources (--src) that no entry of the .bib has
  are looked up in Zotero (every library) and their entry appended to the
  .bib (a file of the course: committed, so that others have it);
- the dev links to the Zotero items, user specific, are kept in
  lib/zotero.json (gitignored): bib key -> ref (`user:ID/KEY`), found from
  the entries' identifiers; null: not found (looked up again with --refresh).

--migrate moves the slide-app `zotero = {…}` fields of the .bib into
lib/zotero.json, and drops the `file = {…}` fields (local paths).

Typst refuses a .bib with a duplicate key: so does this command (exit 1,
the duplicates listed). Fix them in Zotero (merge the items, or give them
distinct citation keys).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

from . import zotero

# the fields an appended entry loses: user specific (local paths, tags)
PRIVATE_FIELDS = ("file", "keywords", "zotero")


# ------------------------------------------------------------- identifiers
def _arxiv(i: str) -> str:
    return "arxiv:" + re.sub(r"v\d+$", "", i.strip().lower())


def canonical(s: str) -> str | None:
    """`doi:<lower case DOI>`, `arxiv:<id without version>`,
    `isbn:<digits>` (`isbn:978-…`: no hyphen, no space) or
    `url:<host/path, no scheme, www. or final />`; None: not an identifier.
    Mirrored by `_canonical` in lib/slides.typ."""
    s = s.strip().lower()
    m = re.fullmatch(r"(?:doi:(?://)?\s*|https?://(?:dx\.)?doi\.org/)(\S+)", s)
    doi = m[1] if m else (s if re.fullmatch(r"10\.\d{4,}/\S+|10/\w+", s) else None)
    if doi:
        if a := re.fullmatch(r"10\.48550/arxiv\.(\S+)", doi):
            return _arxiv(a[1])
        return "doi:" + doi
    if m := re.fullmatch(r"arxiv:\s*(\S+)", s):
        return _arxiv(m[1])
    if m := re.fullmatch(r"isbn:\s*([0-9x][0-9x -]*)", s):
        return "isbn:" + re.sub(r"[ -]", "", m[1])
    if m := re.fullmatch(
        r"https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf)/(.+?)(?:\.pdf)?/?", s
    ):
        return _arxiv(m[1])
    if m := re.fullmatch(r"https?://(?:www\.)?(\S+?)/?", s):
        return "url:" + m[1]
    return None


# --------------------------------------------------------------------- bib
def field(chunk: str, name: str) -> str | None:
    m = re.search(rf"(?im)^\s*{name}\s*=\s*\{{([^}}]+)\}}", chunk)
    return m.group(1).strip() if m else None


def bfield(chunk: str, name: str) -> str | None:
    """A field with nested braces (`title = {{RoFormer}}: …}`), raw."""
    m = re.search(rf"(?im)^\s*{name}\s*=\s*\{{", chunk)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(chunk) and depth:
        depth += {"{": 1, "}": -1}.get(chunk[i], 0)
        i += 1
    return chunk[m.end() : i - 1].strip() if depth == 0 else None


def detex(s: str) -> str:
    """Braces and the common escapes of a BibTeX value out."""
    s = re.sub(r"\\(textbackslash|[&%$#_])", lambda m: m[1][-1:], s)
    return re.sub(r"\s+", " ", s.replace("{", "").replace("}", "")).strip()


def norm_title(s: str) -> str:
    """A title for comparison: lower case, letters and digits only.
    Mirrored by `_norm-title` in lib/slides.typ."""
    return re.sub(r"[\W_]+", "", s.lower())


def label(chunk: str) -> str:
    """`Author et al. 2024, Title`: what a `#reference` keeps next to its
    identifier (as the Zotero action copies it)."""
    names = [
        detex(a).split(",")[0].strip()
        for a in re.split(
            r"\s+and\s+", bfield(chunk, "author") or bfield(chunk, "editor") or ""
        )
        if a.strip()
    ]
    who = f"{names[0]} et al." if len(names) > 2 else " and ".join(names)
    date = field(chunk, "date") or field(chunk, "year") or ""
    year = m[0] if (m := re.search(r"\d{4}", date)) else ""
    head = " ".join(x for x in (who, year) if x)
    title = detex(bfield(chunk, "title") or "")
    return f"{head}, {title}" if head else title


def title_part(text: str) -> tuple[str, str | None]:
    """(title, year) of a reference's text `Author et al. 2024, Title`;
    the whole text is the title when it has no `year, `."""
    if m := re.fullmatch(r".*?\b(\d{4})[a-z]?,\s*(.+)", text.strip()):
        return m[2], m[1]
    return text.strip(), None


def entries(text: str) -> list[tuple[str, str]]:
    """(key, chunk) of each entry."""
    out = []
    for chunk in re.split(r"(?m)^(?=@)", text):
        if m := re.match(r"@\w+\{([^,\s]+),", chunk):
            out.append((m.group(1), chunk))
    return out


def isbns(value: str) -> list[str]:
    """The ISBNs of a field (Zotero: several, separated by spaces or commas)."""
    return re.findall(r"[0-9][0-9-]{8,}[0-9xX]", value)


BOOK_TYPES = ("book", "mvbook", "collection", "mvcollection", "reference")


def is_book(chunk: str) -> bool:
    """An entry that is a book: its ISBN identifies it (an article or a
    chapter shares the ISBN of its proceedings / book)."""
    m = re.match(r"@(\w+)\{", chunk)
    return bool(m) and m[1].lower() in BOOK_TYPES


def entry_ids(chunk: str) -> list[str]:
    ids = []
    if doi := field(chunk, "doi"):
        ids.append(canonical(doi) or "doi:" + doi.lower())
    if url := field(chunk, "url"):
        if c := canonical(url):
            ids.append(c)
    kind = field(chunk, "eprinttype") or field(chunk, "archiveprefix") or ""
    if (e := field(chunk, "eprint")) and kind.lower() == "arxiv":
        ids.append(_arxiv(e))
    if is_book(chunk):  # a paper's ISBN is its proceedings': shared
        for isbn in isbns(field(chunk, "isbn") or ""):
            ids.append(canonical("isbn:" + isbn))
    return list(dict.fromkeys(ids))


def duplicates(text: str) -> dict[str, list[int]]:
    """The keys defined more than once: key -> the lines of its entries."""
    lines: dict[str, list[int]] = {}
    for m in re.finditer(r"(?m)^@\w+\{([^,\s]+),", text):
        lines.setdefault(m.group(1), []).append(text.count("\n", 0, m.start()) + 1)
    return {k: v for k, v in lines.items() if len(v) > 1}


def drop_fields(chunk: str, names=PRIVATE_FIELDS) -> str:
    """The entry without these fields (one line each, as Zotero writes them)."""
    alt = "|".join(names)
    return re.sub(rf"(?im)^[ \t]*(?:{alt})\s*=\s*\{{.*\}},?[ \t]*\n", "", chunk)


# -------------------------------------------------------------- the cache
CACHE = pathlib.Path("lib/zotero.json")


def load_cache() -> dict[str, str | None]:
    try:
        return json.loads(CACHE.read_text()).get("items", {})
    except (OSError, ValueError):
        return {}


def save_cache(items: dict[str, str | None]) -> None:
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({"items": dict(sorted(items.items()))}, indent=0))


def migrate(bib: str) -> int:
    """The slide-app `zotero = {…}` fields -> lib/zotero.json; the `file`
    fields dropped. Returns the number of entries changed."""
    path = pathlib.Path(bib)
    text = path.read_text()
    items = load_cache()
    out, changed = [], 0
    for chunk in re.split(r"(?m)^(?=@)", text):
        m = re.match(r"@\w+\{([^,\s]+),", chunk)
        if m and (z := field(chunk, "zotero")) and (ref := zotero.parse_ref(z)):
            items.setdefault(m.group(1), ref)
        new = drop_fields(chunk, ("file", "zotero")) if m else chunk
        changed += new != chunk
        out.append(new)
    if changed:
        path.write_text("".join(out))
    save_cache(items)
    print(
        f"{bib}: {changed} entries cleaned; {CACHE}: {len(items)} items",
        file=sys.stderr,
    )
    return changed


# ------------------------------------------------------- cited references
ARG = re.compile(r'"(?:[^"\\]|\\.)*"|<[^>]*>')
REFERENCE = re.compile(r"reference\(((?:\s*(?:" + ARG.pattern + r")\s*,?)+)\s*\)")


def unquote(tok: str) -> str:
    return re.sub(r"\\(.)", r"\1", tok[1:-1])


def quote(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse(s: str) -> dict:
    """A `#reference` string: `<key> text`, `<identifier> text` or a text
    (a title): {key, ident (canonical), raw (as written), text}. Mirrored by
    `_parse` in lib/slides.typ."""
    s = s.strip()
    if m := re.fullmatch(r"<([^>]+)>\s*(.*)", s, re.S):
        return {"key": m[1], "ident": None, "raw": None, "text": m[2]}
    tok, _, rest = s.partition(" ")
    if c := canonical(tok):
        return {"key": None, "ident": c, "raw": tok, "text": rest.strip()}
    return {"key": None, "ident": None, "raw": None, "text": s}


def cited(src: pathlib.Path) -> list[dict]:
    """The references of the sources' `#reference(…)` strings (a label
    `<key>` alone: in the .bib already)."""
    out = {}
    for f in sorted(src.rglob("*.typ")):
        for m in REFERENCE.finditer(f.read_text(errors="replace")):
            for tok in ARG.findall(m.group(1)):
                if tok.startswith('"'):
                    r = parse(unquote(tok))
                    out.setdefault((r["key"], r["ident"], r["text"]), r)
    return list(out.values())


def fetch(bib: str, src: pathlib.Path, items: dict) -> int:
    """Append the cited references missing from the .bib, from Zotero: by
    identifier, else by title (the text of the reference). Returns the
    number appended."""
    path = pathlib.Path(bib)
    text = path.read_text()
    known = {i for _, c in entries(text) for i in entry_ids(c)}
    keys = {k for k, _ in entries(text)}
    titles = {norm_title(detex(bfield(c, "title") or "")) for _, c in entries(text)}
    added = []
    for r in cited(src):
        title, year = title_part(r["text"])
        if (
            (r["key"] and r["key"] in keys)
            or (r["ident"] and r["ident"] in known)
            or (not r["key"] and not r["ident"] and norm_title(title) in titles)
            or not (r["ident"] or title)
        ):
            continue
        written = r["raw"] or r["text"] or f"<{r['key']}>"
        ref = zotero.find(r["ident"], canonical, r["raw"]) if r["ident"] else None
        if not ref and title:
            ref = zotero.find_title(title, year, norm_title)
        entry = zotero.biblatex(ref) if ref else None
        if not entry:
            print(f"reference not in Zotero: {written}", file=sys.stderr)
            continue
        key = re.match(r"@\w+\{([^,\s]+),", entry).group(1)
        if key in keys:
            print(
                f"reference {written}: Zotero gives the key {key}, already in "
                f"{bib} for another entry: cite it as <{key}>, or fix it in Zotero",
                file=sys.stderr,
            )
            continue
        keys.add(key)
        known.update(entry_ids(entry))
        titles.add(norm_title(detex(bfield(entry, "title") or "")))
        items[key] = ref
        added.append(drop_fields(entry))
        print(f"{bib}: added {key} ({written})", file=sys.stderr)
    if added:
        with path.open("a") as f:
            f.write("".join(f"\n{e}\n" for e in added))
    return len(added)


def link_items(text: str, items: dict, refresh: bool) -> None:
    """Find in Zotero the entries not in the cache (by their identifiers)."""
    for key, chunk in entries(text):
        if key in items and (items[key] or not refresh):
            continue
        # the ISBNs as written (hyphens): Zotero's search is textual
        written = {canonical("isbn:" + x): x for x in isbns(field(chunk, "isbn") or "")}
        items[key] = next(
            (
                r
                for i in entry_ids(chunk)
                if (r := zotero.find(i, canonical, written.get(i)))
            ),
            None,
        ) or zotero.find_title(*title_part(label(chunk)), norm_title)


# ---------------------------------------------------------------- annotate
def annotate(bib: str, src: pathlib.Path) -> int:
    """Give the `#reference` of the sources their text (`Author et al.
    year, Title`, from the .bib): `<key>` -> `"<key> text"`, `"doi://…"` ->
    `"doi://… text"`; a reference with a text, or not in the .bib, is left
    alone. Returns the number of references changed."""
    text = pathlib.Path(bib).read_text()
    labels = {k: label(c) for k, c in entries(text)}
    by_id = {i: k for k, c in entries(text) for i in entry_ids(c)}
    count = 0

    def arg(tok: str) -> str:
        nonlocal count
        if tok.startswith("<"):
            key = tok[1:-1]
            new = quote(f"<{key}> {labels[key]}") if labels.get(key) else tok
        else:
            r = parse(unquote(tok))
            key = by_id.get(r["ident"]) if r["ident"] and not r["text"] else None
            new = quote(f"{r['raw']} {labels[key]}") if labels.get(key) else tok
        count += new != tok
        return new

    for f in sorted(src.rglob("*.typ")):
        old = f.read_text()
        new = REFERENCE.sub(
            lambda m: (
                m[0][: m.start(1) - m.start(0)]
                + ARG.sub(lambda a: arg(a[0]), m[1])
                + m[0][m.end(1) - m.start(0) :]
            ),
            old,
        )
        if new != old:
            f.write_text(new)
    print(f"annotate: {count} reference(s) given their title", file=sys.stderr)
    return count


# -------------------------------------------------------------------- main
def main(
    bib: str,
    use_zotero: bool = False,
    src: str | None = None,
    refresh: bool = False,
) -> int:
    here = pathlib.Path.cwd()
    text = pathlib.Path(bib).read_text()
    dups = duplicates(text)
    if dups:
        for k, at in dups.items():
            where = ", ".join(f"{bib}:{n}" for n in at)
            print(f"error: duplicate bib key {k} ({where})", file=sys.stderr)
        print(
            f"sync: {len(dups)} duplicate key(s): Typst refuses the bibliography; "
            "fix them in Zotero (merge the items or change their citation keys)",
            file=sys.stderr,
        )
        return 1
    (here / "lib").mkdir(exist_ok=True)
    items = load_cache()
    online = use_zotero and zotero.available()
    if use_zotero and not online:
        print("sync: Zotero is not running: no reference fetched", file=sys.stderr)
    if online:
        if src and fetch(bib, pathlib.Path(src), items):
            text = pathlib.Path(bib).read_text()
        link_items(text, items, refresh)
        save_cache(items)
    links = {}
    for key, chunk in entries(text):
        ref = items.get(key) if use_zotero else None
        doi = field(chunk, "doi")
        links[key] = {
            "zotero": zotero.select_url(ref) if ref else None,
            # Better BibTeX short DOIs (10/abcd) resolve on doi.org as well
            "doi": f"https://doi.org/{doi}" if doi else None,
            "url": field(chunk, "url"),
            "ids": entry_ids(chunk),
            "title": norm_title(detex(bfield(chunk, "title") or "")),
        }
    (here / "lib/refs-links.json").write_text(json.dumps(links, indent=0))
    zlinks = sum(bool(v["zotero"]) for v in links.values())
    print(
        f"lib/refs-links.json: {len(links)} entries, {zlinks} Zotero links",
        file=sys.stderr,
    )
    return 0
