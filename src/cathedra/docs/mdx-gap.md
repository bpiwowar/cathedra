# MDX features missing from the Typst engine

This page lists what the MDX/React engine (`slide-app/src`, `docs/`, `bin/`, `makefile.mk`)
can do and the Typst engine (`slide-app/typst/`) cannot do yet, as of 2026-11-16.
It is meant to help decide what to port before MDX is dropped. Features
that both engines have (structure browser **T**, todo markers **M**, help **H**,
**E** / shift-E, shift-H, chalkboard **C**/**B**, slide types, outline with
times, live reload, VS Code → browser jump, blocks, icons, `wikiref`, `ext`, `focus`)
are not listed.

Status: **missing**, **partial** (followed by what is missing), or **different** (followed by how Typst does it).
Effort: S (hours), M (a day or two), L (more).

A `gap:<id>` in the first column is the id of the pointers left in the
course's Typst files wherever the conversion lost or approximated that
feature (see [Markers in the converted course](#markers-in-the-converted-course)).

## Authoring components

| MDX feature | Typst status | Effort / idea |
|---|---|---|
| `gap:element-annotation` `<ElementAnnotation>`, `className="element-annotation"` (and their targets: `\cssId{…}` in formulas, `id=` / `name=` on elements): labelled highlight of part of a formula or element (`docs/annotations.md`, `src/annotations.ts`) | **different**: `#mark("id", …)` targets (text or maths) and `#annot("id", step:, …)[label]`, drawn by Typst on the page foreground (web and PDF alike); handout setting (`typst/docs/annotations.md`) | — (the course's annotations are converted) |
| `<Overlay>`, `<CircleOverlay>`, `<RectOverlay>`: shapes drawn over an image (`src/mdx/components.tsx`) | **done**: `#overlay(img(…), circle-at(x:, y:, size:, step:), rect-at(…), note-at(…)[…])`, %-coordinates of the image, `step` / `only` / `until` as `#frag` (`docs/images.md`) | — |
| `<Details>` / `<DetailsLink>`: "in detail" slides written next to the slide they explain, moved to a backup section, with a return to the same step (`docs/details.md`, `src/details.ts`) | **done**: `#details("id", title: […])[slides]` next to the slide, `#details-link("id")[…]`; laid out in an *In detail* appendix (Touying appendix), a title card per group, a back link in the footer (PDF internal links); the viewer returns to the same step (Esc / I / the link), I opens, walls at the end of the talk and of a group (`docs/details.md`). No handout-specific placement | — |
| `gap:prompt` `<Prompt>` (academic template; the course writes `className="llm-prompt"`): a verbatim LLM prompt with placeholders (`templates/academic/components.tsx`) | **done**: `#prompt[…]` (size, width), `#placeholder[…]`, styled like the course's `.llm-prompt` (`docs/components.md`) | — |
| `gap:widget` Live components in a slide (any imported React component, `<Mount>` for imperative renderers; `docs/rendering.md`) | **partial**: `#interactive(id, props, steps, fallback)` covers React and plain JS, but widgets must be registered in the course's `widgets/index.ts` (not imported where they are used). Ported in this course (`widgets/`): `word2vec` (training by hand-written SGD, seeded, no tfjs; pictures at 0/100/300/600/1000/2000/5000 updates) and `french-cooc` (react-force-graph-2d, the CeTZ graph is its print fallback); Convolution was removed from the course on request. Widgets can now be printed: `make pdf`/`make handout` take pictures of widget states in headless Chrome (`snapshot:`/`snapshots:`, `docs/widgets.md`) | M per widget: port the `.tsx` into `widgets/`, keep the CeTZ figure as `fallback` |
| `gap:illustration` Illustrations framework (`src/illustrations/`, `<Figure of=…>`, `<RFragment state>`, `<FigureSlide>`): declarative states, kiwi constraint layout, cells that **morph** between states (`docs/illustrations.md`) | **done** differently: CeTZ figures with `at-step` / `step-captions`, and parts named with `morph("id", …)` move, resize and fade between step pages on the web (`docs/figures.md`, `lib/morph.typ`, `src/morph.ts`); no constraint layout (fixed coordinates) | — |
| `gap:svg-fragment` Fragments driving parts of an SVG (`svg-id`, `svg-selector`, `svg-deselector`) or any element (`fragment-selector`) (`docs/fragments.md`) | **done** for SVGs: `#svg-steps(path, reveal: (sel: step), hide: (sel: step))` adds a `<style>` hiding the selected elements on each step page (`docs/images.md`). `fragment-selector` on other elements: `#frag` around them | — |
| Interactive SVG through `<object>` (links, hover, scripts) (`docs/images.md`) | **done**: `#svg-object(path("x.svg"))`, the engine widget `svg-object` (an `<object>` on a blob URL); a picture in the PDF (`docs/images.md`) | — |
| `gap:fragment-group` `fragment-order` keys, fragment groups (`data-fragment-index`) | **different**: named steps (`#steps("a", "b")`, `#frag("a")`), or one number for several `#frag`s; `mdx2typ` gives every element its own step | — (by hand; the course's one place is done) |
| `gap:fragments` `className="fragments"` (children shown one at a time) | **different**: `#items` / `#frag`; `mdx2typ` leaves the children all shown at once | — (by hand; the course's two places are done) |
| `gap:class`, `gap:circled`, `gap:process` CSS utility classes on any element (`docs/styling.md`: `gray`, `green`, `large`, `font-2x`, `ps-2`, `m-3`, `float-left`, `right`, `bottom`, `spread`, `cell-v-center`, `blur`, `circled`, …) and the course's own classes in `src/lectures/common/theme.scss` (`process`, `deepseek-paper`, `*-loss-formula`) | **done**: `#circled(n)` (`#set enum(numbering: circled)`, `#items(numbered: circled)`); the rest is plain Typst: `#text(fill: …)`, `#comment` (grey), `#align(right)`, `#v(1fr)` (bottom), `#cols(align: horizon)` (cell-v-center), `#cols` (float-left), `#citation` (quote). `process`, `blur`, `important` / `optional` on a block, `font-2x`, `space2`, `deepseek-paper` had no CSS rule in the MDX themes (no-ops) | — |
| `gap:grid` `<Grid>` / `<Columns>` / `<Cell>` with CSS-grid placement (`docs/layout.md`); classes `grid` (with a CSS-grid `style`), `grid2`, `spread` | **done** with `#cols`: `grid2` and `spread` are `#cols[…][…]` (equal columns), a grid filled column first is `#cols(widths: …)` with its cells written row by row (rows wrap), spans by nesting; Typst's `#grid` for the rest | — |
| Block variants `Task`, `Summary`, `Hypothesis`, `Exercice`, `Codeframe`, `Paper`/`Soa`, `Card`, `Algorithm`, `Limitations` | **done**: `#task`, `#summary`, `#hypothesis`, `#exercise`, `#codeframe`, and `#frame(kind: "card"/"algorithm"/"soa"/"limitations"/"case-study")` | — |
| `<Citation entry=…>` (quote whose attribution is a bibliography entry) | **done**: `#citation(source: <key>)[…]` cites the entry | — |
| `gap:cite-doi` `<Cite entry="doi://…">` / `zotero://…` (any entry, fetched if not yet in the bib) | **different**: a key of `lib/refs.bib` only; an unknown DOI is left as `TODO-REVIEW: citation not in the bibliography` (the course's one pointer was already resolved: the entry is in the bib and cited) | S/M: `sync.py` resolves `doi://` through Zotero (like `prefetch-cites`) |
| MathJax macros (`src/lectures/common/macros.tex`, `docs/maths.md`) | **different**: Typst functions in `common/course.typ`; `mdx2typ` rewrites through `common/mdx-notation.json` | — |
| `<TransitionSlide>` | **different**: Touying section / sub-section slides | — |
| `<EditableTable>` (`src/components/`) | **dropped** (not wanted) | — |

## Viewer and keys

| MDX feature | Typst status | Effort / idea |
|---|---|---|
| Speaker view (Reveal notes plugin, **S**: timer, next slide) (`src/index.ts`) | **missing**: no notes plugin in `typst/src/main.tsx`, and no way to write notes | M: see [plan](#speaker-notes-and-the-speaker-view-m-12-days) |
| Overlay editor, **shift-O**: draws an annotation or overlay box on the slide and gives its coordinates (`src/overlay-editor.ts`, `docs/annotations.md`) | **partial**: shift-O moves and resizes an `#annot` label and writes `dx`/`dy`/`width` into the source (dev server); image overlays (`#overlay`) are not editable with it | S: shift-O for `#overlay` shapes |
| **Z**: opens the Zotero item(s) behind the slide's figures and citations, with a picker (`src/zotero-links.ts`, `docs/images.md`) | **done**: **Z** (dev server) takes the `zotero://` links of the step shown (`origin` images, `#reference` icons), always gives a picker (`src/zotero.ts`, `docs/viewer.md`) | — |
| Overflow scanner, **O**: lists the slides that overflow, with an edit link (`src/overflow-overlay.ts`, `docs/overflow.md`) | **done**: **O** lists Touying's overflow warnings (`outline.overflows`, from `build.mjs`) per slide, go / edit; a notification gives the count in the dev server; `make check` fails on them. Reveal's O (overview) stays on Esc | — |
| Print preview, **shift-P** (`?pdf&preview`) (`docs/pdf.md`) | **different**: the PDF is the source of the pages; `make pdf` / `make handout` | — |
| Interface language (`src/i18n.ts`, `docs/i18n.md`: `lang: "fr"` for help, home link, key list, "Loading…") | **done**: `src/i18n.ts` (en, fr), the language from the template's `lang` (page markers → `outline.lang`): help, structure browser, pickers, notices, key list, "Loading…" | — |
| In-app documentation (**H**) | **different**: Typst help (`src/Help.tsx`) shows the Typst docs and the API index | — |
| Notifications / toasts (`src/notifications.ts`) | **done**: `toast()` (`src/toasts.ts`), used for the dev server (errors / fixed, server lost / back, overflow count) | — |
| Lazy loading of images (`data-src`) | not applicable (only the pages around the current slide are mounted, `src/svg-pages.ts`) | — |

## Tooling, CLI and make targets

| MDX feature | Typst status | Effort / idea |
|---|---|---|
| `slide-app init` / `slide-app new` (`bin/typst-course.js`, `docs/cli.md`) | **done**: Typst is the default (`--mdx` for the old behaviour): `init` writes `Makefile`, `course.yaml`, `common/course.typ`, a first deck, `main.bib`, the `slide-app` link; `new` writes `lectures/<id>.typ` and adds it to the schedule | — |
| `make update-makefile` / `check-makefile` (generated option block) | **done**: the Typst `makefile.mk` has `#@option` lines; the block keeps the course's own include line (`bin/sync-makefile.js`) | — |
| `make duplicates` / `outline --duplicates-only`: files included more than once (`bin/deck-outline.js`) | **done**: `make duplicates` (`tools/outline.mjs --duplicates`, a static scan of the `#include`s) | — |
| `make check-overflow` | **different**: `make check` | — |
| `make pdf-diff` / `slide-app pdf-diff` (two print paths compared) | not applicable (one PDF) | — |
| `slide-app cite`, `prefetch-cites`, `refresh-cites`, `dedupe-bib`, `clean-bib` (`bin/*.js`) | **different**: Typst reads the Better BibTeX export through `tools/sync.py`; no search, no DOI fetch, no refresh | S: they still work on the shared `.bib`; keep them as engine-independent tools |
| `slide-app unused-media` (`bin/find-unused-media.js`) | **done**: `make unused-media` / `slide-app unused-media` in a Typst course (`tools/unused-media.mjs`: every string of a `.typ` resolving to a file); names built at run time are not seen | — |
| `slide-app compute-svg-bb`, `make optimize-images` (`bin/optimize-images.mjs`) | **done**: `make compute-svg-bb SVG=…`, `make optimize-images` (`--typst`: reads `.typ` references, `/`-rooted ones from the course root) | — |
| `slide-app open-slide`, `install-vscode` | **done**: `make open-slide FILE= LINE=` (`tools/open-slide.mjs`, `GET /goto`), `make install-vscode` writes the task and the Tinymist settings | — |
| `check-edit-keys` (regression test of E / shift-E / Z) | **different**: `make live-test` (browser tests) | — |

## Citations and images

| MDX feature | Typst status | Effort / idea |
|---|---|---|
| `<Image src=… origin="zotero://…">` fetching the image (Zotero annotation, URL) into `cache/` at build time (`docs/images.md`) | **done** (`make images`, `tools/images.mjs`): `#img("https://…")`, or `#img(path("images/x.webp"), origin: "zotero://…")` when the file is missing, is fetched into `.cache/images/` (Zotero: the annotation render in `~/Zotero/cache/library`); see `docs/images.md` | — |
| Build-time downsampling with sharp (`resize="800x"`, resolution cap, WebP variants) | **partial**: fetched images are capped (`resize: "800x"`, or the slot `vh`/`vw` x 2, else 1920 px) and written as WebP; images committed in the course are left alone, `make check-images` flags the heavy ones (> 1 MB or > 2400 px) | S: rewrite committed images (`optimize-images` for `typst/`) |
| `filename=` rename of fetched images | **done**: `filename: "name"` names the cached file (default: a hash) | — |
| Pre-rendered CSL references with Zotero links in dev mode | **done** (`#reference`, `refs-links.json`) | — |

## Build and deploy

| MDX feature | Typst status | Effort / idea |
|---|---|---|
| Course index page: deck list, synopsis, outline, PDF and practical links (`docs/synopsis.md`, webpack) | **done**: `make site` (`tools/site.mjs`, `docs/building.md` "The course site"), from the schedule, the decks' outlines (`#synopsis`) and `practicals.json`; no webpack | synopsis maths is plain text (no MathJax / SVG) |
| `make deploy` / `deploy-dev` (rsync), `make zip`, `html-force` | **done**: in the Typst `makefile.mk` (`deploy`, `deploy-dev`, `zip`, `site-force`; same options `DEPLOY_DEST(_DEV)`, `DEPLOY_PDF`), `DRY=1` for `rsync -n`; the site is checked for local absolute paths first | — |
| Practicals manifest and links (`docs/practicals.md`, `practical-manifest::` hooks) | **done**: `PRACTICAL_MANIFEST` and the `practical-manifest::` / `practical::` hooks in the Typst makefile; links on the index page | `#module-meta(practicals:)` not used for the links (the schedule says which deck) |
| `dev: true` decks, `pdf: true` per deck, MD5-cached PDF generation | **done**: `make site` / `site-dev`, `site-pdf` / `site-pdf-dev` read `dev` / `pdf` from the schedule; a PDF is recompiled when the MD5 of its `typst --deps` inputs changes | — |
| MDX dev server (`make serve-dev`) with all decks and the index | **done**: `make serve-course` (port 9010): the index, each deck's dev server started on its first request under `/<id>/` | — |

## Plans for the larger gaps

Not done yet; each plan says how, where, the effort and what is still open.
Ordered by usefulness for this course.

### Course index page and deploy without webpack (done)

Done as planned, with different target names so that the per-deck `html` /
`pdf` (which slide-app's MDX makefile still calls) keep their meaning:
`tools/site.mjs` and the Typst makefile's `site` / `site-dev`, `site-pdf` /
`site-pdf-dev` (MD5 of the `typst --deps` inputs, `.cache/pdf/`), `deploy` /
`deploy-dev` (`DRY=1`: `rsync -n`), `zip`, `site-force`, the
`practical-manifest::` / `practical::` hooks, and `serve-course` (the whole
course on port 9010, deck servers on demand). Same option names as the MDX
makefile (`DESTDIR`, `DEPLOY_DEST`, `DEPLOY_PDF`, `PRACTICAL_MANIFEST`,
`ZIP_OUT`), plus `STATIC`. See `docs/building.md` "The course site".

- **Left**: the synopsis is plain text (Typst maths in a `#synopsis` is not
  typeset on the index page); `lib/typst-decks.js` and the webpack index are
  still there for courses with MDX decks.

### "In detail" slides (`<Details>`, M, 1–2 days)

- **Authoring**: `#details(id, title: […])[slides…]` written right after the
  slide it explains, and `#details-link(id)[text]` on that slide.
- **Typst**: the content is not laid out in place: `details` records its
  body as `<details>` metadata; the template's last section ("In detail",
  a Touying appendix) lays out every recorded body, each a slide group with
  a `page-marker(kind: "details")` and a back link. `details-link` is a
  `link(<details-id>)` (works in the PDF too).
- **Viewer** (`src/main.tsx`): a link to a details slide remembers the
  current slide and step; a "back" button (and Backspace) returns to it
  (port the logic of `src/details.ts`, without the DOM moves). The structure
  browser lists the details section as backup material (not timed: a slide
  type `details`).
- **Open**: in a handout, details at the end (as now in MDX) or right after
  their slide (`#details` can lay out in place when `is-handout`).

### Speaker notes and the speaker view (M, 1–2 days)

- **Authoring**: `#notes[…]` anywhere in a slide: `[#metadata((slide:,
  body: plain(body)))<notes>]`, so no layout change.
- **Build** (`build.mjs`): query `<notes>` with the page markers and write
  `notes.json` (slide → text, as HTML from the Typst content via
  `typst-ts` HTML export, or plain text first).
- **Viewer**: load Reveal's notes plugin in `src/main.tsx`, and give each
  `<section>` an `<aside class="notes">` from `notes.json`; **S** opens the
  speaker view (current and next page are the SVG pages, so the
  speaker window needs the same renderer: simplest is to let the notes
  plugin open the deck URL with `?receiver`, which renders itself).
- **Open**: the course has no notes yet (none in the MDX either), so the
  value is for other courses; a handout with notes (`make handout NOTES=1`)
  would be cheap once the metadata exists.

### Images fetched at build time, downsampled (M, 1–2 days)

- **Authoring**: unchanged `#img(path("images/x.webp"), origin: "zotero://…")`;
  a missing file whose `origin` is known is fetched.
- **Tool**: `tools/fetch-images.py` (uv script) scans the course's `.typ`
  for `#img(path("…")…, origin: "…")` (a regex on the call, as
  `tools/annot-source.mjs` does for `#annot`), and for each missing file:
  a `zotero://open-pdf/…annotation=KEY` origin → the image Zotero renders
  for that annotation, `~/Zotero/cache/library/KEY.png` (as the MDX build
  does, `lib/require-resolver.js`; Zotero writes it when the annotation is
  shown), an `http(s)` origin → download. Then downsample with Pillow: at most 2× the size it is shown
  at (the `zoom` / `vh` of the call, 700 px = page height), WebP. Run by
  `make setup` and before `make html/pdf` (`$(GEN)`).
- **Check**: `make check` warns about images heavier than N kB per shown
  pixel.
- **Open**: overwrite or not a file already there (no, unless `--force`);
  `filename=` of the MDX is the `path` itself here.

### Interface language (S–M, 1 day)

- `typst/src/i18n.ts`: a string table (en, fr) for Help, StructureBrowser,
  the key list, "Loading…", the error box; the language is read from the
  deck (`academic(lang: "fr")` is already the text language: export it in
  `outline.json`, e.g. `lang`).
- Port the French strings from `src/i18n.ts` (347 lines, mostly keys
  already translated).

### Viewer keys: overflow list **O**, Zotero **Z**, image overlays (S each)

- **O**: `build.mjs` already sees Touying's overflow warnings (the
  diagnostics of the compile); send them with the update (`overflows:
  [{g, file, line}]`) and list them in the structure browser (a filter
  "overflowing"), each with its edit link.
- **Z**: collect the `zotero://` link annotations of the current page(s)
  (the SVG page's links), open the only one, or a picker
  (the structure browser's list component) when several.
- **Overlays** (`<Overlay>`, `<CircleOverlay>`, `<RectOverlay>`; unused by
  this course): `#overlay(img, (circle(x: 30%, y: 40%, r: 5%, step: 2),
  rect(…)))`, `place` in a `box` of the image's size, steps through `#frag`;
  shift-O could move them like `#annot` labels (`AnnotEditor.tsx`).

### Tooling (done)

`slide-app init` / `new` (Typst by default, `--mdx` for MDX),
`make update-makefile` / `check-makefile`, `unused-media`, `optimize-images`,
`compute-svg-bb`, `install-vscode`, `open-slide` all work on a Typst course
(`docs/cli.md`, `docs/course.md`). Left: `unused-media` does not see file
names assembled at run time, nor references from widget TypeScript.

### Widgets for the live MDX components (M per widget)

`gap:widget`: done (no pointers left). `Word2Vec` and `FrenchCooc` are
live widgets in the course's `widgets/` (`docs/widgets.md`); the Convolution
slides of `models/models.typ` were removed on request. A widget drawn on
every step page of its slide is now one widget on the web (`build.mjs`
dedupes by id/position/size).

### Morphing illustrations (done)

`gap:illustration`: done without a widget. `#morph("id", …)` names a part of
a figure (CeTZ elements or content); the build records each part's box per
page and compiles the deck once more without the parts (the background);
the viewer animates crops of the step pages between consecutive steps
(FLIP: translate, and scale when the size changes; fades for the rest).
See `docs/figures.md`. The 6 figures (lecture-1: predict-next, encoder,
attention, FFN, layer trace; models: text as memory) use it; the pointers
are removed.

### Others

- Interactive SVG (`<object>` with links and scripts; unused by this course):
  a generic `svg` widget that inlines the file; S.
- Notifications / toasts: only if a feature needs them (the error box covers
  build errors).
- `<EditableTable>`: dropped (not wanted).
- `slide-app cite` / `prefetch-cites` / `refresh-cites`: they work on the
  shared `.bib`; a `doi://` key in a `.typ` could be resolved by `sync.py`
  through Zotero (as `prefetch-cites` does) — S/M, only if a course writes
  DOIs instead of keys.

## Markers in the converted course

Wherever `mdx2typ` (or the hand port that followed) lost or approximated an
MDX feature that the Typst engine lacks, the course's `.typ` file carries a
pointer, so that once the feature is ported every place to use it can be
found, with what the original was (the MDX sources will be deleted):

```typst
// TODO-REVIEW[gap:element-annotation] annotation pointing at "sim" in the formula above (#colbert-sim) — MDX: src/modules/ir/neural-interaction.mdx:64
// | <div className="element-annotation fragment" data-highlight-target="#colbert-sim">cosine or inner product</div>
```

- `TODO-REVIEW[gap:<id>]`: the id of a row of the tables above, then what to
  do once it is ported, then the MDX file and line (relative to `slides/`,
  as of the conversion);
- `// | …` lines: the MDX of that element (at most ~15 lines; a long one keeps
  its opening lines and its closing tag, `…` for what is left out; long lines
  are cut with ` …`). For an annotation, the target element (`name=` / `id=`)
  comes first when it is elsewhere.
- One pointer per MDX element: adjacent annotations of one `div.fragments`
  share one pointer; a pointer sits right before the Typst that renders the
  element (or where it would go, for content the conversion dropped).
- Comments only: the rendered decks are unchanged.

Find them with `grep -rn "gap:prompt" typst/` (one id) or
`grep -rn "TODO-REVIEW\[gap:" typst/` (all); `grep -rn TODO-REVIEW` still
lists them with the other review markers.

## Used by this course

`grep -rn "TODO-REVIEW\[gap:" slides/typst/{modules,lectures}`: 10 pointers
left in 4 files (121 in 27 files after the conversion; they replaced the 113
`TODO-REVIEW: class …` markers of the conversion, merged per element, plus 20
places the conversion degraded silently). The ones that are gone were
replaced by the Typst feature (counts as of the conversion):

| Id | Count | What is pointed at | Status |
|---|---|---|---|
| `gap:class` | 37 | utility / course classes: `gray` 7, `green` 7 (3 of them `<span>`s dropped silently), `ps-2` 5, `cell-v-center` 3, `bottom` 2, `quote` 2, `right`, `space2`, `large`, `font-2x`, `important`, `blur`, `deepseek-paper`, `m-3 float-left`, `me-2 ms-2` (dropped silently), `optional` on a block, `:::comment{.space}` (not converted) | done: plain Typst (`#comment`, `#text(fill: …)`, `#align`, `#v`, `#cols`, `#citation`); the classes without a CSS rule (`ps-2` is pure spacing) dropped |
| `gap:element-annotation` | 25 | 19 annotations or groups of annotations (a `div.fragments` of annotations counts once), 6 lost highlight targets (`\cssId{…}` dropped from 4 formulas and 1 list item; the `id=`s of a list) | done: `#mark` / `#annot` |
| `gap:prompt` | 25 | `className="llm-prompt"`; one prompt lost by the conversion (`rag.mdx:84`, a `<pre>` with a template literal) | done: `#prompt`, `#placeholder` (the lost one restored) |
| `gap:grid` | 8 | `grid` 3, `grid2` 2, `spread` 3 | done: `#cols` |
| `gap:illustration` | 6 | `<Figure of=…>` with morphing states (lecture-1: predict-next, encoder, attention, FFN, layer trace; models: text as memory), now CeTZ figures with `at-step` | done: `morph` parts, animated on the web |
| `gap:circled` | 6 | `ol.circled` | done: `#circled` |
| `gap:process` | 5 | `div.process` | done: dropped (no CSS rule for `.process` in the MDX themes) |
| `gap:widget` | 0 | `<Word2Vec />`, `<FrenchCooc />` ported as live widgets (`<Convolution layers=1/2 />` removed on request) | done |
| `gap:fragments` | 2 | `div.fragments` / `ol.fragments` outside annotations (in annotations: `gap:element-annotation`) | done: `#frag`, `#items` |
| `gap:svg-fragment` | 1 | teacher forcing: `svg-id` / `svg-selector=".generating"` | done: `#svg-steps` |
| `gap:fragment-group` | 1 | lecture-7 overview: `data-fragment-index` groups split into one step per element | done: one step per group |
| `gap:cite-doi` | 1 | `doi://10.48550/arXiv.2202.05924` (not in the bibliography) | done: the entry was already in the bib and cited (`sevillaComputeTrendsThree2022`) |

Not used by this course (no pointer): `<Overlay>`, `<Details>`, speaker
notes, interactive `<object>` SVGs (the course's `<object>` SVGs are static
and became `#img`), `<EditableTable>`, the missing block variants.

Custom React/TS components of the MDX decks (`slides/src`), all ported as
static CeTZ figures rather than widgets: `Word2Vec` (`Word2VecFig.tsx`, live
tfjs training → replayed offline), `FrenchCooc` (force layout),
`EncoderLocator`, and the lecture-1 illustrations (encoder, attention, FFN,
predict-next, layer trace, text-as-memory). `RNN.tsx` and `show-vectors.ts`
are not used by any deck.
