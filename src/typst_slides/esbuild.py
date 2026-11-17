"""The esbuild binary, to bundle a course's React widgets (widgets/index.ts).

Looked for, in order: $ESBUILD, the course's node_modules/.bin/esbuild,
`esbuild` on the PATH, else the official binary for this platform downloaded
once from the npm registry (@esbuild/<platform>, the package esbuild's own
installer uses) into the user cache: no Node needed.
"""

from __future__ import annotations

import hashlib
import io
import os
import platform
import shutil
import stat
import sys
import tarfile
import urllib.request
from pathlib import Path

import platformdirs

VERSION = "0.25.5"


def _platform() -> str:
    machine = platform.machine().lower()
    arch = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine, machine
    )
    if sys.platform == "darwin":
        return f"darwin-{arch}"
    if sys.platform.startswith("linux"):
        return f"linux-{arch}"
    if sys.platform == "win32":
        return f"win32-{arch}"
    raise RuntimeError(f"esbuild: unsupported platform {sys.platform}/{machine}")


def _download(dest: Path) -> Path:
    name = _platform()
    url = f"https://registry.npmjs.org/@esbuild/{name}/-/{name}-{VERSION}.tgz"
    print(f"esbuild: downloading {url}", file=sys.stderr)  # noqa: T201
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    # the registry's integrity check (sha512 of the tarball)
    meta_url = f"https://registry.npmjs.org/@esbuild/{name}/{VERSION}"
    try:
        import base64
        import json

        with urllib.request.urlopen(meta_url, timeout=30) as r:
            integrity = json.load(r)["dist"]["integrity"]
        algo, digest = integrity.split("-", 1)
        if hashlib.new(algo, data).digest() != base64.b64decode(digest):
            raise RuntimeError(f"esbuild: {url} does not match its integrity hash")
    except (OSError, KeyError, ValueError):
        pass
    member = "package/esbuild.exe" if sys.platform == "win32" else "package/bin/esbuild"
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        f = tar.extractfile(member)
        if f is None:
            raise RuntimeError(f"esbuild: {member} missing from {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        tmp.write_bytes(f.read())
        tmp.chmod(tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        tmp.replace(dest)
    return dest


def esbuild(course_root: Path | None = None) -> str:
    """The path of an esbuild binary (downloaded if need be)."""
    if os.environ.get("ESBUILD"):
        return os.environ["ESBUILD"]
    if course_root:
        local = course_root / "node_modules" / ".bin" / "esbuild"
        if local.exists():
            return str(local)
    found = shutil.which("esbuild")
    if found:
        return found
    exe = "esbuild.exe" if sys.platform == "win32" else "esbuild"
    cached = (
        Path(platformdirs.user_cache_dir("typst-slides")) / f"esbuild-{VERSION}" / exe
    )
    if not cached.exists():
        _download(cached)
    return str(cached)
