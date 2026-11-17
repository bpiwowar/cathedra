# Changelog

The Typst engine's changes, by **API version**: the integer in
[`VERSION`](VERSION). A course records the version its sources are migrated
to in `.slide-app-version` (missing = 1); `make migrate` brings it up to date
(see [docs/upgrading.md](docs/upgrading.md)). The format follows
[Keep a Changelog](https://keepachangelog.com/).

## API 2

### Added

- A slide's number of steps is found by itself: `#frag`, `step(n)` in
  `#items`, `#annot(step:, until:)`, `#svg-steps`, `#overlay` shapes,
  `#step-captions` and `#interactive(snapshots:)` are counted as Touying's
  `#pause` / `#only` / `#uncover` are, at any depth (frames included).
  `#steps(n)` is only needed for an `#at-step` figure alone, or a step
  function inside a `context` / `layout` / CeTZ canvas (a step the slide does
  not reach stops the compilation, saying so); `#steps("a", "b")` still names
  steps. `#steps(n)` keeps working (a minimum). `step-marks(body)` makes the
  steps of a component's own `layout`-ed body visible.
- Dev server: a red bar at the bottom of a step that overflows, with the
  excess (*height +92pt*).
- `academic(aspect-ratio: "16-10")` (or a deck's `course-theme.with(aspect-ratio: …)`,
  or `--input aspect-ratio=16-10`): any `"W-H"` page shape, 841.89pt wide.
- `tools/migrate.py` and `make migrate` (`DRY=1`): migrate a course's sources
  to the engine's API version; `make` warns when the course is behind.
- `VERSION` (the engine's API version) and `.slide-app-version` (the course's).
- Native term lists: `/ Term: description` (and `#set terms(spacing: …)`),
  styled by the template.
- Block quotes are Typst's own: `#quote(block: true, attribution: …)[…]`
  (the attribution can be a label, which cites).
- Figure captions are Typst's own: `#figure(img(…), caption: […])` (small,
  centred, not numbered).
- `#img` with only `vh:` or `vw:` scales the whole image (proportions kept,
  smaller if wider than the space), never cropped.

### Changed

- The web viewer shows the pages as SVG only (the PDF.js viewer is gone); the
  PDF mode of the viewer no longer exists.
- `#img` without a size is inline, so images side by side stay on one line.
- `make clean` also removes the fetched images cache (`.cache/images`).

### Deprecated

- `#dt[term]` + `#dd[description]` (and `#dt(above: …)`): use
  `/ Term: description`. Aliases kept.
- `#citation(source: X)[…]`: use `#quote(block: true, attribution: X)[…]`.
  Alias kept.

### Removed

- `#img(…, caption: […])`: use `#figure(img(…), caption: […])`.
- `#ext(url)[…]`: use `#link(url)[…]`.

### Migration

`make migrate` rewrites: `#img(caption:)` to `#figure`, `#dt`/`#dd` to term
lists (including the pair split over two `#frag` blocks), `#citation` to
`#quote`, `#ext` to `#link`. A `#dt` followed by several `#dd`, or with no
`#dd` right after it, is reported and left as is. The spacing of the old
`#dt(above: …)` becomes a `#set terms(spacing: …)` inside a `#[ … ]` block
around the group (or inside the `#frag`): left open in a module, a `#set`
makes Touying add a blank page after the last slide of the file.

## Earlier (API 1)

The engine before versioning, newest first:

- SVG pages viewer; morphing figures (`#morph`) moving parts between step
  pages, computed in the viewer.
- Course site without webpack: index page, `make site`, `site-pdf`, `deploy`,
  `zip`, `serve-course`.
- Images fetched at build time (URL / Zotero origin), downsampled
  (`make images`, `check-images`); `unused-media`, `optimize-images`,
  `install-vscode`, `open-slide`.
- "In detail" slides (`#details`, `#details-link`), `#overlay` shapes over
  images, `#svg-object`, `#svg-steps`; viewer keys O (overflowing slides),
  Z (Zotero items), details navigation, i18n, toasts.
- Pictures of React widgets in the PDFs and handouts (headless Chrome,
  cached; `make snapshots`); widget snapshots of any state.
- `#task`, `#summary`, `#hypothesis`, `#exercise`, `#codeframe`, `#prompt`,
  `#placeholder`, `#circled`.
- Element annotations `#mark` / `#annot`, drawn by Typst, moved with shift-O.
- `mdx2typ` conversion of MDX modules and decks; `make outline`,
  `duplicates`, `space`, `format`, `live-test`.
