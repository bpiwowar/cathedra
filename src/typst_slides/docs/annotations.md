# Element annotations

Frame a part of the slide (a term of a formula, a few words) and explain it
in a label joined to it by a dashed curve, from a given step on. The Typst
version of slide-app's `<ElementAnnotation>`. Typst draws everything (on the
page foreground), so the web deck and the PDF show the same thing.

```typst
=== GRPO loss
#steps("exp", "kl")

#mark("loss", $ cal(L) = - mark("exp", bb(E)) [ … ] + #mark("kl", $beta "KL"(pi_theta || pi_"ref")$) $)

#annot("exp", step: "exp", color: green, avoid: "loss")[Expectation over prompts]
#annot("kl", step: "kl", color: red, avoid: "loss")[KL penalty keeps the policy close to the reference]
```

## The target: `#mark`

`#mark("id", body)` renders `body` unchanged and records where it is on the
page. The id names it for `annot` (and `avoid`), on the slide.

- text: `#mark("adv")[group-relative advantage]` (in a box: it does not break
  across lines);
- in maths, `mark("exp", bb(E))` (maths arguments), or an inline formula
  `#mark("kl", $beta "KL"(…)$)`. Inside a display formula a marked part keeps
  the display style (fractions, limits of sums);
- a whole display formula, `#mark("loss", $ … $)`: usually an `avoid` zone;
- block content (a heading and a list, a term list's description, a frame) with
  `block: true`: `#mark("process", block: true)[#subhead[…] + …]`; the block
  is as wide as its content.

The frame is drawn around the box the body is laid out in (its corners are
recorded where Typst puts them), extended to the ink of descenders and deep
subscripts (an inline box stops at the baseline), a few points out.

## The label: `#annot`

`#annot("id", …)[label]`, anywhere on the slide (it takes no room where it is
written):

| Argument | Default | |
|---|---|---|
| `step` | `1` | the step it appears on: a number or a name of `#steps`, 1 = from the start |
| `only` | `false` | shown on that step only (slide-app's `exclusive`) |
| `until` | `none` | the step it disappears on (a number or a name): for a block that appears later under the labels |
| `color` | `#6366f1` | the frame around the target, the label's edge, the curve |
| `position` | `auto` | `"above"` or `"below"` the target; `auto`: the side with more room (below when `avoid` is given) |
| `avoid` | the target | an anchor id, or an array of them, the label keeps clear of (their common box) |
| `width` | `auto` | the label's width: a length, or a % of the page width; `auto`: its natural width, at most the size's maximum (35% of the page for `md`) |
| `dx`, `dy` | `none` | pin the label: its top-left corner relative to the target's top-left one (shift-O writes them) |
| `size` | `"md"` | `"sm"`, `"md"`, `"lg"`: text size and maximum width |
| `border` | `true` | `false`: no frame around the target |
| `id` | `none` | tells apart two annotations of the same target (shift-O needs it) |
| `handout` | `auto` | in a handout: `true` shown, `false` not, `auto` the deck setting |

Give the step with `step:`, not by wrapping the annotation in `#frag`: hidden
content is still laid out, so an annotation inside a hidden `#frag` would show.

## Placement

As in slide-app: a label goes above or below its target (or its `avoid` zone),
left-aligned with the target. The labels of a step are then taken from left to
right, and each one that overlaps one before it is moved past it, above or
below, and kept inside the page. A pinned label (`dx` / `dy`; one of them is
enough, the other then stays automatic) is left where it is. The other
labels keep clear of it.

## Printed PDF and handouts

The printed PDF shows on each step page the annotations shown so far, as the
web deck does. A handout (`--input handout=1`) has one page per slide, its
last step. What it shows is a setting of the deck, or of the course:

- `"all"` (default): every annotation of the slide, whatever its step, `only:`
  ones included, except those an `until:` ends by the last step;
- `"steps"`: those of the last step (an `only:` annotation of an earlier step
  is left out);
- `"none"`: none.

An annotation's `handout: true` / `false` overrides it, for example to leave
out one of several `only:` annotations that would crowd the handout page.

```typst
// a deck
#show: course-theme.with(config-info(…), annot-config(handout: "none"))
// the whole course (common/course.typ)
#let (theme: course-theme, title-slide: title-slide) = academic(…, annotations: (handout: "steps"))
```

The deck's `annot-config` replaces the course's settings. A handout does not
spread the annotations of a crowded slide over several pages.

## Moving a label: shift-O (dev server)

In the dev server (`make serve`), **shift-O** outlines the labels of the step
shown. Hover one (or Tab to it), then press Enter or click it. Drag it into
place; the handle on its right edge sets its width (arrows nudge it, by 10 with
shift; + and - change the width). Enter writes `dx:`, `dy:` (and `width:` when
it changed) on the `#annot` call in the source. The deck recompiles and the
label stays where you put it. Esc cancels at any stage, with nothing written.

The call is found by its key (the target id, or `id:`) in the lines of the
slide, else in the whole file. Two annotations with the same key on one slide
need an `id:`; the editor says so. The file is written on disk: save your
editor's buffer first.

## Other templates

The `academic` template applies the two pieces the annotations need. Another
template, or a deck that sets its own page foreground, adds them itself:

```typst
show: annot-rules                                // display style in marked maths
config-page(foreground: annot-layer())           // draws the annotations
```

`annot-layer(defaults: (handout: "all"))` takes the settings.

## Limits

- A label is measured with its citations (`#reference`) replaced by a text
  of a usual length (measuring a real one keeps the document from
  converging), so a label holding a long reference may be placed as if it
  were a line shorter or taller. Each label is also laid out once, hidden, in
  the slide, so that its citations reach the bibliography.
- Targets are on the page as Typst lays it out. A `mark` inside something
  scaled or rotated afterwards is framed at its unscaled place.
- A marked text does not break across lines. A marked part of a formula is a
  box, so the spacing around it can differ slightly (e.g. a marked operator).
- The labels are part of the page: on the web they cannot be selected
  apart from the page, and shift-O drags a copy of that part of the page.
