# ruff: noqa: T201
"""The course's bibliography for Typst, into lib/ (generated, gitignored).

    typst-slides sync <main.bib>

run from the course directory, writes:

- lib/refs.bib: main.bib (Zotero / Better BibTeX) without duplicate keys
- lib/refs-links.json: bib key -> {zotero, doi, url}, the links of #reference
  (slide-app's <Cite>: the Zotero item in dev builds, else the DOI, else the URL)
- lib/refs.csl: the engine's citation style (typst/csl/normal.csl)

Typst refuses a .bib with a duplicate key, citation-js (slide-app) does not;
main.bib is managed by Zotero, so it is deduplicated here (first entry wins)
rather than edited. Duplicates are reported so they can be fixed in Zotero.
"""

import json
import pathlib
import re
import sys
import urllib.request


def field(chunk: str, name: str) -> str | None:
    m = re.search(rf"(?im)^\s*{name}\s*=\s*\{{([^}}]+)\}}", chunk)
    return m.group(1).strip() if m else None


def zotero_user() -> str | None:
    """The local Zotero user's id, from the desktop app's local API (as
    slide-app's getCurrentUserId); None when Zotero is not running."""
    try:
        url = "http://127.0.0.1:23119/api/users/0/items?limit=1&format=json"
        with urllib.request.urlopen(url, timeout=2) as r:
            items = json.load(r)
        lib = items[0]["library"]["id"] if items else None
        return str(lib) if lib else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def zotero_url(refs: str, user: str | None) -> str | None:
    """First link the local Zotero can open, from `zotero={user:ID/KEY; group:N/KEY…}`
    or a bare `zotero={KEY}` (an item of the local library).

    `user:<id>` is a personal library: the local "My Library" only when <id>
    is the local user (unknown user: assumed so, as slide-app does); another
    user's item is unreachable here, so the reference falls back to its DOI.
    """
    if re.fullmatch(r"\s*\w+\s*", refs):  # a bare item key: the local library
        return f"zotero://select/library/items/{refs.strip()}"
    for ref in refs.split(";"):
        m = re.fullmatch(r"\s*(\w+):(\d+)/(\w+)\s*", ref)
        if not m:
            continue
        scope, id_, key = m.groups()
        if scope == "group" or (scope == "library" and id_ != "1"):
            return f"zotero://select/groups/{id_}/items/{key}"
        if scope == "library" or (scope == "user" and (user is None or user == id_)):
            return f"zotero://select/library/items/{key}"
    return None


def main(bib: str) -> None:
    engine = pathlib.Path(__file__).resolve().parent / "typst"
    here = pathlib.Path.cwd()
    (here / "lib").mkdir(exist_ok=True)
    text = pathlib.Path(bib).read_text()
    chunks = re.split(r"(?m)^(?=@)", text)
    user = zotero_user()
    seen, out, links = set(), [], {}
    for chunk in chunks:
        m = re.match(r"@\w+\{([^,\s]+),", chunk)
        if m and m.group(1) in seen:
            print(f"duplicate bib key skipped: {m.group(1)}", file=sys.stderr)
            continue
        if m:
            seen.add(m.group(1))
            z = field(chunk, "zotero")
            doi = field(chunk, "doi")
            links[m.group(1)] = {
                "zotero": zotero_url(z, user) if z else None,
                # Better BibTeX short DOIs (10/abcd) resolve on doi.org as well
                "doi": f"https://doi.org/{doi}" if doi else None,
                "url": field(chunk, "url"),
            }
        out.append(chunk)
    (here / "lib/refs.bib").write_text("".join(out))
    (here / "lib/refs-links.json").write_text(json.dumps(links, indent=0))
    print(f"lib/refs.bib: {len(seen)} entries", file=sys.stderr)
    zlinks = sum(bool(v["zotero"]) for v in links.values())
    who = (
        f"Zotero user {user}"
        if user
        else "Zotero not running: user:* refs taken as yours"
    )
    print(f"lib/refs-links.json: {zlinks} Zotero links ({who})", file=sys.stderr)
    (here / "lib/refs.csl").write_text((engine / "csl/normal.csl").read_text())
