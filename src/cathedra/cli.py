# ruff: noqa: T201
"""The `cathedra` command (run from the course directory: Typst's root).

The course's makefile.mk calls it; `cathedra --help` lists the commands.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Optional

import typer

from . import __version__
from .paths import TYPST, Course, engine_dir

app = typer.Typer(
    help="Lecture slides in Typst: web decks (live reload), PDFs, course sites.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="markdown",
    context_settings={"help_option_names": ["-h", "--help"]},
)
site_app = typer.Typer(
    help="The course site: decks of the schedule, index page, PDFs.",
    no_args_is_help=True,
)

# the panels of `cathedra --help`
SETUP, BUILD, AUTHOR, MEDIA, MIGRATE = (
    "Set up",
    "Build & publish",
    "Authoring",
    "Media",
    "Migration",
)
app.add_typer(site_app, name="site", rich_help_panel=BUILD)

PASS = {"allow_extra_args": True, "ignore_unknown_options": True}
Decks = Annotated[
    Optional[list[str]],
    typer.Argument(help="deck ids or .typ files (default: every deck)"),
]
Out = Annotated[Path, typer.Option("--out", help="output directory")]


def course() -> Course:
    return Course()


def decks_of(c: Course, decks: list[str] | None) -> list[Path]:
    if not decks:
        return [c.deck_file(i) for i in c.deck_ids()]
    return [c.resolve_deck(d) for d in decks]


def link_engine(c: Course) -> None:
    """The engine as the decks import it: /cathedra/lib/slides.typ. A course
    with the engine as a submodule (a directory) imports
    /cathedra/typst/lib/slides.typ: nothing to do; otherwise `cathedra` (or
    the former `slide-app`) is a link to the package's Typst files, kept
    pointing at the installed version (uvx moves it when the version
    changes)."""
    link = engine_dir(c.root)
    if link.is_symlink():
        if link.resolve() != TYPST.resolve():
            link.unlink()
            link.symlink_to(TYPST)
    elif not link.exists():
        link.symlink_to(TYPST)


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool, typer.Option("--version", help="print the version")
    ] = False,
) -> None:
    if version:
        from .engine import TYPST_VERSION

        print(f"cathedra {__version__} (Typst {TYPST_VERSION})")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        print(ctx.get_help())
        raise typer.Exit()
    c = course()
    if engine_dir(c.root).is_symlink():
        link_engine(c)


# ------------------------------------------------------------------ set up
@app.command(rich_help_panel=SETUP)
def setup(
    bib: Annotated[
        Optional[Path], typer.Argument(help="the course's bibliography")
    ] = None,
) -> None:
    """The `cathedra` link to the engine (unless a submodule), the bibliography."""
    c = course()
    link_engine(c)
    if bib:
        sync(bib)


@app.command(rich_help_panel=SETUP)
def sync(
    bib: Annotated[
        Path, typer.Argument(help="the Zotero / Better BibTeX bibliography")
    ],
) -> None:
    """lib/refs-links.json (the links of #reference); fails on a duplicate key."""
    from .sync import main

    if main(str(bib)):
        raise typer.Exit(1)


@app.command(rich_help_panel=SETUP)
def fonts() -> None:
    """Where the engine's fonts are (passed to every compilation)."""
    from .paths import FONTS

    print(FONTS)


# -------------------------------------------------------------- the decks
@app.command(rich_help_panel=BUILD)
def build(
    decks: Decks = None,  # type: ignore[assignment]
    out: Out = Path("out"),
    dev: Annotated[
        bool,
        typer.Option(
            "--dev",
            help="for the author: E opens the sources, references link to Zotero, help",
        ),
    ] = False,
    jobs: Annotated[
        int, typer.Option("--jobs", "-j", help="decks built in parallel (0: CPUs)")
    ] = 0,
) -> None:
    """The web decks, `OUT/<deck>/`."""
    from .build import DeckBuild

    c = course()
    files = decks_of(c, decks)

    def one(f: Path) -> bool:
        return DeckBuild(c, f, out, dev=dev).build_all()

    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        ok = all(list(ex.map(one, files)))
    raise typer.Exit(0 if ok else 1)


@app.command(rich_help_panel=BUILD)
def serve(
    deck: Annotated[
        Optional[str], typer.Argument(help="deck id or .typ file (default: the first)")
    ] = None,
    out: Out = Path("out"),
    port: Annotated[int, typer.Option(help="port")] = 8000,
    socket: Annotated[
        Optional[str], typer.Option(help="serve on this Unix socket instead")
    ] = None,
) -> None:
    """Dev server of a deck: live reload, H help, E edit…"""
    from .serve import serve as run

    c = course()
    f = c.resolve_deck(deck) if deck else decks_of(c, None)[0]
    run(c, f, out, port=port, socket=socket)


@app.command(rich_help_panel=BUILD)
def pdf(
    decks: Decks = None,  # type: ignore[assignment]
    out: Out = Path("out"),
    handout: Annotated[
        bool,
        typer.Option(
            "--handout",
            help="the last step of each slide only: `OUT/<deck>-handout.pdf`",
        ),
    ] = False,
    jobs: Annotated[int, typer.Option("--jobs", "-j")] = 0,
) -> None:
    """Printable PDFs, `OUT/<deck>.pdf` (with the widgets' snapshots)."""
    from .engine import DeckCompiler

    c = course()
    out.mkdir(parents=True, exist_ok=True)

    def one(f: Path) -> bool:
        inputs: dict[str, str] = {}
        if handout:
            inputs["handout"] = "1"
        target = out / f"{f.stem}{'-handout' if handout else ''}.pdf"
        comp = DeckCompiler(c, f, inputs).compile()
        for d in comp.diagnostics:
            print(d.text, file=sys.stderr)
        if comp.ok:
            target.write_bytes(comp.pdf())
            print(target)
        return comp.ok

    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        ok = all(list(ex.map(one, decks_of(c, decks))))
    raise typer.Exit(0 if ok else 1)


@app.command(rich_help_panel=BUILD)
def check(
    decks: Decks = None,  # type: ignore[assignment]
    out: Out = Path("out"),
    jobs: Annotated[int, typer.Option("--jobs", "-j")] = 0,
) -> None:
    """Compile every deck (`OUT/<deck>.pdf`); fail on errors or overflowing slides
    (Touying reports a slide past the canvas as a warning), and when plain
    `typst compile` could not compile it from a clone (docs/building.md)."""
    from .engine import DeckCompiler
    from .standalone import plain_problems

    c = course()
    out.mkdir(parents=True, exist_ok=True)
    files = decks_of(c, decks)

    def one(f: Path):
        comp = DeckCompiler(c, f).compile()
        if comp.ok:
            (out / f"{f.stem}.pdf").write_bytes(comp.pdf())
        return comp, plain_problems(c, f)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(jobs or min(8, os.cpu_count() or 4)) as ex:
        pairs = list(ex.map(one, files))
    results = [comp for comp, _ in pairs]
    status = 0
    for _, problems in pairs:
        for problem in problems:
            print(f"error: {problem}")
            status = 1
    from .compat import api_problems

    deps = sorted({p for comp in results for p in comp.dependencies})
    for problem in api_problems(deps):
        print(f"error: {problem}")
        status = 1
    for comp in results:
        if not comp.ok:
            status = 1
        for d in comp.diagnostics:
            if "ligature component" in d.text:
                continue
            # the message and the location, as the make target printed them
            print("\n".join(d.text.split("\n")[:5]))
            if d.severity == "warning" and "overflow" in d.message.lower():
                status = 1
    took = time.perf_counter() - t0
    if status == 0:
        print(
            f"check: all decks compile (also as plain typst), no overflow ({took:.1f} s)"
        )
    else:
        print(f"check: FAILED ({took:.1f} s)")
    raise typer.Exit(status)


@app.command(rich_help_panel=BUILD)
def snapshots(decks: Decks = None) -> None:  # type: ignore[assignment]
    """Pictures of the React widgets for the PDFs (headless Chromium)."""
    from .snapshots import snapshots as run

    c = course()
    run(c, decks_of(c, decks))


@app.command(rich_help_panel=AUTHOR)
def outline(
    decks: Decks = None,  # type: ignore[assignment]
    slides: Annotated[
        bool, typer.Option("--slides", help="every slide, with its file:line")
    ] = False,
    json_: Annotated[bool, typer.Option("--json", help="the outlines as JSON")] = False,
    duplicates: Annotated[
        bool, typer.Option("--duplicates", help="the files included more than once")
    ] = False,
    time_per_slide: Annotated[float, typer.Option("--time-per-slide")] = 2,
) -> None:
    """Deck structure, slide counts and time vs the schedule's target."""
    import json

    from .outline import (
        compile_outlines,
        print_duplicates,
        print_outlines,
        schedule_decks,
    )

    c = course()
    selected = schedule_decks(c, decks or [])
    if duplicates:
        print_duplicates(c, selected)
        return
    results = compile_outlines(c, selected)
    if json_:
        data = [{"id": d["id"], "target": d.get("target"), **o} for d, o in results]
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    print_outlines(results, time_per_slide, slides)
    if len(results) < len(selected):
        raise typer.Exit(1)


@app.command("open-slide", context_settings=PASS, rich_help_panel=AUTHOR)
def open_slide(ctx: typer.Context) -> None:
    """FILE LINE: move the running deck(s) to the slide of that line."""
    from .open_slide import main

    raise typer.Exit(main(ctx.args))


@app.command(rich_help_panel=AUTHOR)
def contact(
    deck: Annotated[str, typer.Argument()],
    outdir: Annotated[Path, typer.Argument()],
    per: Annotated[int, typer.Argument()] = 20,
) -> None:
    """Contact sheets of a deck's pages (PNG), for reviewing."""
    from .contact import contact_sheets

    c = course()
    n = contact_sheets(c, c.resolve_deck(deck), outdir, per)
    print(f"{n} pages", file=sys.stderr)


@app.command("api-doc", rich_help_panel=AUTHOR)
def api_doc(
    src: Annotated[
        Optional[Path], typer.Argument(help="the course's sources (its common/)")
    ] = None,
) -> None:
    """The API index (docs/api.md of the help) on stdout."""
    from .apidoc import api_markdown

    c = course()
    sys.stdout.write(api_markdown(course=src.resolve() if src else c.src, root=c.root))


# --------------------------------------------------------------- sources
@app.command(rich_help_panel=MIGRATE)
def migrate(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="print a diff, write nothing")
    ] = False,
    check_only: Annotated[
        bool, typer.Option("--check", help="only say whether the course is behind")
    ] = False,
) -> None:
    """Migrate the sources to the engine's API version (docs/upgrading.md)."""
    from .migrate import main

    raise typer.Exit(
        main(
            [*(["--dry-run"] if dry_run else []), *(["--check"] if check_only else [])]
        )
    )


