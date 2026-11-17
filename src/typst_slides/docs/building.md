# Building and checking

`make help` lists the targets, by section — in colour on a terminal unless
`NO_COLOR` is set (`HELP_COLOR=yes|no` forces it). A course adds its own
section with an exported `HELP_PROJECT` define: a title line, then
`  <target>  <description>` lines.

| Target | |
|---|---|
| `make setup` | the `slide-app` link (unless a submodule), bibliography |
| `make serve DECK=<id>` | dev server on http://localhost:8000 (writes into `OUT`) |
| `make html` | the web decks, `out/<deck>/`: the pages as SVG (`svg/`, `svg.json`), the slide structure, the viewer (see [the viewer](viewer.md#how-the-pages-are-shown)) |
| `make pdf` | printable PDFs, `out/<deck>.pdf`, one page per step |
| `make handout` | handouts, `out/<deck>-handout.pdf`: one page per slide, its last step |
| `make check` | compile every deck; fail on errors, on slides that overflow, and when plain `typst compile` could not compile a deck from a clone (see [below](#without-typst-slides)) |
| `make outline` | deck structure, slide counts, time vs the `target` of `course.yaml` |
| `make outline-slides` | the same, with every slide and its `file:line` |
| `make duplicates` | the files `#include`d more than once, by one deck or across decks, with where |
| `make convert MODULE=<topic>` | port an MDX module (see [conversion](conversion.md)) |
| `make migrate` | migrate the sources to the engine's API version (`DRY=1`: a diff only; see [upgrading](upgrading.md)) |
| `make space` | canonical blank lines between slides |
| `make format` | indent every `.typ` with [typstyle](https://typstyle-rs.github.io/typstyle/) (`brew install typstyle`); the converter runs it too |
| `make live-test` | browser tests of the viewer, against `make serve` (a slide-app checkout, `typst-slides[browser]`) |
| `make serve-course` | the production site, live, on http://localhost:9010: the index page and its decks, no `dev: true` deck or practical (see [the course site](#the-course-site)) |
| `make serve-dev` | the same for the dev site: the `dev: true` decks and practicals too |
| `make site` / `site-dev` | the course site: decks, index page, static files, in `DESTDIR` / `DESTDIR_DEV` |
| `make site-pdf` / `site-pdf-dev` | the PDFs of the `pdf: true` decks, `<site>/pdf/<id>.pdf` (MD5-cached) |
| `make deploy` / `deploy-dev` | site + PDFs, rsync to `DEPLOY_DEST` / `DEPLOY_DEST_DEV` |
| `make zip` | the site as `ZIP_OUT`, PDFs left out |
| `make update-makefile` / `check-makefile` | refresh / verify the generated option list in the course Makefile |
| `make unused-media` | media files no `.typ` references (`CLEAN=1` deletes them) |
| `make optimize-images` | PNG/JPEG/GIF to WebP, capped in size, references rewritten (`DRY=1`, `PRUNE=1`) |
| `make compute-svg-bb SVG=<paths>` | trim SVGs to their content (`APPLY=1` writes; default `modules common`) |
| `make install-vscode` | VS Code task *Show slide in Typst deck* and the Tinymist settings (see [course](course.md#vs-code)) |
| `make open-slide FILE=<f.typ> LINE=<n>` | move the running deck to the slide at that line |

## The dev server

`make serve` (and `make serve-course`, which starts one per deck) applies
changes live: the deck and its modules, any file the last compilation read
(images, data, the bibliography), the engine's `lib/` and `templates/`, the
course's widgets (the page reloads) and these docs (the help). The server's
own code (Python) and the viewer bundle are not reloaded in place: restart
`make serve` after changing them; the open pages reconnect and reload.

Every make target runs `$(TYPST_SLIDES) <command>` (see
[course](course.md#the-engine-package-or-submodule)); `typst-slides --help`
lists the commands, which can also be run by hand from the course directory
(`typst-slides check lectures/lecture-1.typ`, `typst-slides outline --slides`…).
Decks are compiled in parallel threads in one process (the compilations share
Typst's cache), and every compilation gets the engine's fonts.

## Options

Set in the course Makefile, before the include (see [setting up a
course](course.md)), or on the command line (`make serve DECK=lecture-2`):

| Option | Default | |
|---|---|---|
| `BIB` | (required) | the Zotero / Better BibTeX bibliography |
| `TYPST_SLIDES` | `uvx typst-slides`, or `uv run --all-extras --project <checkout> typst-slides` in a checkout of slide-app | the command the targets run |
| `SLIDES_SCHEDULE` | none | YAML `lectures: [{id, title, target}]`: titles, order, target times |
| `DECK` | the first deck | what `make serve` shows |
| `DEV` | none | `DEV=1`: `make html` builds for the author — **E** / shift-E open the sources, references link to Zotero — it writes the sources' absolute paths into the output: not for publishing |
| `PORT` | 8000 | dev server port |
| `OUT` | `out` | output directory |
| `SRC` | `.` | where the sources are (`lectures/`, `modules/`, `common/`, `widgets/`); the course directory stays Typst's root (`lib/`, `.cache/`, `out/`), so their paths start with `/$(SRC)/` |
| `DECKS` | every deck of `$(SRC)/lectures/` (`<id>.typ` or `<id>/<id>.typ`) | the decks `html` / `pdf` / `handout` / `check` build |
| `MDX_SRC` | `../src/modules` | slide-app MDX modules, for `make convert` |
| `MDX_MACROS` | `../src/lectures/common/macros.tex` | their MathJax macros |
| `MDX_BACKUP` | none | where `make convert` moves each MDX file it converted |
| `DESTDIR` / `DESTDIR_DEV` | `out/site` / `out/site-dev` | the course site (production / dev) |
| `STATIC` | none | a directory copied as is into the site (e.g. an `externalPdf`) |
| `PRACTICAL_MANIFEST` | none | the practicals' JSON manifest, for the index page's links |
| `DEPLOY_DEST` / `DEPLOY_DEST_DEV` | none | where `deploy` / `deploy-dev` rsync the site (`host:/path/`) |
| `DEPLOY_PDF` | `yes` | `no`: deploy without (re)compiling the PDFs |
| `ZIP_OUT` | `$(DESTDIR).zip` | the archive of `make zip` |
| `COURSE_PORT` | 9010 | port of `make serve-course` |

## The course site

`typst-slides site` makes what a course publishes, from the schedule
(`SLIDES_SCHEDULE`, see [course](course.md#the-schedule)):

- `make site` builds every deck of the schedule into `DESTDIR/<id>/` (a
  `dev: true` deck only in `make site-dev`, into `DESTDIR_DEV`), copies
  `STATIC`, and writes `index.html`: the decks in order, with their PDF link
  (`pdf: true`), `[dev]` badge, synopsis (`#synopsis` before the title slide,
  else the schedule's `summary`), a foldable outline (sections, sub-sections,
  their `#synopsis` and time at `timePerSlide` minutes per slide, 2 by
  default) and practical links. A lecture with `externalPdf` (a path in the
  site, e.g. from `STATIC`) is only a link. A deck directory no longer in the
  site is removed. The build fails if a text file of the site holds a local
  absolute path (the course directory, `$HOME`).
- `make site-pdf` / `site-pdf-dev` compile the `pdf: true` decks to
  `<site>/pdf/<id>.pdf`, the index's PDF links (with the widget pictures,
  `make snapshots`). A PDF is compiled again only when the MD5 of what its
  last compilation read changed: `.cache/pdf/`; `FORCE=1`
  compiles them all.
- `make deploy` / `deploy-dev`: the `practical` hook, the site and its PDFs
  (not with `DEPLOY_PDF=no`), then `rsync --delete` to `DEPLOY_DEST` /
  `DEPLOY_DEST_DEV` (an error if unset). `DRY=1` runs `rsync -n`: what would
  change, nothing sent.
- `make site-force` / `site-dev-force` start from an empty directory; `make
  zip` archives the site (no PDFs).

The practicals (slide-app's `docs/practicals.md`): `PRACTICAL_MANIFEST` names
the JSON manifest (`{baseUrl, practicals: [{id, name, files: [{label,
path}]}], bundles}`) and the schedule's `practicals: [id, {id, optional:
true}]` which deck introduces which. The course refreshes the manifest with
its own `practical-manifest::` rule (run before every site build), and may
build the practicals before a deploy with `practical::`:

```make
PRACTICAL_MANIFEST := ../practicals.json
include ../slide-app/typst/makefile.mk

practical-manifest::
	$(MAKE) -C ../../pratical manifest MANIFEST=$(abspath $(PRACTICAL_MANIFEST))
```

The index's wording is English; `lang: fr` at the top of the schedule
translates it, and `index: {practicals: TP}` overrides a string (`title`,
`lectures`, `practicals`, `optional`, `outline`, `expandAll`, `collapseAll`).

`make serve-course` is the dev server of the whole course (port
`COURSE_PORT`, 9010) as the production site lists it, `make serve-dev` as the
dev site does (with the `dev: true` decks and practicals): the index on `/`
(rebuilt when a source changes, the page reloading), and under `/<id>/` the
deck's own dev server
(live reload, E, H…), started on its first request on the socket
`out/<id>.sock` and stopped with this server; a deck server already on that
socket (`make serve DECK=<id> SOCKET=out/<id>.sock`) is used as is. Other
paths are files of `STATIC`, then (`serve-dev` only) of the dev site, then of
the site (their `pdf/`).

## Overflow

Touying warns when a slide's content goes past the page; `make check` turns
that into an error. Shorten the slide, split it, or use `#cols`.

## PDF variants

A handout (`make handout`, or `--input handout=1`) keeps the last step of each
slide. Content that should differ there uses `#print[…]` / `#web[…]` (the
handout is a print output), or tests `is-handout`.

The page shape is `"16-9"` by default (841.89pt, A4, wide). The course sets
another with `academic(aspect-ratio: "16-10")`, a deck with
`course-theme.with(aspect-ratio: "16-10", …)`, and a single compile with
`--input aspect-ratio=16-10` (which wins over both). Any `"W-H"` works:
`"16-10"` (WXGA / WUXGA projectors, MacBook screens), `"4-3"`, …

```bash
typst compile --root . --font-path slide-app/fonts lectures/lecture-1.typ out.pdf \
  --input todo=0      # no work-in-progress notes (the typst CLI, if installed)
```

## Without typst-slides

A course does not depend on typst-slides being maintained: a clone of it
compiles to PDF with plain `typst compile`, and its authors can stop using
the tool at any time. Typst does all of the typesetting, and the engine's
Typst world is the typst CLI's (the same packages, from Typst Universe, and
the fonts built into Typst, plus the engine's `fonts/`). What the tool adds
is the web version (the viewer, the live widgets), the course site, and
generated files that only improve the PDFs:

| Generated (gitignored) | Without it |
|---|---|
| `lib/refs-links.json` (`make setup`) | the icon of `#reference` has no link |
| `.cache/widgets/` (`make snapshots`) | a widget shows its `fallback`, or a dashed frame |

The course reads them only when typst-slides compiles (`generated` in
`lib/slides.typ`, set by `--input typst-slides=1`): the files git keeps are
enough for the rest. In particular:

- the decks cite the course's `.bib` itself, with the engine's style
  (`bib-style`): see [citations](citations.md) (a duplicate key fails);
- an image fetched by `make images` is written to its path, a file of the
  course to commit: see [images](images.md#fetched-images).

```bash
git clone --recurse-submodules <course> && cd <course>
typst compile --root . --font-path slide-app/typst/fonts \
  src/lectures/lecture-1/lecture-1.typ lecture-1.pdf
```

(`--input handout=1` for the handout.) The engine comes with the course: a
`slide-app` submodule, or a copy of the package's `typst/` directory in
place of the `slide-app` link; once it is published on Typst Universe, the
decks import it as a package.

**Kept that way by `make check`:** besides the normal compilation, it
compiles every deck as plain typst does (no `typst-slides` input) and fails
when that compilation fails, or reads a file that git ignores and does not
track (a clone would not have it). Whatever adds such a dependency, a
migration, a tool or a hand edit, is caught there, not on the day the tool
is gone. The engine's tests also compile a made-up course with the typst CLI
(when installed), without its generated files.
