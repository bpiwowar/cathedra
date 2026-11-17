# ruff: noqa: T201
"""The links of the course's references, into lib/ (generated, gitignored).

    cathedra sync <main.bib>

run from the course directory, writes lib/refs-links.json: bib key ->
{zotero, doi, url}, the links of #reference (the Zotero item in dev builds,
else the DOI, else the URL). The decks cite main.bib itself
(`#bibliography("/main.bib", style: bib-style)`), so that plain `typst
compile` works from the course's git sources.

Typst refuses a .bib with a duplicate key: so does this command (exit 1,
the duplicates listed), rather than writing a deduplicated copy. main.bib is
managed by Zotero (Better BibTeX): fix them there (merge the items, or give
them distinct citation keys).
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


def duplicates(text: str) -> dict[str, list[int]]:
    """The keys defined more than once: key -> the lines of its entries."""
    lines: dict[str, list[int]] = {}
    for m in re.finditer(r"(?m)^@\w+\{([^,\s]+),", text):
        lines.setdefault(m.group(1), []).append(text.count("\n", 0, m.start()) + 1)
    return {k: v for k, v in lines.items() if len(v) > 1}


def main(bib: str) -> int:
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
    user = zotero_user()
    links = {}
    for chunk in re.split(r"(?m)^(?=@)", text):
        m = re.match(r"@\w+\{([^,\s]+),", chunk)
        if not m:
            continue
        z = field(chunk, "zotero")
        doi = field(chunk, "doi")
        links[m.group(1)] = {
            "zotero": zotero_url(z, user) if z else None,
            # Better BibTeX short DOIs (10/abcd) resolve on doi.org as well
            "doi": f"https://doi.org/{doi}" if doi else None,
            "url": field(chunk, "url"),
        }
    (here / "lib/refs-links.json").write_text(json.dumps(links, indent=0))
    zlinks = sum(bool(v["zotero"]) for v in links.values())
    who = (
        f"Zotero user {user}"
        if user
        else "Zotero not running: user:* refs taken as yours"
    )
    print(
        f"lib/refs-links.json: {len(links)} entries, {zlinks} Zotero links ({who})",
        file=sys.stderr,
    )
    return 0
