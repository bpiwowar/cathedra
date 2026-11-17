// Morphing between the steps of a figure (web only; see ../docs/figures.md).
//
// `#morph("id", body)` names a part of a figure that changes from one step
// page to the next: in the browser, a part with the same id on two
// consecutive pages of a slide moves (and resizes) from its first place to
// its second, a part on one page only fades in or out, and the rest of the
// page cross-fades. The PDF and the handout are unchanged.
//
// `body` is Typst content (`#morph("x")[…]`) or CeTZ elements
// (`morph("x", { rect(…); content(…) })` inside a `cetz.canvas`); in CeTZ,
// the names of the elements inside stay visible outside, as if there were no
// `morph`. An id is unique on a page (two parts with the same id merge into
// one box).
//
// How: on the web, each part records the corners of its box on the page
// (`<morph>` metadata), build.mjs writes them to morph.json, and
// src/morph.ts animates crops of the rendered pages.
#import "@preview/cetz:0.5.3"

#let _is-web = sys.inputs.at("target", default: "print") == "web"

// A zero-size marker recording its place on the page.
#let _marker(id) = box(width: 0pt, height: 0pt, context [#metadata((
    id: id,
    page: here().page(),
    x: here().position().x / 1pt,
    y: here().position().y / 1pt,
  ))<morph>])

// A part of a figure that morphs between steps, with a stable `id` (a string).
#let morph(id, body) = {
  assert(type(id) == str, message: "morph: the id is a string")
  if type(body) == array or type(body) == function {
    // CeTZ elements: processed in the current context (names leak out, as
    // without a group), then two markers at the corners of their bounds
    if not _is-web { return body }
    (
      ctx => {
        let (ctx: ctx, bounds, drawables) = cetz.process.many(ctx, cetz.util.resolve-body(ctx, body))
        if bounds != none {
          for p in (bounds.low, bounds.high) {
            let d = cetz.drawable.content(p, 0, 0, (), _marker(id))
            drawables.push(cetz.drawable.apply-tags(d, cetz.drawable.TAG.no-bounds))
          }
        }
        (ctx: ctx, drawables: drawables)
      },
    )
  } else {
    if not _is-web { return body }
    box({
      place(top + left, _marker(id))
      place(bottom + right, _marker(id))
      body
    })
  }
}
