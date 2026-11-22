# Quick reference

What you reach for while writing a slide. **/** searches every page; the
[API index](api.md) has every function with its parameters.

## Slides

| Markup | |
|---|---|
| `= Title` | a section (deck only), with its section slide |
| `== Title` | a sub-section, first line of a module |
| `=== Title` | a slide; `===` alone: one more slide, `Title (2)` |
| `#allow-breaks[…]` | a slide that goes on to more pages |
| `#sidebar[side][main]` | a grey column with the title on the left |
| `#synopsis[…]`, `#module-meta(minutes: 10, …)` | for the outline and the index, never shown |
| `#slide-type("optional")`, `#todo("…")` | [slide types and todo markers](slide-types.md) |

More: [writing slides](authoring.md).

## Steps

```typst
#pause                                  // the rest on the next step
#only(3)[only on step 3]
#uncover("2-")[from step 2 on]
#frag(2)[#definition[…]]                // nests: steps inside are counted
#steps("frame", "detail")               // named steps…
#frag("detail", only: true)[…]          // … used by name
#items([first], step(3)[at step 3])     // a list that keeps its place
```

More: [steps](authoring.md#steps).

## Blocks and layout

```typst
#definition(title: [Eliteness])[A document is *elite* if …]
#alert[Do not tune $k_1$ on the test set.]
#cols[left][right]                      // no space before the [ ]
#cols(widths: (1fr, 2fr), align: horizon)[narrow][wide]
#hand[A take-home remark]
#codeframe(title: [BM25])[```py …```]
#subhead[A heading inside a slide]
```

Kinds: `definition`, `observation`, `alert`, `idea`, `remark`, `goal`,
`motivation`, `question`, `problem`, `solution`, `theorem`, `example`, `task`,
`summary`, `hypothesis`, `exercise`. More: [components](components.md).

## Images and figures

```typst
#img(path("images/x.webp"), zoom: 0.6, center: true)
#img(path("images/plot.svg"), vh: 50%)  // half the page's height
#svg-steps(path("images/x.svg"), reveal: (".part": 2))
#overlay(img(…), circle-at(x: 30%, y: 40%, step: 2))
#cells((1, -2, 0, 1))                   // a coloured vector
```

More: [images](images.md), [figures](figures.md) (figures in steps,
morphing, handouts).

## References, annotations, details

```typst
#reference(<Key>)                       // full reference, end of slide
#cite(<Key>)                            // inline
#mark("kl", $beta "KL"$)  #annot("kl", step: 2)[KL penalty]
#details-link("flash")[How it works]    // to "in detail" slides
#interactive("wand", height: 9cm)       // a live widget
```

More: [citations](citations.md), [annotations](annotations.md),
[in detail](details.md), [widgets](widgets.md).

## Everything else

[Templates](templates.md) · [setting up a course](course.md) ·
[building](building.md) · [the viewer](viewer.md) (keys) ·
[upgrading](upgrading.md) · [about cathedra](../README.md) (all the pages)
