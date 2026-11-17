# Components

All from `lib/slides.typ`, which the course's `common/course.typ` brings
along. The [API index](api.md) lists every one with its signature.

## Calling a function with content

A function call can take its content arguments as `[…]` blocks written right
after the closing parenthesis: `#alert(title: [Note])[body]` is
`#alert(title: [Note], [body])`. They must follow **without a space or a line
break**: on a new line, a `[…]` is ordinary text of the slide, not an
argument. Inside the blocks, line breaks are free:

```typst
#cols[
  first column
][
  second column
]
```

## Titled blocks

A rounded frame with an icon and an optional title:

```typst
#definition(title: [Eliteness])[A document is *elite* for $t$ if …]
#alert[Do not tune $k_1$ on the test set.]
```

Kinds: `definition`, `observation`, `alert`, `idea`, `remark`, `goal`,
`motivation`, `question`, `problem`, `solution`, `theorem`, `example`, `task`,
`summary`, `hypothesis`, `exercise`; `codeframe` frames code.

## Columns

`#cols(widths: auto, gutter: 1.2em, align: top, ..bodies)`: one content block
per column, side by side.

```typst
#cols[left][right]                          // two equal columns
#cols(widths: (1fr, 2fr))[narrow][wide]     // one width per column: an array
#cols(widths: (1fr, 1fr), align: horizon)[
  #img(path("images/a.webp"), width: 80%)
][
  #goal(title: [Classify each word])[…]
]
```

- `widths`: an **array**, one width per column: `(1fr, 2fr)`, `(40%, 1fr)`,
  `(8cm, 1fr)`. `widths: 1fr, 1fr` (no parentheses) is an error.
- Any number of columns: with `widths: auto` (the default), one equal
  column per block (`#cols[a][b][c]`: three). With an array, its length is
  the number of columns, and more blocks wrap to new rows, as in a grid:
  `#cols(widths: (1fr, 1fr))[a][b][c][d]` is two rows of two.
- `align`: vertical (and horizontal) alignment of the cells: `top`,
  `horizon`, `bottom`, `center + horizon`…
- `gutter`: the space between columns.

## Sidebar slides

A grey column on the left with the slide title and what goes with it (a
sub-heading, the references), the main content on the right with the whole
height of the slide (the title is no longer drawn above it):

```typst
=== Combined Dataset Example: Dolmino
#sidebar[
  Dolmino, the data used to train OLMo
  #reference(<olmo2OLMo22025>)
][
  #img(path("images/dolmino-mix.webp"), vh: 75%, center: true)
]
```

Options: `width` (26%), `gutter` (1em), `fill` (light grey), `title: false`
to leave the slide title out of the sidebar. Inside a template,
`has-sidebar()` (in a `context`) tells whether the current page has one.

## Other blocks

| Typst | |
|---|---|
| `#hand[…]` | a take-home remark |
| `#quote(block: true, attribution: [Salton, 1971])[…]` | a quoted passage (Typst's own `quote`); `attribution: <key>` cites a bibliography entry |
| `#reference(<key>)` | see [citations](citations.md) |
| `#interactive("id", …)` | a live web component, see [widgets](widgets.md) |
| `#mark("kl", …)`, `#annot("kl", step: 2)[…]` | a framed part of a formula or text with a label, see [annotations](annotations.md) |
| `#subhead[…]`, `#subhead(level: 2)[…]` | a heading inside a slide |
| `#items(numbered: false, spacing: …)[…], step(n)[…]` | a list whose items appear in steps, in place (`numbered`: `true`, or a function of the number, e.g. `circled`) |
| `/ Term: description` | a definition list (Typst's own term list): the term in bold on its line, the description indented under it; a description on several lines is indented under `/ Term:`; more room above each term with `#[ #set terms(spacing: 0.9em) … ]`: scope the `#set` in a block, an open `#set` in a module makes Touying add a blank page to the last slide of the file |
| `#img(path("images/x.webp"), zoom: 0.5, center: true)` | an image, see [images](images.md) |
| `#frame(kind: "case-study", title: […])[…]` | a titled frame; `kind` (`block`, `card`, `algorithm`, `case-study`, `soa`, `limitations`) sets the colour |
| `#focus(width: 70%, alpha: 0.85)[…]` | a box over the slide, which is veiled in white (`alpha`: the veil's opacity) |
| `#comment[…]`, `#warning[…]`, `#pro[…]`, `#con[…]` | a side comment, a warning, an advantage, a drawback |
| `#boxed[…]`, `#small[…]` | framed text (`#boxed(center: true)[…]`: centred on its own line; `inset:` the padding, 0.4em × 0.25em), smaller text |
| `#prompt[…]`, `#prompt(size: 0.6em)[…]`, `#placeholder[{x}]` | a prompt given to a model, verbatim in a monospace box (`\` for line breaks; `width: auto` to fit its text, e.g. in an annotation label); a part to fill in, in indigo |
| `#circled(2)` | a number in a disc; as list markers: `#set enum(numbering: circled)`, or `#items(numbered: circled, …)` |
| `#svg-steps(path("x.svg"), reveal: (".part": 2))` | an SVG whose parts appear in steps, see [images](images.md#svg-parts-in-steps) |
| `#overlay(img(…), circle-at(x: 30%, y: 40%, step: 2), rect-at(…), note-at(…)[…])` | shapes and notes over an image, at %-coordinates, in steps, see [images](images.md#shapes-over-an-image) |
| `#svg-object(path("x.svg"))` | an SVG whose links, hover styles and scripts work in the browser, see [images](images.md#interactive-svg) |
| `#details("id", title: […])[slides]`, `#details-link("id")[…]` | "in detail" slides, in an appendix, see [details](details.md) |
| `#wikiref("BM25")`, `#selflink(url)` | a Wikipedia link, a link showing its URL |
| `#frag(n)[…]`, `#frag(n, only: true)[…]`, `#steps("a", "b")` (names), `#steps(n)` (only for `#at-step`) | steps that nest, numbered or named; their number is found by itself (see [authoring](authoring.md#steps)) |

## Icons

Font Awesome Free 7 (fonts installed by `make setup`):

```typst
#fa(0xf1ea)               // solid
#fa(0xf1ea, solid: false) // regular
```

`icons` holds the ones the blocks use.

## Colours

`primary`, `accent`, `link-color`, `muted`.
