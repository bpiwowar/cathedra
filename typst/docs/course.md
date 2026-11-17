# Setting up a course

A course's Typst slides live in one directory next to the slide-app submodule
(e.g. `slides/typst/`, with `slides/slide-app/`), or in the directory that
holds the submodule, with the sources in `SRC` (e.g. `slides/src/`; see
[building](building.md)).

`slide-app init <dir>` writes all of what follows (and a first deck), with
the course in a directory of its own and the `slide-app` link; `slide-app new
<id>` adds `lectures/<id>.typ` and its schedule entry. Typst is the default;
`--mdx` selects the MDX engine. This page is what they write, by hand.

## Makefile

```make
# deck titles, order and target times (optional)
SLIDES_SCHEDULE := ../../course.yaml
# the Zotero / Better BibTeX bibliography
BIB             := ../src/main.bib

include ../slide-app/typst/makefile.mk
```

The options are listed in [building](building.md#options); `make
update-makefile` writes them into the Makefile as a generated comment block
(around the include line), `make check-makefile` tells whether it is stale.
Then:

```bash
make setup    # links slide-app, installs the engine, fonts, bibliography
```

## common/course.typ

What every deck and module imports (`#import "/common/course.typ": *`):

```typst
#import "/slide-app/lib/slides.typ": *
#import "/slide-app/templates/academic.typ": academic

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [Statistical Learning],
  background: read("/common/background.svg", encoding: none),
)

// the course notation, for maths: $tf(t, d)$
#let tf = math.upright("tf")
```

Everything `slides.typ` defines (and Touying's `#pause`, `#only`…) comes
along. See [templates](templates.md) for the options.

## The schedule

`SLIDES_SCHEDULE` is a YAML file:

```yaml
lectures:
  - id: lecture-1          # lectures/lecture-1.typ
    title: "Lecture 1: Foundations"
    target: 2h             # make outline compares the deck's time with it
```

Without it, `make outline` takes every `lectures/*.typ`, and the browser tab
shows the file name.

## Widgets

`widgets/index.ts` exports the course's React widgets; see
[widgets](widgets.md).

## Web styling

The browser deck shows the slide on black. A `web.css` at the course's root,
if any, is loaded after the engine's styles; e.g. another colour around the
slide:

```css
:root { --backdrop: #1e1e2e; }
```

## VS Code

`make install-vscode` (or `slide-app install-vscode`) writes what follows:
the task and the two settings. Decks use root-absolute paths (`/common/…`, `/modules/…`, `/lib/refs.bib`):
they start from the course's slide directory (the build's `--root`). The
Typst extension, Tinymist, must be told that directory and the fonts; set it
in the workspace's settings (a `.code-workspace` file, or `.vscode/settings.json`
of the folder opened):

```json
"tinymist.rootPath": "/absolute/path/to/course",
"tinymist.fontPaths": ["/absolute/path/to/course/slide-app/typst/fonts"]
```