@app.command(rich_help_panel=AUTHOR)
def space(files: Annotated[list[Path], typer.Argument()]) -> None:
    """Blank lines between slides (idempotent)."""
    from .spacing import main

    main([str(f) for f in files])


@app.command(context_settings=PASS, rich_help_panel=MIGRATE)
def convert(ctx: typer.Context) -> None:
    """MDX -> Typst (pandoc; `cathedra[convert]`): see docs/conversion.md."""
    from .convert.mdx2typ import main

    raise typer.Exit(main(ctx.args))


# ------------------------------------------------------- media, makefile
def _passthrough(name: str, module: str, doc: str, panel: str) -> None:
    def command(ctx: typer.Context) -> None:
        import importlib

        raise typer.Exit(
            importlib.import_module(f"cathedra.{module}").main(ctx.args) or 0
        )

    command.__doc__ = doc
    app.command(
        name, context_settings=PASS, add_help_option=False, rich_help_panel=panel
    )(command)


_passthrough(
    "images",
    "images",
    "Fetch the missing images given by an origin, to their path (--check: heavy images).",
    MEDIA,
)
_passthrough(
    "unused-media",
    "unused_media",
    "Media files no .typ references (--clean removes them).",
    MEDIA,
)
_passthrough(
    "optimize-images",
    "optimize_images",
    "PNG/JPEG/GIF -> WebP, references rewritten (--dry, --prune).",
    MEDIA,
)
_passthrough(
    "compute-svg-bb", "svg_bbox", "Trim SVGs to their content (--apply writes).", MEDIA
)
_passthrough(
    "install-vscode",
    "vscode",
    "VS Code task (show the slide under the cursor) and Tinymist settings.",
    SETUP,
)
_passthrough(
    "sync-makefile",
    "makefile_sync",
    "Refresh (or --check) the generated option list of the course Makefile.",
    SETUP,
)


