# Converting from MDX

```bash
make convert MODULE=bm25
```

reads `$(MDX_SRC)/<id>/<id>.mdx` (default `../src/modules`) and writes
`modules/<id>/<id>.typ` (and `figures/`). It is a one-shot migration aid:
the output is reviewed and edited by hand, not regenerated. **Converting
again overwrites the hand edits**: check `git diff` after.

With `MDX_BACKUP=<dir>` (`--backup`), each converted `.mdx` is then moved to
`<dir>/modules/<id>/<id>.mdx` (a deck: `<dir>/lectures/<id>/<id>.mdx`), never
overwriting a backup. This converts in place: with `MDX_SRC` and the Typst
sources in the same folders (`SRC=src`, `MDX_SRC=src/modules`), the `.typ`
takes the place of the `.mdx` and keeps its images where they are. A deck
whose folder `lectures/<id>/` exists is written there, as `<id>.typ`.

## How

1. The JSX is turned into pandoc markdown (headings, fenced divs, raw Typst).
2. pandoc converts markdown to Typst and LaTeX maths to Typst maths, with the
   MathJax macros of the MDX decks (`MDX_MACROS`) expanded;
   `tools/mdx2typ.lua` turns the divs into `lib/slides.typ` calls.
3. The maths is tidied to use the course notation, `---` / `--` become
   dashes, `tools/spacing.py` spaces the slides.

The output starts with `#import "/common/course.typ": *`.

## The course notation

pandoc writes a LaTeX macro such as `\tf` as `upright(t f)`. The course maps
these back to its own Typst names (those of `common/course.typ`) in
`common/mdx-notation.json`, a list of `[regex, replacement]` pairs applied to
every formula:

```json
[
  ["upright\\(t f\\)", "tf"],
  ["bb\\(R\\)", "RR"]
]
```

When `common/course.typ` defines `#let vv(`, `#let mm(` or `#let softmax`, the
converter also emits them (detected automatically, nothing to configure; a
course without them is unchanged): `\mathbf{x}` / `\boldsymbol{x}` ->
`vv(x)` (`mm(X)` for a capital), `\operatorname{softmax}` / `\text{softmax}`
-> `softmax`, and a transpose (`^\top`, `^T`, `^\intercal`) of a bold symbol
or a parenthesised group -> `^top` (`sum_(t = 1)^T` keeps its bound). `bb(E)`,
`bb(P)`, `bb(R)` -> `EE`, `PP`, `RR` (Typst built-ins) always. `\vec` stays an
arrow.

## The course's classes

CSS classes of the course's own theme (e.g. `.llm-prompt`) map to functions of
`common/course.typ` in `common/mdx-classes.json`:

```json
{ "llm-prompt": "llm-prompt" }
```

A class neither the engine nor the course knows is kept as a
`// TODO-REVIEW: class …` comment.

Directly, `tools/mdx2typ.py [--src DIR] [--macros FILE] [--notation FILE]
[--classes FILE] [--deck] [--backup DIR] <id>…`, from the course directory
(`SLIDES_SRC`: the `SRC` of the Makefile).

Needs `pandoc` and `uv`; the bibliography must be in sync (`make setup`).

## What becomes what

| MDX | Typst |
|---|---|
| `export const meta = {…}` | `#module-meta(id: …, …)` |
| `<SubSection title="…">` | `== …` |
| `<Slide title="…">` | `=== …` |
| `<Slide className="optional">` | `=== …` + `#slide-type("optional")` |
| `<Todo title="…"/>` | `#todo("…")` |
| `<Definition title="…">`, `<Alert>`, … | `#definition(title: […])[…]`, `#alert[…]`, … |
| `<Comment>` | `#remark[…]` |
| `<Synopsis>` | `#synopsis[…]` |
| `<Citation source="…">` | `#quote(block: true, attribution: […])[…]` |
| `<Columns columns="…">` + `<div>` | `#cols(widths: (…))[…][…]` |
| `<div className="hand">` | `#hand[…]` |
| `<Cite entry="doi://…"/>` | `#reference(<key>)` |
| `<Cite entry="…" inline/>` | `#cite(<key>)` |
| `<Ext href="…">` | a link |
| `<b>`, `<em>`, `<code>`, `<br/>` | `#strong[…]`, `#emph[…]`, `` `…` ``, line break |
| inline `<svg>` | `figures/<id>-<n>.svg` + `#image(…)` |
| `<ul>`, `<ol>` (+ `spaced`, `spaced2x`) | `- …`, `+ …` (`#set list(spacing: …)`) |
| a list with `className="fragment"` items | `#items(…, step(2)[…])` |
| `<dl><dt><dd>` | `/ Term: description` (term list) |
| `<h1>`, `<h2>`, `<h3>` in a slide | `#subhead[…]`, `#subhead(level: 2)[…]` |
| `<Grid columns="…">` | `#cols(widths: (…))[…][…]` (one cell per child) |
| `<Frame title type>`, `<Card>`, `<Algorithm>`, `<Soa>` | `#frame(kind: …, title: […])[…]` |
| `<Focus>`, `<Box>` | `#frag(n)[#focus[…]]`, `#boxed[…]` |
| `<img data-src style={{zoom}}>`, `<Image src origin>` | `#img(path("images/…"), zoom: …, origin: …)` (file copied) |
| `className="fragment"` (`fragment only`) | `#frag(n)[…]` (`#frag(n, only: true)`) |
| `className="hand comment warning positive-aspect …"` | `#hand`, `#comment`, `#warning`, `#pro`, `#con`, `#small`, `#boxed`, … |
| `className="space"`, `space2x` | `#v(1em)`, `#v(2em)` before |
| `<span className="…">` | the same styles, inline |
| `<WikiRef name>`, `<SelfLink href>` | `#wikiref("…")`, `#selflink("…")` |
| `<sup>`, `<sub>`, `<a href>`, `<table>` | `#super`, `#sub`, a link, `#table` |
| `{/* comment */}` | `// comment` |
| `$…$` (LaTeX) | `$…$` (Typst maths) |
| tables | `#table(…)` |

`<Cite>` entries are matched against `lib/refs.bib` by DOI (`doi://…`) or
Zotero key (`zotero://select/library/items/…`); an unknown entry stops the
conversion.

## What is left to do by hand

The script prints `unconverted JSX: […]` for components it does not know.
Typically:

- **React components** (animations, plots): write a widget (see
  [widgets](widgets.md)) and an `#interactive(…)` slot with a PDF fallback;
- **fragments** of other components (`<Fragment>`): `#frag(n)[…]` (see
  [authoring](authoring.md#steps));
- **overflow**: an MDX deck has the same height budget (700 px ≈ the Typst
  page), but its hidden fragments too keep their space — a slide that only
  fitted thanks to `fragment only` or a scrolling image needs trimming;
- **layout tweaks** (custom CSS, sizes): Typst `#v`, `#box`, `#text(size: …)`;
- slide-app `className="todo"` blocks come out as `// TODO-REVIEW` groups.

Then `make check` (overflow!), and look at every slide in `make serve`.

## Afterwards

Add the module to a deck (`#include "/modules/<id>/<id>.typ"`) and compare
`make outline` with the MDX deck's.