- `make install-vscode` also adds the task *Show slide in Typst deck*
  (`.vscode/tasks.json`): it runs `slide-app/tools/open-slide.mjs` on the file
  and line under the cursor, which sends `GET /goto?file=&line=` to the
  running deck (`make serve`, or the sockets of slide-app's dev server) and
  moves the open browser tabs to that slide. Bind it to a key with
  `--keybinding` (a user keybinding, active in `.typ` files); from a shell,
  `make open-slide FILE=lectures/lecture-1.typ LINE=42`. The folder's
  settings use `${workspaceFolder}`, so they hold wherever the folder is.
- In a multi-root workspace (a `.code-workspace` file listing the course
  among its folders) the folder's `tinymist.*` settings are ignored, and
  Tinymist expands `${workspaceFolder}` to the *first* folder of the
  workspace: `make install-vscode` therefore also writes absolute paths into
  the `settings` of every `.code-workspace` file, in the course directory or
  an ancestor, that lists it (comments kept). Re-run it after moving the
  course or the engine.
- Without a root, Tinymist takes the open file's own folder:
  `#import "/common/course.typ"` then fails with
  `file not found (searched at …/modules/<topic>/common/course.typ)`.
- The settings apply only to windows of that workspace. A `.typ` file opened
  outside it (from a link, another tool, a window with no folder) gets none
  of them: check the window's title (`… (WORKSPACE)`), or Tinymist's log
  (Output › Tinymist), whose configuration line shows `rootPath`.
- In user settings, the root would hold for every Typst file of every window:
  only if this course is your only Typst project.
- Reload the window (*Developer: Reload Window*) after a change, and run
  `make` once: `lib/refs.bib` and `lib/refs.csl` are generated.

## Housekeeping

```bash
make unused-media          # media files no .typ names (CLEAN=1 deletes them)
make optimize-images       # PNG/JPEG/GIF -> WebP, capped; DRY=1, PRUNE=1
make compute-svg-bb SVG="modules/ir"   # trim SVG canvases (APPLY=1 writes)
```

`unused-media` counts every `"…"` string of a `.typ` that resolves to a file
(relative to it, or `/`-rooted); a name built at run time is not seen, so read
the list before deleting. `optimize-images` rewrites the references to the
`.webp` it writes. Both skip `out/`, `.cache/`, `lib/`, `slide-app`.

## Git

The course versions its directory and the `slide-app` link; the bibliography
files in `lib/` and `out/` are generated:

```
out/
lib/refs.bib
lib/refs.csl
lib/refs-links.json
```

## The course site

`make site` / `deploy` publish the decks with an index page (deck list,
synopsis, outline, PDF and practical links): see [building](building.md#the-course-site).
The schedule's entries take, besides `id`, `title` and `target`:

```yaml
lang: en                   # the index page's wording (en, fr)
timePerSlide: 2            # minutes per slide, for the outline's times
lectures:
  - id: lecture-1
    title: "Lecture 1: Foundations"
    pdf: true              # make site-pdf compiles it, the index links it
    dev: true              # only in the dev site (site-dev, deploy-dev)
    summary: "…"           # the deck's synopsis, if it has no #synopsis
    practicals: [intro, {id: extra, optional: true}]
  - title: "Lecture 2: Guest talk"
    externalPdf: pdf/lecture-2.pdf   # a file of the site (STATIC): a link only
```

The site needs no webpack: this replaces slide-app's MDX build (below) for a
course without MDX decks.

## Next to MDX decks

In a slide-app course, a deck of the schedule can be written in Typst while
the others stay in MDX: mark it in the deck list (`webpack.config.js`
`sources`, or the file it reads):

```yaml
  - id: lecture-1
    title: "Lecture 1: Foundations"
    format: typst          # typst/lectures/lecture-1.typ
```

slide-app then:

- leaves it out of the webpack build (with no MDX deck left, webpack only
  writes the index page: no deck runtime, no MathJax);
- `make html` / `html-dev` (and the `-force` variants): builds it into
  `<output>/<id>/` (after webpack), with `make -C typst html`; `html-dev`
  adds the `dev: true` decks, but is built for readers (no source paths,
  no E / shift-E, DOI links rather than Zotero): it is published by
  `deploy-dev`. The author build is the dev server's;
- `make pdf` / `pdf-dev`: when it has `pdf: true`, compiles it with `make -C
  typst pdf` straight to `<output>/pdf/<id>.pdf`, where the index page's PDF
  link and `make deploy` expect it — no HTML build, no browser, `PDF_FLAGS`
  ignored. A `dev: true` deck is not in the production build, so only
  `pdf-dev` prints it (`make pdf` says so when that leaves nothing to print);
- the index page links `<id>/`, with its outline and synopsis;
- `make outline` lists it with the others, in order, in the totals.

The Typst directory is `typst/` by default. Elsewhere, say so in three
places: `TYPST_DIR` in the course Makefile (build), the `typst: { dir }` slide
option (index page), `webpackConfig.typst = { dir }` (`make outline`).
In slide-app's dev server (`make serve-dev`), the first request under
`/<id>/` starts that deck's Typst dev server (live reload, H, E…) on a Unix
socket, `typst/out/<id>.sock`, and forwards `/<id>/` to it: the index page's
link works as in the built site. These servers stop with the dev server.
`make -C typst serve DECK=<id>` serves one deck alone, on port 8000.