# ------------------------------------------------------------------- site
SiteOut = Annotated[Optional[Path], typer.Option("--out", help="the site's directory")]
Dev = Annotated[
    bool, typer.Option("--dev", help="the dev site (with the dev: true decks)")
]
Practicals = Annotated[
    Optional[Path], typer.Option("--practicals", help="the practicals' JSON manifest")
]
Static = Annotated[
    Optional[list[Path]], typer.Option("--static", help="directories copied as is")
]


def _need(out: Path | None) -> Path:
    if not out:
        print("--out=DIR is required", file=sys.stderr)
        raise typer.Exit(2)
    return out.resolve()


@site_app.command("decks")
def site_decks(
    dev: Dev = False, pdf_: Annotated[bool, typer.Option("--pdf")] = False
) -> None:
    """Ids of the decks to build."""
    from .site import deck_ids, schedule

    c = course()
    print(" ".join(deck_ids(c, schedule(c), dev, pdf_)))


@site_app.command("build")
def site_build(
    out: SiteOut = None,
    dev: Dev = False,
    static: Static = None,
    practicals: Practicals = None,
) -> None:
    """The decks (`DIR/<id>/`), the static files, `DIR/index.html`."""
    from .site import build_site, schedule

    c = course()
    ok = build_site(
        c,
        schedule(c),
        _need(out),
        dev,
        [s.resolve() for s in static or []],
        practicals and practicals.resolve(),
    )
    raise typer.Exit(0 if ok else 1)


