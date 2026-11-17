# "In detail" slides

Depth on demand: a slide links to a group of in-depth slides kept in an
appendix at the end of the deck. Follow the link when the room wants more,
and come back to where the talk was, at the same step. The group is written
**next to the slide it explains**, not at the end of the file.

## Authoring

```typst
=== Exact attention, made fast: FlashAttention

Never materialise $S = Q K^top$ in memory: compute attention block by block.

#details-link("flash")[How it works: tiling and online softmax]

#details("flash", title: [FlashAttention])[
  === Why attention is memory-bound
  …

  === Tiling and online softmax
  …
]
```

- `#details(id, title: […])[slides…]` lays out nothing where it is written.
  The template collects every group of the deck (in document order, a
  group's own groups right after it) and lays them out after the last slide,
  in a section titled *In detail* (*Compléments* when the template's `lang`
  is `"fr"`; `academic(details-title: […])` to change it), each group behind
  a title card (its `title`).
- `#details-link(id)[text]`: a link to the group's title card (an arrow in
  front). Several slides may link to the same group; a group may hold links
  of its own, and groups of its own.
- A group may be a whole module: `#details("archi", title: […])[#include "…"]`.
- The headings inside a group may be indented (the outline finds them).
- The appendix is a Touying appendix: its slides keep their numbers, but the
  total (`n / total` in the footer) is that of the talk.

## In the PDF

The link goes to the group's title card. The footer of every slide of a
group has a *Back to slide n* link to the first slide linking to the group.

## In the browser

| Action | Effect |
|---|---|
| a click on the link, or **I** | open the group (the slide's group; a picker if it links to several) |
| → ↓ space… inside the group | its steps and slides; at its last slide they stop ("End of the details") |
| ← ↑ at its first slide | stop too: navigation never leaves a group by itself |
| **I**, **Esc**, or the footer's *Back* link | back to the slide and step the group was opened from |
| space / → at the end of the talk | stop ("End of the talk"): the talk never walks into the appendix |

Groups nest: going back unwinds one level at a time. Opened without a link
(reload, the outline **T**, the overview, an address), **Esc** goes to the
slide linking to the group (a picker when there are several). Going back to
the talk by other means ends the digression. A group's slides have a violet
bar on the left; the structure browser shows them as the *in detail* type
(🔍, not timed).

Implementation: `#details`, `collect-details`, `details-appendix`,
`details-link`, `details-back` in `lib/slides.typ` (the page markers carry
the group: `details`); the outline (the groups and the slides linking
to them: `outline.details`); `src/details.ts` (the viewer).
