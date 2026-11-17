# ruff: noqa: T201
"""Install the VS Code "show the slide under the cursor" machinery in a course.

    python -m cathedra.vscode [--project-dir <path>] [--course-dir <path>]
        [--keybinding [<keys>]] [--editor <name>]
    (or: make install-vscode)

- .vscode/tasks.json gets a task "Show slide in Typst deck", which runs
  `make open-slide FILE=${file} LINE=${lineNumber}` in the course directory
  (`cathedra open-slide`: GET /goto?file=&line= on the deck's dev
  servers) for the file and cursor line being edited;
- .vscode/settings.json gets the Tinymist root and font path that the decks'
  root-absolute imports (`/common/course.typ`) need;
- so do the `.code-workspace` files of the project directory and its
  ancestors that list it among their folders (absolute paths there: a
  multi-root workspace ignores the folders' tinymist.* settings, and Tinymist
  expands ${workspaceFolder} to the workspace's FIRST folder);
- with --keybinding, a shortcut in the USER keybindings.json (VS Code has no
  per-workspace keybindings).

--course-dir says where the course is when it is not the project (workspace)
directory. Idempotent: re-running refreshes our task and settings in place
and leaves everything else untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from .paths import FONTS

TASK_LABEL = "Show slide in Typst deck"
DEFAULT_KEY = "cmd+alt+o" if sys.platform == "darwin" else "ctrl+alt+o"
EXT = ".typ"


# --- JSONC ------------------------------------------------------------------


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*[\s\S]*?\*/", "", text)
    return re.sub(r"(^|[^:])//.*$", r"\1", text, flags=re.M)


def strip_jsonc(text: str) -> str:
    """Comments and trailing commas removed."""
    return re.sub(r",(\s*[}\]])", r"\1", strip_comments(text))


def read_jsonc(file: Path, fallback):
    """A JSONC file (VS Code allows // and /* */ comments), or `fallback` if
    it is absent. Raises ValueError on genuinely broken JSON."""
    if not file.exists():
        return fallback
    return json.loads(strip_comments(file.read_text(encoding="utf-8")))


def dump(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


# --- what goes in -------------------------------------------------------------


def in_workspace(project_dir: Path, path: Path) -> str:
    """`path` in ${workspaceFolder} terms; absolute when outside the project
    (the engine installed in a virtual environment elsewhere)."""
    rel = Path(os.path.relpath(path, project_dir)).as_posix()
    if rel == ".":
        return "${workspaceFolder}"
    if rel.startswith("../"):
        return path.as_posix()
    return "${workspaceFolder}/" + rel


def our_task(project_dir: Path, course_dir: Path) -> dict:
    return {
        "label": TASK_LABEL,
        "type": "process",
        "command": "make",
        "args": ["open-slide", "FILE=${file}", "LINE=${lineNumber}"],
        "options": {"cwd": in_workspace(project_dir, course_dir)},
        "presentation": {"reveal": "silent", "panel": "shared", "close": True},
        "problemMatcher": [],
    }


def install_task(project_dir: Path, task: dict) -> str:
    """Merge our task into .vscode/tasks.json; the message to show."""
    tasks_path = project_dir / ".vscode" / "tasks.json"
    existed = tasks_path.exists()
    try:
        config = read_jsonc(tasks_path, {"version": "2.0.0", "tasks": []})
    except ValueError as e:
        raise SystemExit(
            f"✗ Could not parse {tasks_path} (comments are fine, trailing "
            f"commas are not).\n  Fix or remove it, then re-run. Parser said: {e}"
        ) from e
    if not isinstance(config.get("tasks"), list):
        config["tasks"] = []
    config.setdefault("version", "2.0.0")
    before = next(
        (t for t in config["tasks"] if t and t.get("label") == TASK_LABEL), None
    )
    config["tasks"] = [
        t for t in config["tasks"] if not t or t.get("label") != TASK_LABEL
    ]
    config["tasks"].append(task)
    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    tasks_path.write_text(dump(config), encoding="utf-8")
    verb = (
        "Created"
        if not existed
        else "Updated"
        if before != task
        else "Already up to date —"
    )
    return f'✓ {verb} .vscode/tasks.json (task "{TASK_LABEL}")'


def install_settings(project_dir: Path, wanted: dict) -> str:
    """Set the Tinymist root and fonts in .vscode/settings.json."""
    settings_path = project_dir / ".vscode" / "settings.json"
    try:
        settings = read_jsonc(settings_path, {})
    except ValueError as e:
        return (
            f"✗ Could not parse {settings_path}: {e}\n"
            "  Add tinymist.rootPath / tinymist.fontPaths by hand (docs/course.md)."
        )
    changed = any(settings.get(k) != v for k, v in wanted.items())
    settings.update(wanted)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(dump(settings), encoding="utf-8")
    verb = "Updated" if changed else "Already up to date —"
    return f"✓ {verb} .vscode/settings.json (tinymist.rootPath, tinymist.fontPaths)"


# --- multi-root workspaces ------------------------------------------------------


def _covers(ws_dir: Path, folders, d: Path) -> bool:
    for f in folders:
        if not isinstance(f, dict) or not isinstance(f.get("path"), str):
            continue
        r = os.path.relpath(d, (ws_dir / f["path"]).resolve())
        if r == "." or (not r.startswith("..") and not os.path.isabs(r)):
            return True
    return False


def find_workspace_files(d: Path) -> list[Path]:
    """The .code-workspace files in `d` and its ancestors that list `d` (or a
    folder containing it) among their folders."""
    found = []
    for ws_dir in [d, *d.parents]:
        try:
            names = sorted(
                n for n in os.listdir(ws_dir) if n.endswith(".code-workspace")
            )
        except OSError:
            continue
        for n in names:
            ws = ws_dir / n
            try:
                folders = read_jsonc(ws, {}).get("folders") or []
            except (ValueError, OSError, AttributeError):
                continue
            if _covers(ws_dir, folders, d):
                found.append(ws)
    return found


def update_workspace_settings(ws: Path, wanted: dict) -> str:
    """Set `wanted` in the "settings" of a .code-workspace file, editing its
    text in place (it usually has comments a JSON round trip would drop);
    rewritten as plain JSON only when a key cannot be placed by hand."""
    current = read_jsonc(ws, {})
    settings = current.get("settings") or {}
    stale = [k for k, v in wanted.items() if settings.get(k) != v]
    if not stale:
        return "Already up to date —"
    text = ws.read_text(encoding="utf-8")
    missing = []
    for k in stale:
        value = json.dumps(wanted[k], ensure_ascii=False)
        regex = re.compile(rf'("{re.escape(k)}"\s*:\s*)("(?:[^"\\]|\\.)*"|\[[^\]]*\])')
        if regex.search(text):
            text = regex.sub(lambda m: m.group(1) + value, text, count=1)
        else:
            missing.append(k)
    if missing:
        m = re.search(r'"settings"\s*:\s*\{', text)
        if m:
            lines = "".join(
                f"\n\t\t{json.dumps(k)}: {json.dumps(wanted[k], ensure_ascii=False)},"
                for k in missing
            )
            text = text[: m.end()] + lines + text[m.end() :]
        else:
            current["settings"] = {**settings, **wanted}
            text = json.dumps(current, indent="\t", ensure_ascii=False) + "\n"
    try:
        json.loads(strip_jsonc(text))
    except ValueError as e:
        raise ValueError(
            f"the edited file would not parse ({e}); left unchanged"
        ) from e
    ws.write_text(text, encoding="utf-8")
    return "Updated"


def install_workspaces(project_dir: Path, wanted: dict) -> list[str]:
    out = []
    for ws in find_workspace_files(project_dir):
        rel = os.path.relpath(ws) or str(ws)
        try:
            r = update_workspace_settings(ws, wanted)
            out.append(
                f"✓ {r} {rel} (multi-root workspace: tinymist.rootPath, "
                "tinymist.fontPaths, absolute)"
            )
        except (ValueError, OSError) as e:
            out.append(
                f"✗ Could not update {rel}: {e}\n"
                f'  Set in its "settings": {json.dumps(wanted)}'
            )
    return out


# --- the user keybinding (--keybinding) -----------------------------------------


def user_keybindings_path(editor: str) -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / editor
            / "User"
            / "keybindings.json"
        )
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(home / "AppData" / "Roaming")
        return Path(base) / editor / "User" / "keybindings.json"
    base = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    return Path(base) / editor / "User" / "keybindings.json"


def install_keybinding(editor: str, key: str) -> str:
    """Our shortcut in the user's keybindings.json, matched on command+args
    and updated in place; every other binding left alone."""
    kb_path = user_keybindings_path(editor)
    ours = {
        "key": key,
        "command": "workbench.action.tasks.runTask",
        "args": TASK_LABEL,
        "when": f"editorTextFocus && resourceExtname == {EXT}",
    }
    try:
        bindings = read_jsonc(kb_path, [])
    except ValueError as e:
        return f"✗ Could not parse {kb_path}: {e}\n  Add the binding by hand."
    if not isinstance(bindings, list):
        return f"✗ {kb_path} is not a list of bindings: add the binding by hand."

    def is_ours(b) -> bool:
        return (
            isinstance(b, dict)
            and b.get("command") == ours["command"]
            and (b.get("args") == TASK_LABEL)
        )

    prev = next((b for b in bindings if is_ours(b)), None)
    existed = kb_path.exists()
    bindings = [b for b in bindings if not is_ours(b)] + [ours]
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    kb_path.write_text(dump(bindings), encoding="utf-8")
    verb = (
        "Created"
        if not existed
        else "Updated"
        if prev != ours
        else "Already up to date —"
    )
    return (
        f"✓ {verb} {kb_path}\n"
        f'  Shortcut "{key}" → "{TASK_LABEL}" (active in {EXT} files).'
    )


# --- putting it together ------------------------------------------------------


def usage_lines(key: str | None) -> list[str]:
    lines = [
        "",
        "How to use:",
        "  1. Start the dev server:        make serve   (in the course directory)",
        f"  2. Put the cursor inside a slide in any {EXT} file.",
    ]
    if key:
        lines.append(
            f'  3. Press {key}  (or Cmd-Shift-P → "Run Task" → "{TASK_LABEL}").'
        )
    else:
        lines += [
            f'  3. Run the task:                Cmd-Shift-P → "Run Task" → "{TASK_LABEL}"',
            "",
            "  Want a shortcut? VS Code has no per-workspace keybindings, so either",
            "  re-run with  --keybinding  to add it to your user keybindings.json, or",
            "  paste this:",
            "    {",
            f'      "key": "{DEFAULT_KEY}",',
            '      "command": "workbench.action.tasks.runTask",',
            f'      "args": "{TASK_LABEL}",',
            f'      "when": "editorTextFocus && resourceExtname == {EXT}"',
            "    }",
        ]
    lines += [
        "",
        "  Reload the VS Code window (Developer: Reload Window) after the settings change.",
    ]
    return lines


def install(
    project_dir: Path,
    course_dir: Path | None = None,
    key: str | None = None,
    editor: str = "Code",
) -> list[str]:
    """Install everything; the report lines."""
    course_dir = course_dir or project_dir
    messages = [install_task(project_dir, our_task(project_dir, course_dir))]
    messages.append(
        install_settings(
            project_dir,
            {
                "tinymist.rootPath": in_workspace(project_dir, course_dir),
                "tinymist.fontPaths": [in_workspace(project_dir, FONTS)],
            },
        )
    )
    messages += install_workspaces(
        project_dir,
        {
            "tinymist.rootPath": str(course_dir),
            "tinymist.fontPaths": [str(FONTS)],
        },
    )
    if key:
        messages.append(install_keybinding(editor, key))
    return messages + usage_lines(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cathedra install-vscode",
        description="VS Code task (show the slide under the cursor) and Tinymist "
        "settings for a Typst course.",
    )
    parser.add_argument(
        "--project-dir", default=".", help="the VS Code project (workspace) directory"
    )
    parser.add_argument(
        "--course-dir", help="the course directory, if not the project dir"
    )
    parser.add_argument(
        "--keybinding",
        nargs="?",
        const=DEFAULT_KEY,
        metavar="KEYS",
        help="also add a shortcut to your USER keybindings.json "
        f"(default keys: {DEFAULT_KEY}; VS Code has no per-workspace keybindings)",
    )
    parser.add_argument(
        "--editor",
        default="Code",
        help='which editor profile: "Code" (default), "Code - Insiders", '
        '"Cursor", "VSCodium"',
    )
    parser.add_argument(
        "--typst", action="store_true", help="(accepted; always a Typst course)"
    )
    args = parser.parse_args(argv)
    project_dir = Path(args.project_dir).resolve()
    course_dir = Path(args.course_dir).resolve() if args.course_dir else None
    for line in install(project_dir, course_dir, args.keybinding, args.editor):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