@site_app.command("index")
def site_index(
    out: SiteOut = None, dev: Dev = False, practicals: Practicals = None
) -> None:
    """DIR/index.html alone."""
    from .site import schedule, write_index

    c = course()
    write_index(c, schedule(c), _need(out), dev, practicals and practicals.resolve())


@site_app.command("pdf")
def site_pdf(
    out: SiteOut = None,
    dev: Dev = False,
    force: Annotated[bool, typer.Option("--force")] = False,
) -> None:
    """`DIR/<id>.pdf` of the `pdf: true` decks (MD5-cached)."""
    from .site import build_pdfs, deck_ids, schedule

    c = course()
    ids = deck_ids(c, schedule(c), dev, pdf=True)
    if not ids:
        extra = (
            "" if dev else " (dev: true decks are only in the dev site: site-pdf-dev)"
        )
        print(f"no deck with pdf: true in the {'dev ' if dev else ''}site{extra}")
    raise typer.Exit(0 if build_pdfs(c, ids, _need(out), force) else 1)


@site_app.command("check")
def site_check(out: SiteOut = None) -> None:
    """No local absolute path in the site."""
    from .site import check_paths

    c = course()
    o = _need(out)
    if not check_paths(c, o):
        raise typer.Exit(1)
    print(f"{c.rel(o) or '.'}: no local absolute path")


@site_app.command("serve")
def site_serve(
    port: Annotated[int, typer.Option()] = 9010,
    static: Static = None,
    practicals: Practicals = None,
    sockets: Annotated[
        Path, typer.Option(help="where the decks' dev servers listen")
    ] = Path("out"),
    dev: Annotated[
        bool, typer.Option(help="the dev site (with the `dev: true` decks)")
    ] = False,
) -> None:
    """Dev server of the whole course: index + its decks (production or dev)."""
    from .course_server import serve_course

    serve_course(
        course(),
        port,
        [s.resolve() for s in static or []],
        practicals and practicals.resolve(),
        sockets,
        dev,
    )


def main() -> None:
    app()


if __name__ == "__main__":
    main()
