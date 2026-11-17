# Writing slides

## Decks and modules

A **deck** (`lectures/<id>.typ`) composes modules and adds nothing but the
overview and the wrap-up:

```typst
#import "/common/course.typ": *

#synopsis[What the lecture covers (index page, outline).]

#show: course-theme.with(config-info(
  title: [Foundations — Models & Efficient Lexical Retrieval],
  author: [Benjamin Piwowarski],
  date: [Lecture 1],
))

#title-slide()

= Lexical ranking models

#include "/modules/vector-space/vector-space.typ"
#include "/modules/bm25/bm25.typ"
```

A **module** (`modules/<topic>/<topic>.typ`) is self-contained: its own
figures, its metadata, and it starts with a sub-section:

```typst
#import "/common/course.typ": *

#module-meta(
  id: "bm25",
  title: "Eliteness, 2-Poisson and BM25",
  minutes: 14,
  prereqs: ("prob-foundations",),
  practicals: ("ranking-models",),
  sources: ("Robertson & Zaragoza 2009",),
)

== BM25

#synopsis[From eliteness to BM25 …]

=== Eliteness: a hidden variable

…
```

`course-theme` and `title-slide` come from the course's template
([templates](templates.md)). Paths are root-absolute (`/common/…`,
`/modules/…`); a module's own files are relative
(`#image("figures/bm25-1.svg")`).

## Headings

| Markup | Where | Gives |
|---|---|---|
| `= Title` | deck only | a main section, with its section slide |
| `== Title` | first line of a module | a sub-section, with its sub-section slide |
| `=== Title` | anywhere | one slide |
| `===` (empty) | after a `=== Title` slide | one more slide, titled `Title (2)`, `Title (3)`… |

Everything until the next heading belongs to the slide. Do not write `---` at
the top level: Touying reads it as a slide break (use `—`).
`make space` puts the canonical blank lines between slides.

The title above a slide (and in a `#sidebar`) is `#slide-title()`: a
template other than `academic` calls it too.

## Steps

Touying's animation commands work as usual; each step is one PDF page, and in
the browser every page after the first is a Reveal fragment:

```typst
=== A slide in three steps

First point
#pause
Second point
#only(3)[Only on the third step]
#uncover("2-")[From the second step on]
```

Touying's `#uncover` cannot hold another one. Steps that nest (a step inside
a frame that is a step, a list whose items appear one by one inside a column)
use the engine's `#frag`:

```typst
=== Nested steps
#frag(2)[#definition(title: [Later])[
  #items([shown with the frame], step(3)[one step later])
]]
#frag(3, only: true)[only on step 3]
```

The number of steps (pages) is found by itself, from what the slide uses:
`#pause`, `#only`, `#uncover`, `#frag`, `step(n)` in `#items`, `#annot(step:,
until:)`, `#svg-steps`, `#overlay` shapes, `#step-captions`, `#interactive`'s
`snapshots`. `#steps(n)` is still needed, as a minimum, when nothing names
the last steps:

- a figure drawn by `#at-step(k => …)` alone;
- a step function inside a `context`, a `layout` or a CeTZ canvas (Touying
  cannot look inside them; the frames of the engine, `#definition` and the
  others, are seen through). A step the slide does not reach then stops the
  compilation, asking for `#steps(n)`.

A component of your own that lays its body out in a `layout` or a `context`
makes its steps visible with `step-marks(body)`:
`#let my-box(body) = { step-marks(body); layout(size => … body …) }`.

Steps can be named, so that adding one does not shift the others: step 1 is
the slide as it opens, the names follow in order.

```typst
=== Named steps
#steps("frame", "detail")

#frag("frame")[#definition(title: [Later])[
  #items([shown with the frame], step("detail")[one step later])
]]
#frag("detail", only: true)[only on the last step]
```

Figures and captions take the names too: see [figures](figures.md#a-figure-in-steps).

## Metadata (never rendered)

- `#module-meta(id:, title:, minutes:, prereqs:, practicals:, sources:)`:
  `minutes` is what `make outline` adds up against the `target` of
  `course.yaml`.
- `#synopsis[…]`: what a section covers, for the outline and the index.
- `#slide-type("optional")`, `#todo("…")`: see
  [slide types](slide-types.md).

## Web or print only

`#web[…]` and `#print[…]` keep content for one output: the web build compiles
with `--input target=web`, anything else is the printable PDF.

## Maths

Typst maths (`$tf(t, d) dot idf(t)$`), with the notation the course defines
in `common/course.typ` (see [setting up a course](course.md)).
