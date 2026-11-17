"""The engine API a template works with: its typst.toml's
`[tool.cathedra] api` (e.g. ">=3, <4"), checked against the engine's
API version (typst/VERSION; lib/slides.typ `api-version`)."""

from __future__ import annotations

import operator
import re
import tomllib
from pathlib import Path

from .paths import TYPST

OPS = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


def engine_api() -> int:
    return int((TYPST / "VERSION").read_text().strip())


def satisfies(version: int, spec: str) -> bool:
    """`spec`: comparisons separated by commas (">=3, <4")."""
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(>=|<=|==|!=|>|<)?\s*(\d+)", part)
        if not m:
            raise ValueError(f"bad API range {spec!r}")
        if not OPS[m.group(1) or "=="](version, int(m.group(2))):
            return False
    return True


def tool_table(data: dict) -> dict | None:
    """The engine's table of a typst.toml: [tool.cathedra], or the former
    [tool.typst-slides]."""
    tool = data.get("tool", {})
    return tool.get("cathedra", tool.get("typst-slides"))


def packages_of(files: list[Path]) -> dict[Path, dict]:
    """The typst.toml (with a [tool.cathedra] table, or the former
    [tool.typst-slides]) of the packages the files belong to: {toml path: its
    content}."""
    found: dict[Path, dict] = {}
    seen: set[Path] = set()
    for f in files:
        for d in Path(f).resolve().parents:
            if d in seen:
                break
            seen.add(d)
            toml = d / "typst.toml"
            if toml.is_file():
                try:
                    data = tomllib.loads(toml.read_text())
                except (OSError, tomllib.TOMLDecodeError):
                    break
                if tool_table(data) is not None:
                    found[toml] = data
                break
    return found


def api_problems(files: list[Path]) -> list[str]:
    """What is wrong with the templates `files` (a compilation's
    dependencies) use: one message each."""
    api = engine_api()
    out = []
    for toml, data in packages_of(files).items():
        pkg = data.get("package", {})
        spec = tool_table(data).get("api")
        if not spec:
            continue
        name = f"{pkg.get('name', toml.parent.name)} {pkg.get('version', '')}".strip()
        try:
            ok = satisfies(api, spec)
        except ValueError as e:
            out.append(f"{name} ({toml}): {e}")
            continue
        if not ok:
            out.append(
                f"{name} needs the cathedra API {spec}, the engine has API {api}: "
                f"update the template, or use an engine it supports ({toml})"
            )
    return out
