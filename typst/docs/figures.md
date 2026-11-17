# Figures

Figures are drawn in Typst — CeTZ (`cetz`, imported by `lib/slides.typ`),
fletcher, or plain boxes and grids — not in React. A figure that changes with
the steps of its slide is a function of the current step.

## A figure in steps

```typst
=== Predicting the next word
#steps("input", "scores", "pick")

#import "figures/predict-next.typ": predict-next
#align(center, at-step(predict-next))
#v(1fr)
#step-captions(
  input: [shown at step "input"],
  scores: [shown at step "scores"],
  pick: [shown at step "pick"],
)
```

- `#steps("a", "b", …)`: the slide's steps, named. Step 1 is the slide as it
  opens, the names are the steps after it, in order (pages in the PDF,
  fragments on the web). Adding or moving a step is only a change of this
  list: what refers to the names follows. Numbered steps need no
  declaration (their number is found from `#frag`, `#step-captions`…), but
  a figure drawn by `#at-step` alone, which nothing else counts, needs
  `#steps(n)`.
- `#at-step(k => …)`: content drawn for the current step `k` (a number, 1 to
  n); compare it with `step-no("name")`: `if k >= step-no("scores") { … }`.
- `#step-captions(name: […], …)`: one caption per named step, in the same
  place (or, in order, `#step-captions([…], […])`: from step 2 on).
- `#frag("name")[…]`, `step("name")[…]` in `#items`: content from that step on.

A name that `#steps` does not declare stops the compilation with the list of
the slide's steps. Names are used as argument names in `#step-captions`:
letters, digits and `-`.

In the figure, draw **everything at fixed coordinates** and add or change parts
with `k`. Also draw an invisible rectangle covering the last step's extent
(`rect(…, stroke: none)`), so that the figure does not move or recentre from
one step to the next. See the LLM course's `modules/lecture-1/figures/` for
examples.

## Morphing between steps (web)

By default a step page replaces the previous one at once. Name the parts of a
figure with `morph` and the web viewer animates the step change instead:

```typst
// CeTZ: inside the canvas, around one or more elements
morph("block1", rect((0, 0), (4, 1), name: "b"))
morph("block1-label", content("b.center")[Decoder])
line("b.south", (2, -1))      // names inside a morph stay visible outside

// plain Typst content
#morph("total")[$sum_i x_i$]
```

- A part with the same id on two consecutive step pages of a slide **moves**
  from its box on the first to its box on the second, as a whole (FLIP: one
  transform per part, never a tween of its coordinates). Same size (within
  0.5pt or 1%): translation only, the new picture fading in over the old
  one. Another size: translation + scale, the two pictures cross-fading
  around the middle of the move, so that each is shown while it is the less
  stretched one.
- A part on one page only fades in or out; everything that is not a part
  (arrows, captions…) cross-fades, quickly.
- Ids are per slide; an id appears once per page (twice: the union of the
  boxes). A part inside another (a label in its frame) is taken out of the
  frame: give a frame and its text separate ids, so that the frame
  may scale while the text only moves (`modules/lecture-1/figures/encoder.typ`).
- What changes shape (a vertical vector becoming horizontal) reads better as
  two ids, which fade, than as one, which would be squashed.
- A slide without parts, a jump of several steps, a page not mounted yet and
  `prefers-reduced-motion` keep the instant change. The PDF and the handout
  are unchanged (`morph` is its body there).

How: on the web, a part records its box on the page (`<morph>` metadata,
`lib/morph.typ`), and `build.mjs` writes these boxes to `morph.json`.
`src/morph.ts` follows the steps, `src/morph-svg.ts` builds the transition
from the pages' SVG (see [the viewer](viewer.md#how-the-pages-are-shown)),
with copies of their elements, no pixels:
- an element belongs to the smallest part whose box (padded) holds it;
- each part is animated as a whole over the rest of the pages;
- what is on both pages at the same place stays still, the rest of each page
  fades (quickly), so a line crossing a part's box stays visible;
- the real page is shown when the animation ends.

## Handouts

`make handout` (`--input handout=1`) keeps the last step of each slide:
`at-step` gets the last `k`, `step-captions` lists all the captions (small, in
two columns). When the last step does not tell the whole story, test
`is-handout` and draw something else (e.g. two steps side by side), scaled
down if needed: `scale(75%, reflow: true, …)`.

## Coloured vectors and matrices (`lib/figures.typ`)

Palettes in OKLCH:

```typst
#cells((1, -2, 0, 1))                         // a row of cells, diverging palette
#cells(v, vertical: true, palette: "greens", range: 2, size: 0.4cm)
#cells(v, labels: true)                       // the values in the cells
#cells(v, fade: true)                         // pale (what is not used)
#matrix-cells(((1, 0), (0, 1)), palette: "blues")
```

Palettes: `diverging` (blue ← white → red), `greens`, `oranges`, `violets`,
`yellows`, `blues`. A palette is a function `(value, range) -> colour`; being
stored in a dictionary, it is called as `(palettes.greens)(v, r)` (Typst does
not call a dictionary field as a method).

## Data

A figure that shows computed values (activations, a graph layout, a training
run) reads a small JSON next to it (`json("data/x.json")`), written once by a
script of the course (e.g. a uv script in `tools/`, with fixed seeds). Do not
load multi-megabyte files from Typst.
