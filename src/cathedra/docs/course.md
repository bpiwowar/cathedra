# Setting up a course

A course's Typst slides live in one directory (Typst's root: `lib/`,
`.cache/`, `out/`), with the sources there or in `SRC` (e.g. `slides/src/`;
see [building](building.md)).

## The engine: package or submodule

The engine is the `cathedra` Python package. A course uses it in one of
two ways:

- **The released package** (`uvx cathedra`, nothing installed by hand):
  `uvx cathedra setup` makes the `cathedra` link to the package's Typst
  files (`lib/`, `templates/`, `fonts/`, `makefile.mk`); the decks import
  `/cathedra/lib/slides.typ`, the Makefile includes `cathedra/makefile.mk`.
  The link is refreshed by every `cathedra` command (uvx installs a new
  version elsewhere). `CATHEDRA` (default `uvx cathedra`) is the
  command the make targets run: pin a version with
  `CATHEDRA := uvx cathedra==0.1.0`, add the widget pictures with
  `CATHEDRA := uvx --from 'cathedra[browser]' cathedra`.
- **A checkout of cathedra** (a git submodule `cathedra/`, for developing
  the engine with the course): the decks import
  `/cathedra/typst/lib/slides.typ`, the Makefile includes
  `cathedra/typst/makefile.mk`, and the make targets run that checkout's own
  version: `CATHEDRA = uv run --all-extras --project cathedra
  cathedra`, chosen automatically when `makefile.mk` is in a checkout.
  Its Python files are used in place (an edit applies to the next command);
  an edit of its Rust sources (`rust/`, `Cargo.toml`) makes `uv run` rebuild
  the native module first (`[tool.uv] cache-keys`; Rust and cargo needed),
  and an edit of the viewer (`viewer/`) needs `pnpm run build` there.

## Makefile

```make
# deck titles, order and target times (optional)
SLIDES_SCHEDULE := ../../course.yaml
# the Zotero / Better BibTeX bibliography
BIB             := ../src/main.bib

include cathedra/makefile.mk          # cathedra/typst/makefile.mk: a submodule
```

The options are listed in [building](building.md#options); `make
update-makefile` writes them into the Makefile as a generated comment block
(around the include line), `make check-makefile` tells whether it is stale.
Then:

```bash
make setup    # the cathedra link (unless a submodule), the bibliography
```

## common/course.typ

What every deck and module imports (`#import "/common/course.typ": *`):

```typst
#import "/cathedra/lib/slides.typ": *
#import "/cathedra/templates/academic/academic.typ": academic

// the course's generated data, given to the template (see below)
#let course-data = if generated {
  (
    ref-links: json("/lib/refs-links.json"),
    widget-shots: json("/.cache/widgets/manifest.json"),
  )
} else { (:) }

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [Statistical Learning],
  background: read("/common/background.svg", encoding: none),
  data: course-data,
)

// the course notation, for maths: $tf(t, d)$
#let tf = math.upright("tf")
```

The engine and the template read no file of the course: `common/course.typ`
reads what the tools generate and gives it to the template (`data:`), which
passes it on to the engine (`course-setup` in `lib/slides.typ`): the
reference links (`lib/refs-links.json`, `cathedra sync`) and the
widgets' pictures for print (`.cache/widgets/manifest.json`, `make
snapshots`). These files are gitignored and optional: the course reads them
only when cathedra compiles (`generated`, true with `--input
cathedra=1`, which cathedra passes; it writes the missing ones,
empty). Plain `typst compile` and an editor read none of them, and compile
from the files git keeps (see [building](building.md#without-cathedra)).

With the `ZOTERO` option, `cathedra sync` also keeps `lib/zotero.json`, the
author's own Zotero items (see [citations](citations.md)): gitignore it too
(`lib/` as a whole, or `lib/refs-links.json` and `lib/zotero.json`).

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

`make install-vscode` (or `cathedra install-vscode`) writes what follows:
the task and the two settings. Decks use root-absolute paths (`/common/…`, `/modules/…`, `/main.bib`):
they start from the course's slide directory (the build's `--root`). The
Typst extension, Tinymist, must be told that directory and the fonts; set it
in the workspace's settings (a `.code-workspace` file, or `.vscode/settings.json`
of the folder opened):

```json
"tinymist.rootPath": "/absolute/path/to/course",
"tinymist.fontPaths": ["/absolute/path/to/course/cathedra/fonts"]
```

- `make install-vscode` also adds the task *Show slide in Typst deck*
  (`.vscode/tasks.json`): it runs `make open-slide` on the file and line
  under the cursor, which sends `GET /goto?file=&line=` to the running deck
  (`make serve`, or the sockets of `make serve-course`) and
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
  `make` once (the editor compiles as plain typst: no generated file needed).

## Housekeeping

```bash
make unused-media          # media files no .typ names (CLEAN=1 deletes them)
make optimize-images       # PNG/JPEG/GIF -> WebP, capped; DRY=1, PRUNE=1
make compute-svg-bb SVG="modules/ir"   # trim SVG canvases (APPLY=1 writes)
```

`unused-media` counts every `"…"` string of a `.typ` that resolves to a file
(relative to it, or `/`-rooted); a name built at run time is not seen, so read
the list before deleting. `optimize-images` rewrites the references to the
`.webp` it writes. Both skip `out/`, `.cache/`, `lib/`, `cathedra`.

## Git

The course versions its directory (with its `.bib` and the images
`make images` fetched) and the `cathedra` link or submodule; what the tool
generates is ignored, and optional (see
[building](building.md#without-cathedra)):

```
out/
lib/
.cache/
```

`make check` fails when a deck, compiled as plain typst, reads a file git
ignores.

## The course site

`make site` / `deploy` publish the decks with an index page (deck list,
synopsis, outline, PDF and practical links): see [building](building.md#the-course-site).
The schedule's entries take, besides `id`, `title` and `target`:

```yaml
lang: en                   # the index page's wording (en, fr)
timePerSlide: 2            # minutes per slide, for the outline's times
timing: dev                # outline times: true, false, dev (default: dev site only)
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
