"""The local Zotero app (its local API, http://127.0.0.1:23119/api), optional.

Zotero 7: Settings → Advanced → "Allow other applications on this computer
to communicate with Zotero". Everything here returns None / [] when Zotero is
not running: the course then builds without it.

A Zotero item is a *ref*, `<scope>:<id>/<KEY>`: `user:<user id>/KEY` (My
Library) or `group:<group id>/KEY`. Refs are local to whoever has the item:
they live in the course's lib/zotero.json (gitignored), never in its .bib.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from functools import cache

API = "http://127.0.0.1:23119/api"
TIMEOUT = 5


def _get(path: str, **params) -> bytes | None:
    url = f"{API}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
            return r.read()
    except (OSError, ValueError):
        return None


def _json(path: str, **params):
    data = _get(path, **params)
    try:
        return json.loads(data) if data else None
    except ValueError:
        return None


@cache
def user_id() -> str | None:
    """The local user's Zotero id (None: Zotero not running, or an empty
    library)."""
    items = _json("/users/0/items", limit=1, format="json")
    try:
        lib = items[0]["library"]["id"] if items else None
    except (KeyError, IndexError, TypeError):
        return None
    return str(lib) if lib else None


def available() -> bool:
    return _get("/users/0/groups", limit=1) is not None


@cache
def libraries() -> list[tuple[str, str, str]]:
    """(scope, id, API path) of each local library: My Library, the groups."""
    uid = user_id()
    libs = [("user", uid, "/users/0")] if uid else [("library", "1", "/users/0")]
    for g in _json("/users/0/groups", format="json", limit=100) or []:
        gid = g.get("id") or g.get("data", {}).get("id")
        if gid:
            libs.append(("group", str(gid), f"/groups/{gid}"))
    return libs


def _path(ref: str) -> str | None:
    m = re.fullmatch(r"(user|library|group):(\d+)/(\w+)", ref)
    if not m:
        return None
    scope, id_, key = m.groups()
    if scope == "group" or (scope == "library" and id_ != "1"):
        return f"/groups/{id_}/items/{key}"
    return f"/users/0/items/{key}"


def parse_ref(s: str) -> str | None:
    """A ref from a slide-app `zotero={…}` field (`user:ID/KEY`,
    `group:ID/KEY`, `library:1/KEY`, a bare KEY; `;`-separated: the first)
    or a zotero://select link."""
    s = s.split(";")[0].strip()
    if m := re.search(r"zotero://\w+/groups/(\d+)/items/(\w+)", s):
        return f"group:{m[1]}/{m[2]}"
    if m := re.search(r"zotero://\w+/users/(\d+)/items/(\w+)", s):
        return f"user:{m[1]}/{m[2]}"
    if m := re.search(r"zotero://\w+/library(?:/(\d+))?/items/(\w+)", s):
        return f"library:{m[1] or 1}/{m[2]}"
    if re.fullmatch(r"(user|library|group):\d+/\w+", s):
        return s
    if re.fullmatch(r"\w+", s):
        return f"library:1/{s}"
    return None


def select_url(ref: str) -> str | None:
    """The zotero:// link the local app opens; None for another user's
    library (unreachable here)."""
    m = re.fullmatch(r"(user|library|group):(\d+)/(\w+)", ref)
    if not m:
        return None
    scope, id_, key = m.groups()
    if scope == "group" or (scope == "library" and id_ != "1"):
        return f"zotero://select/groups/{id_}/items/{key}"
    uid = user_id()
    if scope == "user" and uid is not None and uid != id_:
        return None
    return f"zotero://select/library/items/{key}"


def _ids(data: dict, canonical) -> set[str]:
    """The identifiers of a Zotero item (its JSON `data`), canonical."""
    fields = [data.get("DOI"), data.get("url"), data.get("archiveID")]
    extra = data.get("extra") or ""
    fields += re.findall(r"(?im)^(?:DOI|arXiv):\s*(\S+)", extra)
    if data.get("itemType") == "book":  # a paper's ISBN is its proceedings'
        fields += [
            "isbn:" + i
            for i in re.findall(r"[0-9][0-9-]{8,}[0-9xX]", data.get("ISBN") or "")
        ]
    return {c for f in fields if f and (c := canonical(f))}


def find(ident: str, canonical, written: str | None = None) -> str | None:
    """The ref of the item whose DOI / URL / arXiv id / ISBN is `ident`
    (canonical form, `canonical()` normalising the item's fields alike), in
    any library. Zotero's search is textual: `written` (the identifier as
    cited, e.g. an ISBN with its hyphens) is searched first."""
    bare = ident.split(":", 1)[1]
    queries = [
        q.split(":", 1)[1].strip() if q.lower().startswith("isbn:") else q
        for q in (written,)
        if q
    ]
    for query in dict.fromkeys([*queries, bare]):
        for scope, id_, path in libraries():
            items = _json(
                f"{path}/items",
                q=query,
                qmode="everything",
                format="json",
                limit=50,
                itemType="-attachment",
            )
            for item in items or []:
                data = item.get("data", item)
                if ident in _ids(data, canonical):
                    return f"{scope}:{id_}/{data['key']}"
    return None


def biblatex(ref: str) -> str | None:
    """The item exported as biblatex (Better BibTeX keys, when installed)."""
    path = _path(ref)
    data = _get(path, format="biblatex") if path else None
    text = data.decode() if data else ""
    return text.strip() if text.strip().startswith("@") else None


def find_title(title: str, year: str | None, norm) -> str | None:
    """The ref of the one item with this title (`norm()` alike) and year (if
    given): My Library first; None when none or several (ambiguous)."""
    if not title:
        return None
    target = norm(title)
    found = []
    for scope, id_, path in libraries():
        items = _json(
            f"{path}/items",
            q=title,
            qmode="titleCreatorYear",
            format="json",
            limit=50,
            itemType="-attachment",
        )
        for item in items or []:
            data = item.get("data", item)
            if norm(data.get("title") or "") != target:
                continue
            if year and year not in (data.get("date") or ""):
                continue
            found.append((scope, f"{scope}:{id_}/{data['key']}"))
    mine = [r for s, r in found if s != "group"]
    if len(mine) == 1:
        return mine[0]
    return found[0][1] if len(found) == 1 else None
