# cathedra

Lecture slides written in [Typst](https://typst.app/docs/) with the
[Touying](https://touying-typ.github.io/) package, shown in the browser by a
Reveal.js viewer. One source gives two outputs: the web deck (the pages as
inline SVG, live React widgets on top) and a printable PDF; a course gets an
index page, its PDFs and a deployment.

This help opens with **H** in the dev server (`make serve`).

## Install

A Python package (Python 3.11 or later) with Typst built in: nothing else to
install (no Node, no typst CLI). The `cathedra` command runs from a
course's directory:

```bash
uvx cathedra --help                  # or: pip install cathedra
uvx --from 'cathedra[browser]' cathedra snapshots   # widget pictures
```

Extras: `browser` (Playwright: widget pictures for the PDFs, viewer tests;
then `playwright install chromium`), `convert` (MDX to Typst, with pandoc).
A course drives it through make (`makefile.mk`, see [setting up a
course](docs/course.md)), which calls `uvx cathedra …`, or the version of
a cathedra checkout (e.g. a git submodule) with `uv run --project`.

## Quick start (in a course)

```bash
make setup                  # engine dependencies, fonts, bibliography
make serve DECK=lecture-1   # http://localhost:8000, live reload
make check                  # every deck compiles, no slide overflows
make pdf                    # out/<deck>.pdf
```

## Editing slides

The dev server (`make serve`) is made for writing:

- **Live reload.** It keeps the compiler warm, so saving a `.typ` file shows
  the change in about 100 ms. Only the changed pages are re-rendered, and the
  position in the deck, widget states and drawings are kept. Errors show in
  the browser.
- **From the slide to its source and back.** **E** opens the slide's source
  in VS Code, and **shift-E** shows the chain of `#include`s down to it. The
  other way, a VS Code task (*Show slide in Typst deck*, set up by
  `make install-vscode` with the Tinymist settings) moves the open decks to
  the slide under the cursor.
- **Overflow.** **O** lists the slides whose content overflows; from there you
  can go to a slide or edit its source. An overflowing step has a red bar
  with the excess height, and `make check` fails on any overflow.
- **Placing labels with the mouse.** **shift-O** lets you drag an
  annotation's label (`#annot`) into place and resize it. The position is
  written back into the source (`dx:`, `dy:`, `width:`).
- **Finding a slide.** **T** opens the structure browser: sections, slides,
  times against the target, slide types and work-in-progress markers.
  `make outline` prints the same in the terminal. Slide addresses use the
  title, so they stay the same when slides are added above.
- **Images.** `#img(path(…), origin: …)` fetches a missing image once from
  its origin (a URL or a Zotero annotation) and resizes it (`make images`).
  `optimize-images`, `unused-media` and `compute-svg-bb` keep the media folder
  lean.

## Zotero

The bibliography is the course's Better BibTeX export from Zotero: entries
are never typed by hand.

- **Citing.** `#reference(<key>)` puts the full reference at the bottom of the
  slide, and `#cite(<key>)` cites inline. `cathedra sync` (run by
  `make setup`) reports duplicate keys with their lines, so you can merge the
  items in Zotero.
- **Links.** In the dev server, the icon in front of a reference opens the
  item in the Zotero app; in a built deck or PDF it links to the DOI or URL.
  `cathedra sync` asks the running Zotero for these links, and handles group
  libraries and items from other users' libraries.
- **Figures from papers.** A Zotero image annotation, i.e. a region selected
  in a PDF, can be the `origin:` of an `#img`. The picture Zotero rendered is
  copied into the course, and the image keeps a link back to the annotation.
- **Z** in the dev server opens the Zotero item of the slide's references
  and figures, with a picker when there are several.

## Without cathedra

A course never depends on this package being maintained: a clone compiles
to PDF with plain `typst compile`, so its authors can stop using the tool at
any time. Typst does all of the typesetting, with the same packages and fonts
as the typst CLI. The tool adds the web version (viewer, live widgets), the
site, and generated files that only improve the PDFs (reference links,
pictures of the widgets): the course reads them only when cathedra
compiles. The rest is in git: the decks cite the course's `.bib` itself,
fetched images are committed. `make check` enforces it: it also compiles
every deck as plain typst does, and fails if that needs a file git ignores.
See [building](docs/building.md#without-cathedra).

## Engine and course

The engine is the `cathedra` package (its Typst files: `cathedra/` in
the course, a link `cathedra setup` makes, or the `typst/` directory of a
cathedra submodule); a course only holds its content and its configuration:

| Course path | What |
|---|---|
| `Makefile` | the options, then `include cathedra/makefile.mk` |
| `cathedra` | a link to the engine's Typst files (`make setup` creates it): decks import `/cathedra/…` |
| `common/course.typ` | what every deck imports: the engine, the template configured for the course, the course notation |
| `lectures/<id>.typ` or `lectures/<id>/<id>.typ` | a deck: title slide, sections, `#include` of modules, wrap-up (in a folder, with the files only it uses) |
| `modules/<topic>/<topic>.typ` | the content, one topic per module, with its `figures/` |
| `widgets/index.ts` | the course's React widgets (optional) |
| `lib/` | generated: the bibliography and its links (`cathedra sync`) |
| `out/` | generated: the web decks and PDFs |

`common/`, `lectures/`, `modules/` and `widgets/` can instead live in a
sub-directory, `SRC` (e.g. `src/`, the decks then importing
`/src/common/course.typ`): the course directory stays Typst's root, with the
`Makefile`, `lib/`, `.cache/` and `out/`. A course whose `cathedra` submodule
is in its directory imports `/cathedra/typst/lib/slides.typ` and includes
`cathedra/typst/makefile.mk` (no link).

| Engine path (repository) | What |
|---|---|
| `src/cathedra/typst/lib/slides.typ` | the components and page markers (`typst/` is a link to `src/cathedra/typst/`) |
| `src/cathedra/typst/templates/*.typ` | what a course looks like (`academic`) |
| `src/cathedra/typst/makefile.mk` | the make targets |
| `src/cathedra/typst/fonts/` | Font Awesome (TTF), given to every compilation |
| `src/cathedra/*.py` | the `cathedra` command: build, dev server, site, PDFs, outline, tools |
| `rust/` | the native module (`cathedra._native`): Typst (compile, SVG pages, PDF, queries) |
| `viewer/` | the browser viewer's sources (Reveal.js, SVG pages, widgets, structure browser, this help); built into `src/cathedra/data/` |
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

The built viewer (`src/cathedra/data/`) is committed, so that the package
builds without Node; the pre-commit hook refuses a change of `viewer/`
without the rebuilt bundle. Releases: a GitHub release publishes the wheels
(Linux, macOS, Windows; abi3) and the sdist on PyPI
(`.github/workflows/publish.yml`, trusted publishing).

## Pages

- [Quick reference](docs/quick.md): the syntax at a glance (the help opens on it)
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
- [Building and checking](docs/building.md): make targets and options, PDFs, outline,
  compiling without cathedra
- [Upgrading a course](docs/upgrading.md): API versions, `make migrate`;
  [CHANGELOG](CHANGELOG.md)
- [Converting from MDX](docs/conversion.md): porting a slide-app MDX module
- [API index](docs/api.md): every function and value, with its signature
  (generated from the sources; in the help only)
