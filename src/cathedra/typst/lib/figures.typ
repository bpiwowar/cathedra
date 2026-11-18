// Figure vocabulary: coloured vectors and matrices, for figures drawn in
// Typst — plain layout or CeTZ (`content(…, cells(…))`).
//
// A figure that changes with the steps of its slide is a function of the
// current step: `#at-step(k => …)` (lib/slides.typ) draws it, everything at
// fixed places, so that nothing moves from one step to the next; a handout
// gets the last step.

// ---------------------------------------------------------------- palettes
// value in [-range, range] (sequential ones: [0, range]) -> colour, in OKLCH
// (mid-tones stay neutral).
#let _lerp(a, b, t) = a + (b - a) * t
#let _seq(lo, hi, c-lo, c-hi, hue) = (v, range) => {
  let t = calc.clamp(v / range, 0, 1)
  oklch(_lerp(lo, hi, t) * 100%, _lerp(c-lo, c-hi, t), hue * 1deg)
}
#let palettes = (
  // blue <- white -> red; 0 is pure white
  diverging: (v, range) => {
    let t = calc.clamp(v / range, -1, 1)
    let a = calc.abs(t)
    oklch(_lerp(1.0, 0.62, a) * 100%, _lerp(0.0, 0.18, a), if t < 0 { 240deg } else { 25deg })
  },
  greens: _seq(0.95, 0.55, 0.02, 0.16, 150),
  oranges: _seq(0.95, 0.65, 0.02, 0.18, 60),
  violets: _seq(0.96, 0.58, 0.02, 0.18, 300),
  yellows: _seq(0.97, 0.78, 0.02, 0.18, 100),
  blues: (v, range) => _seq(0.95, 0.55, 0.02, 0.16, 250)(calc.abs(v), range),
)

// The largest absolute value (1 if all are ~0).
#let auto-range(values) = {
  let m = calc.max(..values.map(calc.abs))
  if m < 1e-6 { 1 } else { m }
}

// ----------------------------------------------------------------- fitting
// `body` scaled to fit the available space (as `layout` gives it), its
// aspect ratio kept; at most `max` (100%: never enlarged). In a block of
// height 1fr, a figure takes what the rest of the slide leaves
// (`step-figure`, lib/slides.typ).
#let fig-fit(body, max: 150%) = layout(size => {
  let m = measure(body)
  // an empty figure, or a measuring pass (Touying): as is
  if m.width == 0pt or m.height == 0pt { return body }
  let r = calc.min(max / 100%, size.width / m.width, size.height / m.height)
  if r == 1 { body } else { scale(r * 100%, reflow: true, body) }
})

// ------------------------------------------------------------------- cells
// A vector as a row (or column) of coloured cells.
// - palette: a name of `palettes` or a function (value, range) -> colour
// - range: auto = the largest absolute value
// - labels: show the values in the cells (true, or a function value -> content)
// - fade: drawn pale (e.g. what is not used)
#let cells(
  values,
  palette: "diverging",
  range: auto,
  size: 0.45cm,
  gap: 1pt,
  vertical: false,
  labels: false,
  fade: false,
  stroke: 0.5pt + luma(150),
) = {
  let colour = if type(palette) == str { palettes.at(palette) } else { palette }
  let r = if range == auto { auto-range(values) } else { range }
  let cell(v) = box(
    width: size,
    height: size,
    fill: if fade { colour(v, r).transparentize(65%) } else { colour(v, r) },
    stroke: if fade { stroke.paint.transparentize(65%) + stroke.thickness } else { stroke },
    align(center + horizon, if labels == false { none } else {
      text(size: size * 0.5, if labels == true { str(v) } else { labels(v) })
    }),
  )
  if vertical {
    stack(dir: ttb, spacing: gap, ..values.map(cell))
  } else {
    stack(dir: ltr, spacing: gap, ..values.map(cell))
  }
}

// A matrix (rows of values) as a grid of cells; same options as `cells`.
#let matrix-cells(rows, palette: "diverging", range: auto, size: 0.45cm, gap: 1pt, labels: false, ..args) = {
  let r = if range == auto { auto-range(rows.flatten()) } else { range }
  stack(dir: ttb, spacing: gap, ..rows.map(row => cells(
    row, palette: palette, range: r, size: size, gap: gap, labels: labels, ..args,
  )))
}
