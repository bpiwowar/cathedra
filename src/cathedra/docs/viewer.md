# The viewer

## Keys

| Key | |
|---|---|
| → ← ↑ ↓, space | Reveal navigation (steps are fragments) |
| **T** | structure browser: outline, times, badges, slide types to show |
| **M** | hide / show the work-in-progress markers |
| **E** | open the slide's source in VS Code (dev server) |
| **shift-E** | the `#include` chain down to the slide (dev server) |
| **shift-O** | move an annotation's label, written into the source (dev server, see [annotations](annotations.md)) |
| **O** | the slides that overflow (Touying's warnings), to go to or edit; **Esc** still shows the overview |
| **W** | the slides marked work in progress (`#todo` 🚧) or to check (`#to-check` 👀), to go to, edit, or change (**S**) |
| **shift-W** | change the slide's work state (work in progress, to check, done) and its note, written into the source (dev server); a click on the note does the same |
| **Z** | open the Zotero item(s) of the slide's figures and references (dev server; always a picker first) |
| **I** | open the slide's ["in detail" slides](details.md); in them, **I** or **Esc** goes back |
| **H** | this help (dev server); `/` searches it, the API index lists every function |
| **shift-H** | back to the course index |
| **C**, **B** | chalkboard: notes on the slide, blackboard |
| **?** | Reveal's list of keys |

## Overflowing slides (O)

The compiler's overflow warnings (Touying: *detecting slide content
overflow at page n*) are listed by **O**, one row per slide: Enter (or a
click) goes to it, at the overflowing step; **E** (or *edit*) opens its
source in VS Code (dev server). In the dev server, a notification says how
many slides overflow after each build that changes the count, and an
overflowing step has a red bar at its bottom with the excess (*height
+92pt*). `make check` fails on the same warnings.

## Work in progress (W)

**W** lists the slides marked `#todo` (🚧) or `#to-check` (👀), in deck
order, like **O**: Enter (or a click) goes to it, **E** (or *edit*) opens
its source in VS Code, **S** (or *state*) changes its work state (dev
server). See [slide types and todo markers](slide-types.md).

**shift-W**, or a click on a slide's 🚧 / 👀 note, opens the slide's work
state: ↑ ↓ (or a click) picks *work in progress* (`#todo`), *to check*
(`#to-check`) or *done* (no marker), the field is the note (optional; left
untouched, the source's note is kept), Enter saves. The dev server writes it
into the source (POST `/work`): the marker between the slide's heading and
the next one is replaced or removed, or a new one goes on the line after the
heading; the deck then rebuilds.

## Zotero (Z)

In the dev server, an `#img(…, origin: "zotero://…")` and the icon of a
`#reference` are links to Zotero. **Z** lists those of the step shown (the
reference's text, or *figure* and the item key), even when there is one,
to pick with ↑ ↓ / 1–9 and Enter: Zotero opens only on that choice.

## Language

The viewer's strings (help, structure browser, pickers, notices, key list)
follow the template's `lang` (`academic(lang: "fr")`): English and French
(`src/i18n.ts`; another language falls back to English).

## Notifications

Notices for the author appear in the bottom-right corner (`src/toasts.ts`,
`toast(message, {kind, ms, id, action})`): build errors and their fix, the
deck server lost and found again, the overflow count. The centred notice
(`flash`) is kept for what happens during the talk (M, the ends of details).

## Slide addresses

The address names the slide by its title: `#/tokenization-algorithms-wordpiece`,
then the step (`#/marks/2`); it does not move when slides are added above.
An untitled slide takes the previous title with `-2`, `-3`…; a title used
twice gets `-2` too. Reveal updates the address at most once a second.

## Structure browser (T)

Every section and slide with its time and badges; type to filter, Enter or a
click goes to the slide. The *In the deck* checkboxes leave a slide type out
(see [slide types](slide-types.md)).

## Live reload

`make serve` keeps the Typst compiler warm: saving a `.typ` file recompiles
in about 100 ms and the browser re-renders only the pages that changed. The
position in the deck, widget states and chalkboard drawings survive. Errors
show in the browser.

From VS Code, a task can move the open decks to the slide under the cursor:
`GET /goto?file=<path>&line=<n>` on the deck's server (port 8000, or the
socket `out/<deck>.sock` under slide-app's dev server). The RITAL course's
`.vscode/tasks.json` has one (*Show slide in Typst deck*) that tries both.
The other way, **E** opens the slide's source.

## Links

References and links are clickable (the SVG pages' own links). `zotero://`
links open the Zotero app.

## How the pages are shown

The pages are inline SVG, from Typst's own SVG export, completed by the
engine (the printable PDFs are `make pdf`'s, see [building](building.md)):

- the build writes `svg/<hash>.svg` (one per page, named by content),
  `svg/glyphs-<hash>.svg` (the glyph outlines, shared, loaded once) and
  `svg/img-<hash>.*` (each image once); `svg.json` lists them. A live update
  fetches the changed pages only.
- The viewer (`viewer/src/svg-pages.ts`) mounts the pages around the current slide
  and unmounts the others: a page is about a thousand DOM nodes. The
  overview (**Esc**) mounts only the slides on screen (the step shown),
  and unmounts them when they leave it.
- Text selection and find-in-page use a transparent text layer; a copy
  joins the pieces of a line (with a space where they are apart) and puts a
  line break between lines.
- Links are the SVG's own (internal ones go through `details.ts`).
- Morphing moves the parts' SVG elements (see [figures](figures.md)).

On lecture-1 (179 pages): 2.0 MB to transfer for every page (gzip), and only
the pages shown are fetched; the overview opens with a few thousand DOM
nodes.

## SVG pages

What the build gives the viewer, whatever renders the pages (today: Typst's
SVG export plus the engine's native module, `rust/pages.rs`; a backend change
must keep this):

- `svg.json`: `{w, h, glyphs, pages}`: the page size in pt (the page
  markers' exact size), the glyph file (`svg/glyphs-<hash>.svg`) and the page
  hashes in page order.
- A page, `svg/<hash>.svg` (the hash names its content): `<svg
  class="typst-svg" viewBox="0 0 w h" preserveAspectRatio="none">` holding
  one `<g class="typst-page">` (the page's content, in page units: 1 = 1pt),
  then the page's own definitions (clip paths, gradients) if any.
- Glyphs: `<use xlink:href="#g…">` referring to the `<symbol id="g…">` of the
  glyph file, which the viewer puts once in the document.
- Images: `xlink:href="svg/img-<hash>.<ext>"` files, not data URIs.
- Text layer: inside the page's group, after its content, one
  `<foreignObject transform="matrix(…)" x y width height>` per run of text,
  holding `<div class="tsel" style="font-size: Npx">text</div>`
  (transparent; the page's CSS lays it out, `index.html`). Selection,
  find-in-page, copy (`svg-pages.ts`) and the Zotero labels (Z,
  `zotero.ts`) read these.
- Links, after the text layer (so that it does not cover them): `<a
  transform="matrix(…)"><rect width height fill="transparent"/></a>`. An
  external link has `target="_blank"` and its URL in `href` / `xlink:href`
  (a `zotero:` one no target: it goes to the app); an internal one is
  `xlink:href="#" onclick="handleTypstLocation(this, page, x, y); return
  false"` (1-based page; `details.ts` follows it).
- Morphing (`morph-svg.ts`) works on the geometry of the page's elements,
  with the boxes of `morph.json`.
