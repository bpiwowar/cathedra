# typst-slides

Lecture slides written in [Typst](https://typst.app/docs/) with the
[Touying](https://touying-typ.github.io/) package, shown in the browser by a
Reveal.js viewer. One source gives two outputs: the web deck (the pages as
inline SVG, live React widgets on top) and a printable PDF; a course gets an
index page, its PDFs and a deployment.

This help opens with **H** in the dev server (`make serve`).

## Install

A Python package (Python 3.11 or later) with Typst built in: nothing else to
install (no Node, no typst CLI). The `typst-slides` command runs from a
course's directory:

```bash
uvx typst-slides --help                  # or: pip install typst-slides
uvx --from 'typst-slides[browser]' typst-slides snapshots   # widget pictures
```

Extras: `browser` (Playwright: widget pictures for the PDFs, viewer tests;
then `playwright install chromium`), `convert` (MDX to Typst, with pandoc).
A course drives it through make (`makefile.mk`, see [setting up a
course](docs/course.md)), which calls `uvx typst-slides …`, or the version of
a slide-app checkout (e.g. a git submodule) with `uv run --project`.

## Quick start (in a course)

```bash
make setup                  # engine dependencies, fonts, bibliography
make serve DECK=lecture-1   # http://localhost:8000, live reload
make check                  # every deck compiles, no slide overflows
make pdf                    # out/<deck>.pdf
```

## Engine and course

The engine is the `typst-slides` package (its Typst files: `slide-app/` in
the course, a link `typst-slides setup` makes, or the `typst/` directory of a
slide-app submodule); a course only holds its content and its configuration:

| Course path | What |
|---|---|
| `Makefile` | the options, then `include slide-app/makefile.mk` |
| `slide-app` | a link to the engine's Typst files (`make setup` creates it): decks import `/slide-app/…` |
| `common/course.typ` | what every deck imports: the engine, the template configured for the course, the course notation |
| `lectures/<id>.typ` or `lectures/<id>/<id>.typ` | a deck: title slide, sections, `#include` of modules, wrap-up (in a folder, with the files only it uses) |
| `modules/<topic>/<topic>.typ` | the content, one topic per module, with its `figures/` |
| `widgets/index.ts` | the course's React widgets (optional) |
| `lib/` | generated: the bibliography and its links (`typst-slides sync`) |
| `out/` | generated: the web decks and PDFs |

`common/`, `lectures/`, `modules/` and `widgets/` can instead live in a
sub-directory, `SRC` (e.g. `src/`, the decks then importing
`/src/common/course.typ`): the course directory stays Typst's root, with the
`Makefile`, `lib/`, `.cache/` and `out/`. A course whose `slide-app` submodule
is in its directory imports `/slide-app/typst/lib/slides.typ` and includes
`slide-app/typst/makefile.mk` (no link).

| Engine path (repository) | What |
|---|---|
| `src/typst_slides/typst/lib/slides.typ` | the components and page markers (`typst/` is a link to `src/typst_slides/typst/`) |
| `src/typst_slides/typst/templates/*.typ` | what a course looks like (`academic`) |
| `src/typst_slides/typst/makefile.mk` | the make targets |
| `src/typst_slides/typst/fonts/` | Font Awesome (TTF), given to every compilation |
| `src/typst_slides/*.py` | the `typst-slides` command: build, dev server, site, PDFs, outline, tools |
| `rust/` | the native module (`typst_slides._native`): Typst (compile, SVG pages, PDF, queries) |
| `viewer/` | the browser viewer's sources (Reveal.js, SVG pages, widgets, structure browser, this help); built into `src/typst_slides/data/` |
| `tests/` | pytest: the engine, a made-up course; `tests/browser/`: the viewer, against a running `make serve` |
| `docs/` | these pages |

### Developing the engine

```bash
uv sync --all-extras             # builds the native module (Rust, maturin)
uv run pytest                    # tests (the browser ones need SLIDES_URL)
(cd viewer && pnpm install && pnpm run build)   # after editing viewer/
pre-commit install               # ruff, cargo fmt/clippy, conventional commits,
                                 # the viewer bundle in step with viewer/
```

The built viewer (`src/typst_slides/data/`) is committed, so that the package
builds without Node; the pre-commit hook refuses a change of `viewer/`
without the rebuilt bundle. Releases: a GitHub release publishes the wheels
(Linux, macOS, Windows; abi3) and the sdist on PyPI
(`.github/workflows/publish.yml`, trusted publishing).

## Pages

- [Setting up a course](docs/course.md): the Makefile, `common/course.typ`, VS Code
- [Templates](docs/templates.md): `academic` and its options
- [Writing slides](docs/authoring.md): decks, modules, headings, steps, metadata
- [Components](docs/components.md): blocks, columns, icons
- [Images](docs/images.md): `#img`, paths, sizes, formats, shapes over an image, interactive SVG
- ["In detail" slides](docs/details.md): `#details`, `#details-link`, an appendix with a way back
- [Citations](docs/citations.md): `#reference`, Zotero and DOI links
- [Slide types and todo markers](docs/slide-types.md)
- [Figures](docs/figures.md): figures in steps, coloured vectors, handouts
- [Element annotations](docs/annotations.md): `#mark` / `#annot`, labels on
  part of a formula or text, moved with shift-O
- [Interactive widgets](docs/widgets.md): React components in a slide
- [The viewer](docs/viewer.md): keys, structure browser, live reload, editing
- [Building and checking](docs/building.md): make targets and options, PDFs, outline
- [Upgrading a course](docs/upgrading.md): API versions, `make migrate`;
  [CHANGELOG](CHANGELOG.md)
- [Converting from MDX](docs/conversion.md): porting a slide-app module
- [API index](docs/api.md): every function and value, with its signature
  (generated from the sources; in the help only)
