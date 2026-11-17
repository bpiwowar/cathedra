# slide-app for Typst

Slides written in [Typst](https://typst.app/docs/) with the
[Touying](https://touying-typ.github.io/) package, shown in the browser by a
Reveal.js viewer. One source gives two outputs: the web deck (the pages as
inline SVG, live React widgets on top) and a printable PDF.

This help opens with **H** in the dev server (`make serve`).

## Quick start (in a course)

```bash
make setup                  # engine dependencies, fonts, bibliography
make serve DECK=lecture-1   # http://localhost:8000, live reload
make check                  # every deck compiles, no slide overflows
make pdf                    # out/<deck>.pdf
```

## Engine and course

The engine is `slide-app/typst/` (this directory); a course only holds its
content and its configuration:

| Course path | What |
|---|---|
| `Makefile` | the options, then `include ../slide-app/typst/makefile.mk` |
| `slide-app` | a link to the engine (`make setup` creates it): decks import `/slide-app/…` |
| `common/course.typ` | what every deck imports: the engine, the template configured for the course, the course notation |
| `lectures/<id>.typ` or `lectures/<id>/<id>.typ` | a deck: title slide, sections, `#include` of modules, wrap-up (in a folder, with the files only it uses) |
| `modules/<topic>/<topic>.typ` | the content, one topic per module, with its `figures/` |
| `widgets/index.ts` | the course's React widgets (optional) |
| `lib/` | generated: the bibliography and its links (`tools/sync.py`) |
| `out/` | generated: the web decks and PDFs |

`common/`, `lectures/`, `modules/` and `widgets/` can instead live in a
sub-directory, `SRC` (e.g. `src/`, the decks then importing
`/src/common/course.typ`): the course directory stays Typst's root, with the
`Makefile`, `lib/`, `.cache/` and `out/`. A course whose `slide-app` submodule
is in its directory imports `/slide-app/typst/lib/slides.typ` (no link).

| Engine path | What |
|---|---|
| `lib/slides.typ` | the components and page markers |
| `templates/*.typ` | what a course looks like (`academic`) |
| `src/` | the browser viewer (Reveal.js, SVG pages, widgets, structure browser, this help) |
| `build.mjs` | compile, build `out/<deck>/`, serve with live updates |
| `makefile.mk` | the make targets |
| `tools/` | bibliography, outline, MDX conversion, fonts, spacing |
| `tests/` | browser tests of the viewer (against a running `make serve`) |
| `docs/` | these pages |

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
