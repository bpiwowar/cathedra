// The components and page markers every deck uses (Touying), whatever its
// template. A course imports it through its own
// common/course.typ, which also configures a template (templates/*.typ).
//
// Authoring model (see ../docs/authoring.md):
//   = Main section        lecture file only; new-section slide
//   == Sub section        first line of a module; new-subsection slide
//   === Slide title       one slide (`#pause`, `#only`… for steps)
//   #synopsis[…]          metadata for the outline, never rendered
//   #module-meta(…)       module metadata (title, minutes, prereqs…)
#import "@preview/touying:0.8.0": *
#import "@preview/cetz:0.5.3"
#import "figures.typ": *
#import "morph.typ": morph

/// The engine's API version (VERSION, docs/upgrading.md): templates check it
/// (`assert-api`).
#let api-version = 4

/// Fails, saying so, when the engine's API version is not in
/// [`min`, `before`): a template (or a course) states the versions it works
/// with, e.g. `#assert-api(3, 4, who: "cathedra-academic 1.0.0")`.
#let assert-api(min, before, who: "this template") = assert(
  api-version >= min and api-version < before,
  message: who + " needs the cathedra API >=" + str(min) + ", <" + str(before)
    + "; this engine has API " + str(api-version)
    + " (update the template, or the engine: docs/upgrading.md)",
)

// ------------------------------------------------------------ course data
/// What the course's tools generate, given by the course (its
/// common/course.typ reads the files and passes them to the template, e.g.
/// `academic(data: …)`, which calls `course-setup` at the start of each deck);
/// the engine reads no course file itself. All of it is optional: the course
/// reads these (gitignored) files only when cathedra compiles
/// (`generated`, below), so that plain `typst compile` works from a clone.
/// - ref-links: bib key → {zotero, doi, url}, the links of `#reference`
///   (lib/refs-links.json, `cathedra sync`)
/// - widget-shots: slot key → "/.cache/widgets/<hash>.png", the widgets'
///   pictures for print (.cache/widgets/manifest.json, `cathedra snapshots`)
/// (`image-cache`, API 3, is accepted and ignored: fetched images are files of
/// the course since API 4, docs/images.md)
#let course-data = state("cathedra-course-data", (ref-links: (:), widget-shots: (:)))
#let course-setup(ref-links: (:), image-cache: none, widget-shots: (:)) = course-data.update((
  ref-links: ref-links,
  widget-shots: widget-shots,
))

/// Whether cathedra compiles this (`--input cathedra=1`; the former
/// `--input typst-slides=1` too): the course's generated files are then there
/// to read. Plain `typst compile` (and an editor not set up for the course)
/// leaves it false.
#let generated = "1" in ("cathedra", "typst-slides").map(k => sys.inputs.at(k, default: "0"))

/// The engine's citation style (CSL, as bytes): `#bibliography("/main.bib",
/// style: bib-style)`.
#let bib-style = read("../csl/normal.csl", encoding: none)

#let primary = rgb("#252955")
#let accent = rgb("#2933aa")
#let link-color = rgb("#2a76dd")
#let muted = luma(120)

// ------------------------------------------------------------------ icons
/// Font Awesome Free 7 (OFL; fonts installed by `make setup`). `code`: the
/// icon's code point (e.g. 0xf1ea); `solid: false` for the regular style.
#let fa(code, solid: true) = text(
  font: if solid { "Font Awesome 7 Free Solid" } else { "Font Awesome 7 Free" },
  weight: if solid { 900 } else { 400 },
  size: 0.85em,
  str.from-unicode(code),
)
#let icons = (
  definition: (0xf124, true), // location-arrow
  observation: (0xf610, true), // microscope
  alert: (0xf06a, true), // circle-exclamation
  idea: (0xf0eb, true), // lightbulb
  remark: (0xf075, true), // comment
  goal: (0xf140, true), // bullseye
  motivation: (0xf185, false), // sun
  question: (0xf059, true), // circle-question
  problem: (0xf071, true), // triangle-exclamation
  solution: (0xe585, true), // tower-cell
  theorem: (0xf0e3, true), // gavel
  example: (0xe4f3, true), // flask-vial
  task: (0xf0ae, true), // list-check
  summary: (0xf46d, true), // clipboard-list
  hypothesis: (0xf492, true), // vial
  exercise: (0xf12e, true), // puzzle-piece
  code: (0xf121, true), // code
  hand: (0xf0a4, false), // hand-point-right
  warning: (0xf071, true), // triangle-exclamation
  pro: (0xf0fe, false), // square-plus
  con: (0xf146, false), // square-minus
  wikipedia: (0xf266, true), // wikipedia-w (brands: falls back to the W)
)

// ---------------------------------------------------------- page markers
/// Plain text of a piece of content (headings, for the outline).
#let plain(c) = {
  if c == none { "" } else if type(c) == str { c } else if c.func() in (list.item, enum.item) {
    // one item per line, "- " first: the index renders them as a list
    "\n- " + plain(c.body).trim()
  } else if c.has("text") {
    if type(c.text) == str { c.text } else { plain(c.text) }
  } else if c.has("children") { c.children.map(plain).join("", default: "") } else if c.has("body") {
    plain(c.body)
  } else if c.func() == smartquote { if c.double { "\"" } else { "'" } } else if c.func() in (
    [ ].func(),
    linebreak,
  ) { " " } else if c.has("base") { plain(c.base) } else { "" }
}

/// In a `context`: the page of the current `#show: allow-breaks` slide (0 its
/// first page, 1 the next…), none on another slide.
#let break-page() = {
  let p = here().page()
  let starts = query(<break-start>)
  let ends = query(<break-end>)
  for (i, st) in starts.enumerate() {
    let a = st.location().page()
    let b = if i < ends.len() { ends.at(i).location().page() } else { a }
    if a <= p and p <= b { return p - a }
  }
  none
}

// In a `context`: (heading body, n) of the current slide's title, n > 1 on a
// continuation (an empty `===`, a page of an allow-breaks slide); none if none.
#let _slide-title-parts() = {
  let page = here().page()
  let hs = query(heading).filter(h => h.location().page() <= page and h.level <= 3)
  let blank(c) = (
    c == none
      or c == []
      or c == [ ]
      or (c.has("text") and c.text.trim() == "")
      or (c.has("children") and c.children.all(blank))
  )
  if hs == () or hs.last().level != 3 { return none }
  let n = 1
  let i = hs.len() - 1
  while i >= 0 and hs.at(i).level == 3 and blank(hs.at(i).body) {
    n += 1
    i -= 1
  }
  if i < 0 or hs.at(i).level != 3 { return none }
  let k = break-page()
  if k != none { n += k }
  (hs.at(i).body, n)
}

/// Emitted on every page (via the footer): the logical slide this page belongs
/// to, its kind (title, section, subsection, slide) and the headings in force.
/// The web build groups pages with the same `slide` into one Reveal <section>,
/// each extra page becoming a fragment; the outline (tools/outline.mjs) reads
/// the structure from them.
#let page-marker(kind: "slide") = context {
  let h(level) = {
    let x = utils.current-heading(level: level)
    if x == none { none } else { plain(x.body).trim() }
  }
  [#metadata((
      slide: utils.slide-counter.get().first(),
      page: here().page(),
      kind: kind,
      // the page of an allow-breaks slide (0, 1…), none for another slide
      cont: if kind == "slide" { break-page() } else { none },
      h1: h(1),
      h2: if kind == "section" { none } else { h(2) },
      h3: if kind == "slide" {
        let t = _slide-title-parts()
        if t == none { h(3) } else {
          plain(t.at(0)).trim() + if t.at(1) > 1 { " (" + str(t.at(1)) + ")" } else { "" }
        }
      } else { none },
      // the "in detail" group of the page (#details): its id, "" on the
      // appendix's title card, none in the talk
      details: {
        let start = query(<details-start>)
        if start == () or here().page() < start.first().location().page() { none } else {
          let groups = query(selector(<details-group>).before(here()))
          if groups == () { "" } else { groups.last().value.id }
        }
      },
      // the deck's language (the viewer's strings)
      lang: text.lang,
      // the page size in pt (the web viewer's slide size)
      width: page.width / 1pt,
      height: page.height / 1pt,
    ))<page-marker>]
}

// ---------------------------------------------------------------- metadata
#let module-meta(id: none, title: none, minutes: none, prereqs: (), practicals: (), sources: ()) = [#metadata((
    id: id,
    title: title,
    minutes: minutes,
    prereqs: prereqs,
    practicals: practicals,
    sources: sources,
  ))<module-meta>]

/// What a section covers (index page, `make outline`); never shown in the deck.
/// `text` is the plain-text version (outline); `body` keeps the markup.
#let synopsis(body) = [#metadata((text: plain(body), body: body))<synopsis>]

/// Slide types (`#slide-type("optional")`…): anywhere in a slide.
/// Rendered as nothing; the outline and the structure browser badge the slide.
#let slide-type(..names) = [#metadata(names.pos())<slide-type>]

// --------------------------------------------------------------- web parts
/// The same source gives two outputs: `--input target=web` is the PDF behind
/// the browser deck (widgets drawn over it), anything else is the printable PDF.
#let target = sys.inputs.at("target", default: "print")
#let is-web = target == "web"
/// Content for one output only.
/// A handout (`--input handout=1`): one page per slide, its last step.
#let is-handout = sys.inputs.at("handout", default: "0") == "1"
#let web(body) = if is-web { body }
#let print(body) = if not is-web { body }

// ------------------------------------------------------- step counting
/// Touying makes one page per step of a slide, and counts them before the
/// slide is laid out, from the `#pause` / `#uncover` / `#only` it finds in the
/// slide's content. The step functions below (`#frag`, `#annot(step:)`…) read
/// the current step later, in `context`, where Touying cannot see them: each
/// also leaves an empty `#uncover("n-")` where it is written, so that the
/// slide gets its n pages without a `#steps(n)`.
///
/// `step-mark(2, "ffn", 4)`: the mark for the largest number (names are
/// counted by their `#steps("…")`); nothing for step 1.
#let step-mark(..ns) = {
  let ns = ns.pos().filter(n => type(n) == int)
  let n = calc.max(1, ..ns)
  // Touying's own `uncover(…)` mark, without the label that makes a mark
  // Touying does not reach (in a container it does not walk) an error: there
  // it is ignored, and `uses-step` checks that the slide has its steps
  if n > 1 { metadata(uncover(str(n) + "-", []).value) }
}
// The last step Touying counts in `c` (1 if none): its `#uncover` /
// `#only` marks, at any depth.
#let _last-step(c) = {
  if type(c) == array { return calc.max(1, ..c.map(_last-step)) }
  if type(c) == arguments { return _last-step(c.pos() + c.named().values()) }
  if type(c) != content { return 1 }
  if c.func() == metadata {
    let v = c.value
    if type(v) != dictionary or v.at("kind", default: none) != "touying-fn-wrapper" { return 1 }
    let n = v.at("last-subslide", default: none)
    return calc.max(if type(n) == int { n } else { 1 }, _last-step(v.at("args", default: ())))
  }
  calc.max(1, ..c.fields().values().map(_last-step))
}
/// A function laying `body` out in a closure (`layout`, `context`) hides its
/// marks from Touying: `step-marks(body)` puts the mark of its last step
/// where Touying sees it (`{ step-marks(body); layout(_ => … body …) }`).
#let step-marks(..bodies) = step-mark(_last-step(bodies.pos()))

// ------------------------------------------------------------------ blocks
/// A titled block: a rounded frame in the accent colour, the title (icon +
/// bold) sitting on the top border. The kinds below are this with their
/// icon: `#definition(title: [T])[body]`, and the same for observation,
/// alert, idea, remark, goal, motivation, question, problem, solution,
/// theorem, example, task, summary, hypothesis, exercise.
/// -> content
#let block-frame(
  /// The icon: a key of `icons` (`"definition"`, `"alert"`…), or `none`.
  /// -> str | none
  kind: none,
  /// On the top border, after the icon (on the first line if too long for it).
  /// -> content | none
  title: none,
  /// The colour of the frame, the icon and the title. -> color
  color: accent,
  /// The icon after the title, not before. -> bool
  icon-right: false,
  /// The content of the block. -> content
  body,
) = {
  let icon = if kind != none and kind in icons {
    let (code, solid) = icons.at(kind)
    text(fill: color, fa(code, solid: solid))
  }
  let label = {
    if icon != none and not icon-right { icon + h(0.3em) }
    if title != none { text(weight: "bold", fill: color, title) }
    if icon != none and icon-right { h(0.3em) + icon }
  }
  let has-label = icon != none or title != none
  // the steps inside, seen by Touying (the body is laid out in a `layout`)
  step-marks(title, body)
  // the label sits on the top border: reserve half its height above the frame
  // (also when the block opens a grid cell, where `above` does not apply)
  block(width: 100%, above: 0.8em, below: 0.8em, breakable: false, inset: (top: if has-label { 0.6em } else { 0pt }), layout(size => {
    let fits = not has-label or measure(label).width < size.width - 1.5em.to-absolute()
    block(
      width: 100%,
      stroke: 1.5pt + color,
      radius: 7pt,
      inset: (x: 0.6em, top: if has-label and fits { 0.9em } else { 0.5em }, bottom: 0.5em),
      {
        // a label too long for the border goes on the first line instead
        if has-label and not fits {
          block(below: 0.4em, {
            if icon != none { icon + h(0.3em) }
            if title != none { text(weight: "bold", fill: color, title) }
          })
        }
        body
      },
    )
    if has-label and fits {
      // centred on the border, whatever the title's size: (cap height) / 2,
      // minus half the stroke
      place(top + left, dx: 0.5em, dy: -measure(label).height / 2 - 0.75pt,
        box(fill: white, inset: (x: 0.25em), label))
    }
  }))
}

/// A definition: a `block-frame` with its icon; `title` on its border.
#let definition(body, title: none) = block-frame(kind: "definition", title: title, body)
/// An observation (icon after the title): a `block-frame` with its icon; `title` on its border.
#let observation(body, title: none) = block-frame(kind: "observation", title: title, icon-right: true, body)
/// A warning: a `block-frame` with its icon; `title` on its border.
#let alert(body, title: none) = block-frame(kind: "alert", title: title, body)
/// An idea: a `block-frame` with its icon; `title` on its border.
#let idea(body, title: none) = block-frame(kind: "idea", title: title, body)
/// A remark: a `block-frame` with its icon; `title` on its border.
#let remark(body, title: none) = block-frame(kind: "remark", title: title, body)
/// A goal: a `block-frame` with its icon; `title` on its border.
#let goal(body, title: none) = block-frame(kind: "goal", title: title, body)
/// A motivation: a `block-frame` with its icon; `title` on its border.
#let motivation(body, title: none) = block-frame(kind: "motivation", title: title, body)
/// A question (icon after the title): a `block-frame` with its icon; `title` on its border.
#let question(body, title: none) = block-frame(kind: "question", title: title, icon-right: true, body)
/// A problem: a `block-frame` with its icon; `title` on its border.
#let problem(body, title: none) = block-frame(kind: "problem", title: title, body)
/// A solution: a `block-frame` with its icon; `title` on its border.
#let solution(body, title: none) = block-frame(kind: "solution", title: title, body)
/// A theorem: a `block-frame` with its icon; `title` on its border.
#let theorem(body, title: none) = block-frame(kind: "theorem", title: title, body)
/// An example: a `block-frame` with its icon; `title` on its border.
#let example(body, title: none) = block-frame(kind: "example", title: title, body)
/// A task: a `block-frame` with its icon; `title` on its border.
#let task(body, title: none) = block-frame(kind: "task", title: title, body)
/// A summary: a `block-frame` with its icon; `title` on its border.
#let summary(body, title: none) = block-frame(kind: "summary", title: title, body)
/// A hypothesis: a `block-frame` with its icon; `title` on its border.
#let hypothesis(body, title: none) = block-frame(kind: "hypothesis", title: title, body)
/// An exercise: a `block-frame` with its icon; `title` on its border.
#let exercise(body, title: none) = block-frame(kind: "exercise", title: title, body)
/// A frame around code: `#codeframe(title: [BM25])[```py …```]`.
#let codeframe(body, title: none) = block-frame(kind: "code", title: title, color: rgb("#2e7d32"), body)

/// A take-home remark, behind a pointing hand. -> content
#let hand(body) = block(above: 0.6em, below: 0.6em, grid(
  columns: (auto, 1fr),
  column-gutter: 0.4em,
  text(fill: accent, fa(icons.hand.at(0), solid: icons.hand.at(1))), body,
))

/// Deprecated: Typst's own `#quote(block: true, attribution: […])` (styled
/// by the template). Kept for older courses: `#citation(source: …)[…]`.
#let citation(body, source: none) = quote(block: true, attribution: source, body)

/// Columns side by side, one content block each:
/// `#cols(widths: (1fr, 2fr))[left][right]`, the blocks right after the
/// parenthesis, with no line break before them.
/// -> content
#let cols(
  /// One width per column: `(1fr, 2fr)`, `(40%, 1fr)`; more blocks than
  /// widths wrap to new rows. `auto`: one equal column per block.
  /// -> array | auto
  widths: auto,
  /// The space between columns. -> length
  gutter: 1.2em,
  /// The alignment of the cells: `top`, `horizon`, `center + horizon`…
  /// -> alignment
  align: top,
  /// The columns' contents. -> content
  ..bodies,
) = {
  let bs = bodies.pos()
  for b in bs {
    if type(b) in (length, fraction, ratio, relative) {
      panic(
        "cols: a column must be content, not " + repr(b) + ". Widths are one array: "
          + "widths: (1fr, 1fr), and the columns follow as [..][..]",
      )
    }
  }
  if type(widths) not in (array, int) and widths != auto {
    panic("cols: widths must be an array, one width per column: widths: (1fr, 2fr)")
  }
  grid(
    columns: if widths == auto { (1fr,) * bs.len() } else { widths },
    column-gutter: gutter,
    row-gutter: 0.8em,
    align: align,
    ..bs,
  )
}

/// The current slide's title: its `===` heading. A slide
/// whose heading is empty (`===` alone) continues the previous one, whose
/// title it shows numbered: `Title (2)`, `Title (3)`…
#let slide-title() = context {
  let t = _slide-title-parts()
  if t == none { none } else if t.at(1) == 1 { t.at(0) } else [#t.at(0) (#t.at(1))]
}

// How a template shows the slide title (a function of the title): the
// title repeated on the pages of a `#show: allow-breaks` slide.
#let _title-block = state("slide-title-block", t => block(below: 0.8em, text(
  size: 1.25em,
  weight: "bold",
  t,
)))
#let set-title-block(f) = _title-block.update(_ => f)

/// An opt-in slide whose content, if it does not fit, goes on to more pages
/// (beamer's `allowframebreaks`), each titled `Title (2)`, `Title (3)`… and
/// shown by the viewer as a slide of its own. The slide's content in it:
///   === A long slide
///   #allow-breaks[
///     …
///   ]
/// No steps (`#pause`…) in such a slide.
#let allow-breaks(body) = touying-set-config((breakable: true), {
  [#metadata(none)<break-start>]
  // (in a grid cell, the title block's spacing below is lost: row-gutter)
  grid(
    columns: (1fr,),
    row-gutter: 0.8em,
    grid.header(repeat: true, context _title-block.get()(slide-title())),
    body,
  )
  [#metadata(none)<break-end>]
})

/// A sidebar slide: a grey column on the left holding the slide title and
/// what goes with it (a sub-heading, the references…), the main content on
/// the right with the whole height of the slide:
///   #sidebar[#reference(<key>)][main content]
/// The template's title above the slide is then left out (`has-sidebar`).
/// -> content
#let sidebar(
  /// The sidebar's width. -> relative
  width: 26%,
  /// The space between the sidebar and the main content. -> length
  gutter: 1em,
  /// The sidebar's background. -> color
  fill: luma(238),
  /// `false` leaves the slide title out of the sidebar. -> bool
  title: true,
  /// The sidebar's content, under the title. -> content
  side,
  /// The main content, on the right. -> content
  body,
) = {
  [#metadata("sidebar")<sidebar-layout>]
  grid(
    columns: (width, 1fr),
    rows: 1fr,
    column-gutter: gutter,
    block(
      width: 100%,
      height: 100%,
      fill: fill,
      inset: (left: 0.7em, right: 0.5em, y: 0.6em),
      stroke: (left: 4pt + accent.lighten(60%)),
      {
        if title {
          block(below: 0.8em, text(size: 1.1em, weight: "bold", fill: primary, slide-title()))
        }
        side
      },
    ),
    body,
  )
}
/// Whether the current page is a sidebar slide (in a `context`).
#let has-sidebar() = query(<sidebar-layout>).any(m => m.location().page() == here().page())

/// Full reference(s), small, at the end of a slide: `#reference(<key>)`. A
/// newspaper icon in front is the link, to the Zotero item in the
/// dev server (`--input dev=1`), else to the DOI, else to the URL (the
/// course data's `ref-links`). In a `context`.
#let dev = sys.inputs.at("dev", default: "0") == "1"
#let ref-url(key) = {
  let l = course-data.get().ref-links.at(str(key), default: (:))
  let pick = if dev { (l.at("zotero", default: none),) } else { () }
  (..pick, l.at("doi", default: none), l.at("url", default: none)).find(u => u != none)
}
#let ref-color = rgb("#000044")
#let reference(..keys) = block(above: 0.9em, text(size: 0.55em, fill: ref-color, style: "italic", context {
  for k in keys.pos() {
    let url = ref-url(k)
    let icon = text(style: "normal", fill: ref-color, fa(0xf1ea, solid: false))
    block(above: 0.25em, below: 0.25em, {
      if url != none { link(url, icon) } else { icon }
      h(0.3em)
      cite(k, form: "full")
    })
  }
}))

// ------------------------------------------------------- inside a slide
/// A heading inside a slide (level 1 to 3, from the largest).
#let subhead(level: 1, body) = block(above: 1em, below: 0.55em, text(
  size: (1.15em, 1.05em, 1em).at(level - 1, default: 1em),
  weight: if level < 3 { "bold" } else { "regular" },
  fill: primary,
  body,
))

/// Steps (Reveal fragments) that nest. Touying's `#uncover` cannot hold
/// another one; `#frag` reads the current step from the page markers instead
/// (the n-th page of a logical slide is its n-th step), so steps can sit in
/// frames, grids and list items at any depth. The number of steps (pages) is
/// found by itself: each step function leaves a mark Touying counts (see
/// `step-mark` above). `#steps(n)` is only needed for steps nothing else
/// names (an `#at-step` figure, a step function inside a `context`, a
/// `layout` or a CeTZ canvas), and `#steps("a", "b")` to name steps.
/// In a handout, a slide's only page is its last step: the largest of
/// `#steps(n)` and the steps its step functions use.
#let current-step() = {
  let s = utils.slide-counter.get().first()
  if is-handout {
    let ns = query(<slide-steps>).filter(m => m.value.slide == s).map(m => m.value.n)
    ns += query(<step-ref>).filter(m => m.value.slide == s).map(m => m.value.n)
    return calc.max(1, ..ns)
  }
  let first = query(<page-marker>).find(m => m.value.slide == s)
  if first == none { 1 } else { here().page() - first.location().page() + 1 }
}
/// Records that the current slide uses step(s) `ns` (numbers, already
/// resolved from names), in the `context` of a step function `fn`: for the
/// handout's last step and, in a talk, to check that the slide reaches them
/// (a step function Touying did not see, inside a `context`, a `layout` or
/// a CeTZ canvas, needs a `#steps(n)`).
#let uses-step(fn, ..ns) = {
  let n = calc.max(1, ..ns.pos().filter(x => x != none))
  if n <= 1 { return }
  let s = utils.slide-counter.get().first()
  if is-handout {
    [#metadata((slide: s, n: n))<step-ref>]
    return
  }
  let pages = query(<page-marker>).filter(m => m.value.slide == s and m.value.kind == "slide").len()
  if pages > 0 and n > pages {
    panic(
      fn + ": step " + str(n) + " is never reached, slide " + str(s) + " has " + str(pages)
        + " step(s). Touying did not see this step (inside a `context`, a `layout` or a CeTZ canvas?): "
        + "give the slide its steps with #steps(" + str(n) + ")",
    )
  }
}
/// The steps of the slide: `#steps(4)`, or named, `#steps("sa", "ffn")`.
/// Step 1 is the slide as it opens; the names are steps 2, 3…, in order, and
/// every function taking a step takes a name too (`#frag("ffn")[…]`): a step
/// inserted later does not shift the others.
#let steps(..args) = {
  let a = args.pos()
  let names = if a.len() == 1 and type(a.first()) == int { () } else { a }
  for x in names {
    if type(x) != str { panic("steps: a number, or names (strings): steps(\"a\", \"b\")") }
  }
  if names.dedup().len() != names.len() { panic("steps: a name is used twice: " + repr(names)) }
  let n = if names == () { a.first() } else { names.len() + 1 }
  uncover(str(n) + "-", [])
  context [#metadata((slide: utils.slide-counter.get().first(), n: n, names: names))<slide-steps>]
}

/// The number of a step of the current slide, from its name (a number is
/// returned as is). Needs `context` (as in `at-step`): `k >= step-no("ffn")`.
#let step-no(name) = {
  if type(name) == int { return name }
  let s = utils.slide-counter.get().first()
  let m = query(<slide-steps>).find(m => m.value.slide == s)
  let names = if m == none { () } else { m.value.at("names", default: ()) }
  let i = names.position(x => x == name)
  if i == none {
    panic("step " + repr(name) + " is not declared on this slide: #steps(" + names.map(repr).join(", ") + ")")
  }
  i + 2
}

/// `body` from step `n` (a number or a name) on, its place kept before; or
/// only on step `n` (no place kept elsewhere) with `only: true`.
#let frag(n, only: false, body) = {
  step-mark(n, _last-step(body))
  context {
    let k = current-step()
    let n = step-no(n)
    uses-step("frag", n)
    if k == n or (k > n and not only) { body } else if not only { hide(body) }
  }
}

/// Content that is a function of the current step (a figure drawn
/// differently at each step): `#at-step(k => …)`, k a number; compare it with
/// `step-no("name")`. In a handout, k is the last step.
#let at-step(f) = context f(current-step())

/// A slot for a live web component (registered under `id` in src/main.tsx),
/// which receives `props`. An animation's steps are Reveal fragments; their
/// number is given by the component (or `steps: n`). The PDF shows `fallback`;
/// the web PDF leaves the slot empty (no stray text under the widget).
/// In print, `make pdf` / `make handout` show a picture of the widget, taken
/// in headless Chromium (`cathedra snapshots`; the course data's
/// `widget-shots`). A picture is of a widget *state*: props added
/// to `props` for it, which the widget reaches (steps shown, epochs trained…)
/// before it calls `onReady` (when registered `async`); a number n is short
/// for `(step: n)`, and `(:)` is the widget as it is (its final step).
/// -> content
#let interactive(
  /// The component's name, as registered in src/main.tsx. -> str
  id,
  /// The slot's width. -> relative
  width: 100%,
  /// The slot's height. -> length
  height: 5cm,
  /// What the component receives. -> dictionary
  props: (:),
  /// The number of steps of the animation (`auto`: as the component says).
  /// -> int | auto
  steps: auto,
  /// What the PDF shows instead of the widget. -> content | none
  fallback: none,
  /// `auto` (a picture of `(:)` when there is no `fallback`), `true` (the
  /// same, even with a fallback), `false` (never a picture), or a state:
  /// `snapshot: (epochs: 50)`.
  /// -> auto | bool | int | dictionary
  snapshot: auto,
  /// One state per step of the slide (in print, one step each), each shown
  /// from that step on: in order, `(0, (epochs: 10), (epochs: 50))` on the
  /// slide's steps 1, 2, 3; or by step name, `("1": 0, ten: (epochs: 10))`
  /// (`"1"`: the unnamed first step). A handout shows the last.
  /// -> array | dictionary | none
  snapshots: none,
) = {
  // in print, the steps of `snapshots` (one per step, or by step), seen by
  // Touying (on the web, the widget has its own steps)
  if not is-web {
    step-mark(
      _last-step(fallback),
      ..if type(snapshots) == array { (snapshots.len(),) } else if type(snapshots) == dictionary {
        snapshots.keys().filter(k => k.match(regex("^\\d+$")) != none).map(int)
      } else { () },
    )
  }
  box(
  width: width,
  height: height,
  // `layout` gives the slot's resolved size (a relative width such as 100%
  // is only known here)
  layout(size => {
    let n-steps = if steps == auto { none } else { steps }
    // the widget steps photographed ("last": the final state), if any
    // a widget state: props for the picture (a number: a step)
    let state(x) = if type(x) == int { (step: x) } else if type(x) == dictionary { x } else {
      panic("interactive: a snapshot state is a number (a step) or props, not " + repr(x))
    }
    let tag(x) = json.encode(state(x), pretty: false)
    // the states photographed: per slide step, one, or none
    let shots = if snapshots != none {
      if type(snapshots) == array { snapshots } else { snapshots.values() }
    } else if snapshot == false or (snapshot == auto and fallback != none) { () } else if (
      snapshot in (auto, true)
    ) { ((:),) } else { (snapshot,) }
    // what the picture depends on (tools/snapshots.mjs)
    let key = (
      id + "|" + json.encode(props, pretty: false) + "|" + repr(n-steps)
        + "|" + str(calc.round(size.width / 1pt, digits: 1)) + "x" + str(calc.round(size.height / 1pt, digits: 1))
    )
    context [#metadata((
        id: id,
        key: key,
        shots: shots.map(x => (tag: tag(x), state: state(x))),
        props: props,
        steps: n-steps,
        page: here().page(),
        x: here().position().x / 1pt,
        y: here().position().y / 1pt,
        w: size.width / 1pt,
        h: size.height / 1pt,
      ))<interactive>]
    if is-web { } else {
      context {
        // (slide step, state)
        let pairs = if snapshots == none { () } else if type(snapshots) == array {
          snapshots.enumerate().map(((i, w)) => (i + 1, w))
        } else {
          snapshots.pairs().map(((k, w)) => (if k.match(regex("^\d+$")) != none { int(k) } else { step-no(k) }, w))
        }
        uses-step("interactive", ..pairs.map(p => p.first()))
        let file = if shots == () { none } else if snapshots != none {
          // the last state reached
          let k = current-step()
          let reached = pairs.filter(p => p.first() <= k).sorted(key: p => p.first())
          let w = if reached == () { pairs.first().last() } else { reached.last().last() }
          course-data.get().widget-shots.at(key + "@" + tag(w), default: none)
        } else { course-data.get().widget-shots.at(key + "@" + tag(shots.first()), default: none) }
        if file != none {
          image(file, width: 100%, height: 100%, fit: "contain")
        } else if fallback == none {
          block(
            width: 100%,
            height: 100%,
            stroke: (paint: luma(200), dash: "dashed"),
            align(center + horizon, text(fill: muted, size: 0.7em)[interactive: #raw(id) (see the web version)]),
          )
        } else { fallback }
      }
    }
  }),
  )
}

/// Work in progress: a note on what is left to do. Marks
/// the slide `todo`; drawn as a red note in the top-right corner, unless
/// compiled with `--input todo=0` (a PDF for the students). On the web the
/// note is an HTML widget (`todo-note`), so M can hide it during the talk.
#let todo(note) = {
  slide-type("todo")
  if is-web {
    place(top + right, dy: -1.2em, float: false, interactive(
      "todo-note",
      width: 14cm,
      height: 1.2em,
      props: (note: plain(note)),
    ))
  } else if sys.inputs.at("todo", default: "1") != "0" {
    place(top + right, dy: -1.2em, float: false, box(
      fill: rgb("#fff0f0"),
      stroke: 0.8pt + rgb("#cc0000"),
      radius: 3pt,
      inset: 0.3em,
      text(size: 0.5em, fill: rgb("#cc0000"))[🚧 #note],
    ))
  }
}

/// One caption per step, in the same place. Named, one per step name:
/// `#step-captions(sa: […], ffn: […])`; or in order, the i-th (from 0) on step
/// `start + i`. A handout lists them all, numbered (small, two columns).
#let step-captions(start: 2, ..captions) = {
  let named = captions.named()
  let cs = captions.pos() + named.values()
  step-mark(_last-step(cs), if named.len() == 0 { start + cs.len() - 1 })
  if is-handout {
    // the steps they cover (the handout's last step)
    context uses-step("step-captions", ..if named.len() > 0 { named.keys().map(step-no) } else {
      (start + cs.len() - 1,)
    })
    block(text(size: 0.7em, columns(2, gutter: 1.5em, enum(tight: true, ..cs))))
  } else if named.len() > 0 {
    context {
      let k = current-step()
      uses-step("step-captions", ..named.keys().map(step-no))
      for (name, c) in named { if step-no(name) == k { c } }
    }
  } else {
    context {
      uses-step("step-captions", start + cs.len() - 1)
      let k = current-step() - start
      if k >= 0 and k < cs.len() { cs.at(k) }
    }
  }
}

/// A step figure, with its captions, taking the rest of the slide: `fig` is
/// a function of the step (as for `at-step`), scaled (`fig-fit`, at most
/// `max`) to the space the captions — and what follows on the slide — leave.
/// On a slide, room is kept for the tallest caption: the figure has the same
/// size at every step. In a handout, the figure shows the last step, above
/// all the captions (two columns). No captions: the figure alone (and what
/// follows the call stays under it).
/// -> content
#let step-figure(
  /// The figure at a step: `k => …`, as for `at-step`. -> function
  fig,
  /// The step of the first caption given in order. -> int
  start: 2,
  /// The alignment of the caption on a slide. -> alignment
  caption-align: left,
  /// The space between the figure and the captions. -> length
  gap: 0.6em,
  /// The largest scale of the figure. -> ratio
  max: 150%,
  /// Content in the bottom-right corner of the figure's area (a mini-map, a
  /// legend…), so it never covers the captions. -> content | none
  corner: none,
  /// As `step-captions`: named by step, or in order from `start`.
  /// -> content
  ..captions,
) = {
  let cs = captions.pos() + captions.named().values()
  block(width: 100%, height: 1fr, {
    align(center + top, context fig-fit(fig(current-step()), max: max))
    if corner != none { place(bottom + right, corner) }
  })
  if cs.len() > 0 {
    v(gap, weak: true)
    let all = step-captions(start: start, ..captions)
    layout(size => if is-handout {
      // measured at the page width, the captions are in one column (of the
      // right width: the height is free); half that height (and a line)
      // holds them in the two columns of `step-captions`
      let h = measure(all, width: size.width).height
      block(width: 100%, height: h / 2 + 1em, all)
    } else {
      let h = calc.max(..cs.map(c => measure(c, width: size.width).height))
      block(width: 100%, height: h, align(caption-align, all))
    })
  }
}

/// A list whose items appear in steps: each item is content, or `step(n)[…]`
/// for one that appears at step n (a number or a name). Unlike a step around a `- item`, a hidden
/// item keeps its place and its marker is hidden with it, so the list does
/// not move when it appears. `numbered`: `true` (1. 2. …), or a function of
/// the number that draws the marker (`circled`).
#let step(n, body) = (when: n, body: body)
#let items(numbered: false, start: 1, depth: 1, spacing: 0.55em, ..its) = {
  let markers = ([•], [‣], [–])
  block(above: 0.8em, below: 0.8em, grid(
    columns: (auto, 1fr),
    column-gutter: 0.5em,
    row-gutter: spacing,
    ..its.pos().enumerate().map(((i, it)) => {
      let (when, body) = if type(it) == dictionary { (it.when, it.body) } else { (none, it) }
      let marker = if type(numbered) == function { numbered(start + i) } else if numbered [#(start + i).] else {
        text(fill: accent, markers.at(calc.min(depth, 3) - 1))
      }
      if when == none { (marker, body) } else { (frag(when, marker), frag(when, body)) }
    }).flatten(),
  ))
}

/// Deprecated: Typst's own term list, `/ Term: description` (styled by the
/// template: the term in bold on its line, the description indented under
/// it). Kept for older courses: `#dt[term]` then `#dd[description]`.
#let dt(above: 0.6em, body) = block(above: above, below: 0.3em, strong(body))
#let dd(body) = pad(left: 1.2em, block(above: 0.3em, below: 0.3em, body))

/// An image: `#img(path("images/x.webp"), zoom: 0.5, center: true)`. Its
/// size is the natural size in pixels (1 px = 1/700 of the page height)
/// times `zoom`, never wider than the space available; an explicit `width`
/// or `height` wins. With `vh` alone (no `vw`, no `width`) or `vw` alone (no
/// `vh`, no `height`), the whole image is scaled, keeping its proportions,
/// and made smaller if it is wider than the space available.
///
/// An image given by `origin:` and missing (`path("images/x.webp")`) is
/// fetched by `cathedra images` into that file, a file of the course
/// (commit it). In a `context`.
/// -> content
#let img(
  /// `path("…")`, relative to the calling file (a plain string would be
  /// looked up next to this file). -> path | str
  path,
  /// The width (`8cm`; a % is of the space available: the column, the
  /// frame…). -> auto | relative
  width: auto,
  /// The height, as `width`. -> auto | relative
  height: auto,
  /// The height as a fraction of the page's (as in CSS): `vh: 50%` is half
  /// the page's height, wherever the image is. -> ratio | none
  vh: none,
  /// The width as a fraction of the page's. -> ratio | none
  vw: none,
  /// A factor on the natural size. -> int | float
  zoom: 1,
  /// Centred horizontally. -> bool
  center: false,
  /// Where the image comes from (a URL): a link in the dev server, and what
  /// `cathedra images` fetches. -> str | none
  origin: none,
  /// Ignored (API 3). -> none
  filename: none,
  /// The size cap of the copy `cathedra images` fetches (`"800x"`); ignored
  /// by `#img` itself. -> str | none
  resize: none,
) = context {
  // `vh` alone (no `vw` / `width`) or `vw` alone (no `vh` / `height`): that
  // size, the other side following the image's proportions, and the whole
  // image scaled down if it is wider than the space available (never cropped)
  let only-vh = vh != none and vw == none and width == auto
  let only-vw = vw != none and vh == none and height == auto
  let body = if only-vh or only-vw {
    box(layout(size => context {
      let natural = measure(image(path))
      let ratio = natural.width / natural.height
      let (w, h) = if only-vh {
        let h = vh / 100% * page.height
        (h * ratio, h)
      } else {
        let w = vw / 100% * page.width
        (w, w / ratio)
      }
      if w > size.width {
        w = size.width
        h = w / ratio
      }
      image(path, width: w, height: h)
    }))
  } else if vh != none or vw != none {
    context image(
      path,
      width: if vw != none { vw / 100% * page.width } else { width },
      height: if vh != none { vh / 100% * page.height } else { height },
    )
  } else if width != auto or height != auto {
    image(path, width: width, height: height)
  } else {
    // in a box: `layout` alone is a block, which would put each image on its
    // own line (`#img(a) #img(b)` side by side, as with an explicit size)
    box(layout(size => context {
      let natural = measure(image(path))
      let px = page.height / 700
      // Typst reads an image without resolution as 72 dpi: 1 px = 1 pt
      let w = calc.min(natural.width / 1pt * px * zoom, size.width)
      image(path, width: w)
    }))
  }
  if origin != none and dev { body = link(origin, body) }
  if center { align(std.center, body) } else { body }
}

/// An SVG image whose parts appear or disappear in steps (slide-app's
/// `svg-selector` / `svg-deselector` fragments):
/// `#svg-steps(path("images/x.svg"), reveal: (".generating": 2), center: true)`.
/// The selectors are those of the SVG's own `<style>` (ids, classes, element
/// names), applied by Typst's SVG renderer.
/// -> content
#let svg-steps(
  /// The SVG: `path("…")`. -> path | str
  src,
  /// CSS selector → the step (number or name) from which those elements
  /// are visible; they are hidden before. -> dictionary
  reveal: (:),
  /// CSS selector → the step from which they are hidden. -> dictionary
  hide: (:),
  /// `img`'s arguments (`zoom`, `width`, `center`…).
  ..args,
) = {
  let svg = read(src)
  step-mark(..reveal.values(), ..hide.values())
  at-step(k => {
    uses-step("svg-steps", ..(reveal.values() + hide.values()).map(step-no))
    let hidden = reveal.pairs().filter(((s, n)) => k < step-no(n)).map(p => p.first())
    hidden += hide.pairs().filter(((s, n)) => k >= step-no(n)).map(p => p.first())
    let style = if hidden == () { "" } else { "<style>" + hidden.join(", ") + " { visibility: hidden }</style>" }
    let parts = svg.split("</svg>")
    let body = if parts.len() < 2 { svg } else { parts.slice(0, -1).join("</svg>") + style + "</svg>" + parts.last() }
    img(bytes(body), ..args)
  })
}

/// The colours of `frame`'s kinds.
#let frame-colors = (
  block: accent,
  card: primary,
  algorithm: rgb("#2e7d32"),
  case-study: rgb("#8a4b08"),
  soa: rgb("#5b3a8a"),
  limitations: rgb("#b03030"),
)
/// A titled frame: `#frame(kind: "algorithm", title: [BM25])[…]`; `kind`
/// (block, card, algorithm, case-study, soa, limitations) picks the colour.
#let frame(kind: "block", title: none, body) = block-frame(
  title: title,
  color: frame-colors.at(kind, default: accent),
  body,
)

/// A content box drawn over the middle of the slide, usually in a step:
/// `#frag(3)[#focus[…]]`. The slide behind is veiled in white (`alpha`: its
/// opacity, 0 = no veil, 1 = hidden).
#let focus(width: 70%, alpha: 0.85, body) = place(center + horizon, float: false, {
  // larger than any page, centred on the box: covers the whole slide
  if alpha > 0 {
    place(center + horizon, rect(width: 200cm, height: 200cm, stroke: none,
      fill: white.transparentize(100% - alpha * 100%)))
  }
  block(width: width, fill: white, stroke: 1pt + luma(140), inset: 0.6em, body)
})

/// One of the blocks' icons, by name (a key of `icons`).
#let icon(name) = fa(icons.at(name).at(0), solid: icons.at(name).at(1))
/// A side comment, in grey, on its own line (a block); `inline: true` keeps
/// it in the running text.
#let comment(inline: false, body) = {
  let c = text(fill: luma(119), body)
  if inline { c } else { block(c) }
}
// A warning, an advantage, a drawback: the text behind an icon, on its own
// line (a block); `inline: true` keeps it in the running text.
#let _iconed(fill, name, inline, body) = {
  let c = [#text(fill: fill, icon(name)) #body]
  if inline { c } else { block(c) }
}
#let warning(inline: false, body) = _iconed(orange, "warning", inline, body)
#let pro(inline: false, body) = _iconed(green.darken(20%), "pro", inline, body)
#let con(inline: false, body) = _iconed(red, "con", inline, body)
/// Framed text.
/// Framed text; `center: true` centres the frame on its own line, `inset`
/// is the space between the text and the frame.
#let boxed(center: false, inset: (x: 0.4em, y: 0.25em), body) = {
  let b = box(stroke: 0.8pt + black, inset: inset, body)
  if center { align(std.center, b) } else { b }
}
/// Smaller text; `block: true` puts it on its own line.
#let small(block: false, body) = {
  let c = text(size: 0.8em, body)
  if block { std.block(c) } else { c }
}

/// A number (or short text) in a filled disc: `#circled(2)`, `#circled[a]`.
/// As list markers: `#set enum(numbering: circled)` before a `+` list, or
/// `#items(numbered: circled, …)`.
/// -> content
#let circled(
  /// What is in the disc. -> int | content
  n,
  /// The disc's diameter. -> length
  size: 1.25em,
  /// The disc's colour. -> color
  fill: primary,
) = box(baseline: -0.05em, circle(
  radius: size / 2,
  fill: fill,
  inset: 0pt,
  align(center + horizon, text(fill: white, weight: "bold", size: 0.62 * size, if type(n) == int { str(n) } else { n })),
))

/// A placeholder in a `#prompt`: the part a reader fills in, `#placeholder[{query}]`.
#let placeholder(body) = text(fill: rgb("#6366f1"), weight: "bold", body)

/// A prompt given to a model, shown verbatim (slide-app's `<Prompt>`), in a
/// grey box with an indigo bar on the left, in a monospace font:
/// `#prompt[Translate to French: #placeholder[{text}]]`. Line breaks are
/// written `\`; markup (`*bold*`, `#text(fill: red)[…]`) still works.
/// -> content
#let prompt(
  /// The text size (`0.6em` for a small one). -> length
  size: 0.75em,
  /// The box's width; `auto` fits it to its text (in an `#annot` label).
  /// -> relative | auto
  width: 100%,
  /// The prompt. -> content
  body,
) = block(
  width: width,
  above: 0.6em,
  below: 0.6em,
  fill: gradient.linear(rgb("#f5f7fa"), rgb("#e4e8ec"), angle: 45deg),
  stroke: (left: 3pt + rgb("#6366f1"), rest: 0.5pt + rgb("#d0d4d8")),
  radius: 4pt,
  inset: (x: 0.8em, y: 0.6em),
  {
    set smartquote(enabled: false)
    text(font: "DejaVu Sans Mono", size: size, fill: rgb("#374151"), body)
  },
)

/// A link to a Wikipedia page: `#wikiref("Okapi BM25")`, `lang: "fr"`,
/// `body:` for other text.
#let wikiref(name, lang: "en", body: none) = link(
  "https://" + lang + ".wikipedia.org/wiki/" + name.replace(" ", "_"),
  if body == none { name } else { body },
)
/// A link showing its URL.
#let selflink(url) = link(url, raw(url))

// ------------------------------------------------------------- annotations
// Element annotations (slide-app's <ElementAnnotation>, docs/annotations.md):
// a part of the slide is marked, `#mark("kl")[…]` (text or maths), and an
// `#annot("kl", step: 2)[label]` frames it and draws a label joined to it by
// a dashed curve. Everything is drawn by Typst on the page foreground
// (`annot-layer`, set by the template), so the web deck and the PDF agree.
//
// How it works: `mark` records the page box of its body (<annot-anchor>),
// `annot` records its options and whether it is shown on this step page
// (<annot-spec>); neither draws anything in the flow. The foreground of each
// page reads both and lays the labels out as slide-app's annotations.ts:
// above or below the target (or the `avoid` anchors), stacked so that they do
// not overlap, kept inside the page; `dx`/`dy` pin a label instead. On the
// web, it also records each label's box (<annot-box>) for the dev server's
// shift-O editor, which writes `dx`/`dy`/`width` back into the source.

/// A display formula's marked part keeps the display style: `mark` labels an
/// inline equation it is given, and inside a block equation that label turns
/// it into display maths (the template applies this rule: `show: annot-rules`).
#let annot-rules(body) = {
  let display(e) = math.equation(block: false, math.display(e.body))
  show math.equation.where(block: true): it => {
    show <annot-math>: display
    it
  }
  // a display formula marked as a whole (`mark` makes it inline, display style)
  show <annot-display>: it => {
    show <annot-math>: display
    it
  }
  body
}

/// The target of an annotation: `#mark("id")[text]`, or in maths
/// `#mark("kl", $beta "KL"(pi || pi_"ref")$)`, or a whole display formula
/// `#mark("loss", $ … $)` (an `avoid` zone, typically), or block content
/// (a heading and a list…) with `block: true`. Renders `body` unchanged;
/// inline, in a box (it does not break across lines).
#let mark(id, block: false, body) = {
  if type(id) != str { panic("mark: the id is a string: mark(\"kl\", …)") }
  // the box's top-left and bottom-right corners, where the body is actually
  // laid out (measuring the body apart is not reliable: maths styles)
  let corner(name, align, dy: 0pt) = place(align, dy: dy, context {
    let p = here().position()
    [#metadata((id: id, corner: name, page: p.page, x: p.x / 1pt, y: p.y / 1pt))<annot-anchor>]
  })
  // An inline box is as high as the text edges say (cap height to baseline),
  // so descenders and deep subscripts (π_θ_old) stick out of it: the corners
  // are moved out to the ink, the difference between measurements with the
  // text edges and with the glyph bounds (the box itself is not changed:
  // the line keeps its height).
  let inline-box(body) = box(context {
    let m(t, b) = measure({
      set text(top-edge: t, bottom-edge: b)
      body
    }).height
    let ink-up = m("bounds", "baseline")
    let ink = m("bounds", "bounds")
    let edge-up = m(text.top-edge, "baseline")
    let edge = m(text.top-edge, text.bottom-edge)
    corner("tl", top + left, dy: -calc.max(0pt, ink-up - edge-up))
    body
    corner("br", bottom + right, dy: calc.max(0pt, (ink - ink-up) - (edge - edge-up)))
  })
  if type(body) == content and body.func() == math.equation and body.block {
    // a display formula: its own display style in a centred box, spaced as a
    // display formula
    // (labelled: the parts marked inside keep the display style too)
    let inner = [#math.equation(block: false, math.display(body.body))<annot-display>]
    // (1.2em: the spacing of a display formula)
    return std.block(width: 100%, above: 1.2em, below: 1.2em, align(center, inline-box(inner)))
  }
  if block {
    // block content (a heading and a list, a frame…): a block around it
    return std.block({
      corner("tl", top + left)
      body
      corner("br", bottom + right)
    })
  }
  if type(body) == content and body.func() == math.equation {
    body = [#body<annot-math>]
  }
  inline-box(body)
}

/// Label sizes (slide-app's sm / md / lg): text size, and the widest a label
/// gets by itself, as a fraction of the page width.
#let annot-sizes = (
  sm: (text: 0.6em, max: 50%),
  md: (text: 0.7em, max: 35%),
  lg: (text: 0.85em, max: 82%),
)
/// The frame's margin around a target (pt, horizontal and vertical), and the
/// gap between a label and what it keeps clear of.
#let annot-pad = (x: 3, y: 3, gap: 10)

/// An annotation of the part marked `target`, with `body` as its label:
///   #annot("kl", step: "kl", color: red)[KL penalty]
/// Use `step:` rather than wrapping it in `#frag`: hidden content is still
/// laid out, so an annotation inside a hidden `#frag` would show.
/// -> content
#let annot(
  /// The id of the `#mark` it annotates. -> str
  target,
  /// Tells two annotations of the same target apart (the shift-O editor
  /// needs it to find the right one in the source). -> str | none
  id: none,
  /// The step it appears on (a number or a name of `#steps`), 1 = from the
  /// start. -> int | str
  step: 1,
  /// Shown on that step only (slide-app's `exclusive`). -> bool
  only: false,
  /// The step it disappears on (e.g. when a block appears under it).
  /// -> int | str | none
  until: none,
  /// The frame, the label's edge and the connector. -> color
  color: rgb("#6366f1"),
  /// `auto` (the side with more room), `"above"`, `"below"`. -> auto | str
  position: auto,
  /// An anchor id, or an array of them, the label keeps clear of (default:
  /// the target), e.g. a `#mark` around the whole formula.
  /// -> str | array | none
  avoid: none,
  /// `auto` (natural, at most the size's maximum), a length, or a % of the
  /// page width. -> auto | relative
  width: auto,
  /// Pins the label: its left edge relative to the target's (the shift-O
  /// editor of the dev server writes it). -> length | none
  dx: none,
  /// Pins the label: its top edge relative to the target's. -> length | none
  dy: none,
  /// `"sm"`, `"md"`, `"lg"`. -> str
  size: "md",
  /// `false`: no frame around the target. -> bool
  border: true,
  /// In a handout: `auto` (the deck setting, see `annot-config`), `true`,
  /// `false`. -> auto | bool
  handout: auto,
  /// The label. -> content
  body,
) = {
  if type(target) != str { panic("annot: the target is a string, the id of a #mark: annot(\"kl\")[…]") }
  if position not in (auto, "above", "below") { panic("annot: position is auto, \"above\" or \"below\"") }
  if size not in annot-sizes { panic("annot: size is \"sm\", \"md\" or \"lg\"") }
  step-mark(step, until, _last-step(body))
  context {
    let k = current-step()
    let n = step-no(step)
    let end = if until == none { none } else { step-no(until) }
    uses-step("annot", n, end)
    [#metadata((
        target: target,
        id: id,
        key: if id == none { target } else { id },
        page: here().page(),
        slide: utils.slide-counter.get().first(),
        shown: (if only { k == n } else { k >= n }) and (end == none or k < end),
        // ended by `until:` on this page (a handout leaves it out too)
        ended: end != none and k >= end,
        color: color,
        position: position,
        avoid: avoid,
        width: width,
        dx: dx,
        dy: dy,
        size: size,
        border: border,
        handout: handout,
        body: body,
      ))<annot-spec>]
    // the label, hidden, in the flow: its citations are then known to the
    // bibliography from the first pass (drawn on the foreground only, they
    // come too late for the document to converge)
    place(top + left, hide(body))
  }
}

/// The page foreground drawing the annotations of the page (the template sets
/// it: `config-page(foreground: annot-layer())`; `defaults`: the settings,
/// see `annot-config`).
#let annot-layer(defaults: (:)) = context {
  let pg = here().page()
  let specs = query(<annot-spec>).filter(m => m.value.page == pg).map(m => m.value)
  if specs.len() == 0 { return }
  let cfg = (handout: "all") + defaults
  if cfg.handout not in ("all", "steps", "none") { panic("annot-config: handout is \"all\", \"steps\" or \"none\"") }
  let shown(a) = if not is-handout { a.shown } else {
    let h = if a.handout == auto { cfg.handout } else if a.handout { "all" } else { "none" }
    if h == "all" { not a.ended } else if h == "none" { false } else { a.shown }
  }
  let anchors = query(<annot-anchor>).filter(m => m.value.page == pg).map(m => m.value)
  let (W, H) = (page.width / 1pt, page.height / 1pt)
  let box-of(id) = {
    let tl = anchors.find(m => m.id == id and m.corner == "tl")
    let br = anchors.find(m => m.id == id and m.corner == "br")
    if tl == none or br == none { none } else { (left: tl.x, top: tl.y, right: br.x, bottom: br.y) }
  }
  // (the text size first: the insets are in the label's em)
  let label(a, w) = text(size: annot-sizes.at(a.size).text, box(
    width: w * 1pt,
    inset: (x: 0.6em, y: 0.4em),
    fill: white,
    radius: 3pt,
    stroke: (left: 2.5pt + a.color, rest: 0.6pt + luma(225)),
    align(left, a.body),
  ))

  // Label sizes are measured with any citation (`#reference`) replaced by a
  // text of a usual length: measuring a real citation here keeps the
  // document from converging (the measured citation never settles). A label
  // holding one may thus be measured a line too short or too tall.
  let cite-free(body) = {
    show cite: [Author, A., Author, B., et al. 2023. A paper title of a usual length. Venue]
    body
  }

  // Layout (slide-app's annotations.ts, in pt): first each label alone…
  let nodes = ()
  for a in specs.filter(shown) {
    let t = box-of(a.target)
    if t == none { continue }
    let ids = if a.avoid == none { () } else if type(a.avoid) == str { (a.avoid,) } else { a.avoid }
    let boxes = ids.map(box-of).filter(b => b != none)
    let av = if boxes.len() == 0 { t } else {
      (
        left: calc.min(..boxes.map(b => b.left)),
        top: calc.min(..boxes.map(b => b.top)),
        right: calc.max(..boxes.map(b => b.right)),
        bottom: calc.max(..boxes.map(b => b.bottom)),
      )
    }
    let sz = annot-sizes.at(a.size)
    let w = if a.width == auto {
      let natural = measure(cite-free(text(size: sz.text, box(inset: (x: 0.6em), a.body)))).width / 1pt + 3
      calc.min(natural, sz.max / 100% * W)
    } else if type(a.width) == ratio { a.width / 100% * W } else if type(a.width) == relative {
      a.width.ratio / 100% * W + a.width.length / 1pt
    } else { a.width / 1pt }
    let h = measure(cite-free(label(a, w))).height / 1pt
    let pos = if a.position != auto { a.position } else if a.avoid != none { "below" } else if (
      H - av.bottom >= av.top
    ) { "below" } else { "above" }
    let x = t.left
    let y = if pos == "above" { av.top - h - annot-pad.gap } else { av.bottom + annot-pad.gap }
    if a.dx != none { x = t.left + a.dx / 1pt }
    if a.dy != none { y = t.top + a.dy / 1pt }
    nodes.push((a: a, t: t, w: w, h: h, x: x, y: y, pos: pos, fixed: a.dx != none or a.dy != none, avoid: boxes))
  }
  // …then from left to right, each moved off the earlier ones it overlaps
  // (and off the pinned ones) and kept inside the page; a pinned label stays
  // where it is put
  nodes = nodes.sorted(key: n => n.x)
  let pad = 5
  for i in range(nodes.len()) {
    let n = nodes.at(i)
    if n.fixed { continue }
    if n.x + n.w > W - 9 { n.x = W - n.w - 9 }
    if n.x < 9 { n.x = 9 }
    for j in range(nodes.len()) {
      let o = nodes.at(j)
      if j == i or (j > i and not o.fixed) { continue }
      let apart = (
        n.x + n.w + pad < o.x or o.x + o.w + pad < n.x or n.y + n.h + pad < o.y or o.y + o.h + pad < n.y
      )
      if not apart { n.y = if n.pos == "above" { o.y - n.h - pad } else { o.y + o.h + pad } }
    }
    if n.y < 4 { n.y = 4 }
    if n.y + n.h > H - 4 { n.y = H - n.h - 4 }
    nodes.at(i) = n
  }

  // Drawing: target frames, connectors, labels on top
  let at(x, y, body) = place(top + left, dx: x * 1pt, dy: y * 1pt, body)
  for n in nodes.filter(n => n.a.border) {
    let t = n.t
    at(t.left - annot-pad.x, t.top - annot-pad.y, rect(
      width: (t.right - t.left + 2 * annot-pad.x) * 1pt,
      height: (t.bottom - t.top + 2 * annot-pad.y) * 1pt,
      radius: 3pt,
      stroke: (paint: color.mix(n.a.color, white), thickness: 1.5pt, dash: "dashed"),
    ))
  }
  // Connectors: a quadratic curve from a side of the label to a side of the
  // target's frame, ending on the frame (never inside it). Every pair of
  // sides is tried: facing sides (a curve leaving the label and entering the
  // frame square to them), perpendicular ones (an elbow), and the same side of
  // both (a U around, a detour); the one crossing the least of the `avoid`
  // zones, then the shortest, wins.
  let inside(p, b) = p.at(0) > b.left and p.at(0) < b.right and p.at(1) > b.top and p.at(1) < b.bottom
  let quad-at(p0, c, p2, u) = range(2).map(i => (
    (1 - u) * (1 - u) * p0.at(i) + 2 * (1 - u) * u * c.at(i) + u * u * p2.at(i)
  ))
  let route(n) = {
    let t = n.t
    let (fx, fy) = if n.a.border { (annot-pad.x, annot-pad.y) } else { (2, 2) }
    let f = (left: t.left - fx, top: t.top - fy, right: t.right + fx, bottom: t.bottom + fy)
    let l = (left: n.x, top: n.y, right: n.x + n.w, bottom: n.y + n.h)
    let cx(b) = (b.left + b.right) / 2
    let cy(b) = (b.top + b.bottom) / 2
    let clamp(v, lo, hi) = if lo > hi { (lo + hi) / 2 } else { calc.max(lo, calc.min(v, hi)) }
    // a side: its point (facing the other box) and its outward direction
    let side(b, s, other, inset) = if s == "top" or s == "bottom" {
      let x = clamp(cx(other), b.left + inset, b.right - inset)
      ((x, if s == "top" { b.top } else { b.bottom }), (0, if s == "top" { -1 } else { 1 }))
    } else {
      let y = clamp(cy(other), b.top + 3, b.bottom - 3)
      ((if s == "left" { b.left } else { b.right }, y), (if s == "left" { -1 } else { 1 }, 0))
    }
    let shrink(b, k) = (left: b.left + k, top: b.top + k, right: b.right - k, bottom: b.bottom - k)
    let best = none
    for ls in ("top", "bottom", "left", "right") {
      for ts in ("top", "bottom", "left", "right") {
        let (p0, d0) = side(l, ls, f, 8)
        let (p2, d2) = side(f, ts, l, 4)
        let ahead(p, d, q) = (q.at(0) - p.at(0)) * d.at(0) + (q.at(1) - p.at(1)) * d.at(1)
        let dot = d0.at(0) * d2.at(0) + d0.at(1) * d2.at(1)
        let cands = if dot == 1 {
          // same side of both (bottom and bottom…): a U around, beyond the
          // further one, a little or well out
          let (mx, my) = ((p0.at(0) + p2.at(0)) / 2, (p0.at(1) + p2.at(1)) / 2)
          (16, 32, 56).map(bend => {
            let c = if d0.at(0) == 0 {
              let y = if d0.at(1) > 0 { calc.max(p0.at(1), p2.at(1)) } else { calc.min(p0.at(1), p2.at(1)) }
              (mx, y + d0.at(1) * bend)
            } else {
              let x = if d0.at(0) > 0 { calc.max(p0.at(0), p2.at(0)) } else { calc.min(p0.at(0), p2.at(0)) }
              (x + d0.at(0) * bend, my)
            }
            // a detour: only when the direct ways are blocked
            (c, 60 + bend)
          })
        } else if ahead(p0, d0, p2) <= 2 or ahead(p2, d2, p0) <= 2 {
          // each end must face the other one
          ()
        } else if dot == 0 {
          // perpendicular sides: the corner where both square lines meet
          let c = if d0.at(0) == 0 { (p0.at(0), p2.at(1)) } else { (p2.at(0), p0.at(1)) }
          if ahead(p0, d0, c) > 2 and ahead(p2, d2, c) > 2 { ((c, 0),) } else { () }
        } else {
          // facing sides: leave square, bend half way
          let c = if d0.at(0) == 0 { (p0.at(0), (p0.at(1) + p2.at(1)) / 2) } else {
            ((p0.at(0) + p2.at(0)) / 2, p0.at(1))
          }
          ((c, 0), (((p0.at(0) + p2.at(0)) / 2, (p0.at(1) + p2.at(1)) / 2), 1))
        }
        for (c, extra) in cands {
          let pts = range(1, 20).map(k => quad-at(p0, c, p2, k / 20))
          // through its own label or into the frame: never; through the
          // `avoid` zones (the formula the target is in): as little as can be,
          // the column right above and below the target aside (the way in)
          let hits = pts.filter(p => inside(p, shrink(l, 1)) or inside(p, shrink(f, 1))).len() * 1000
          hits += pts.filter(p => (
            (p.at(0) < f.left or p.at(0) > f.right) and n.avoid.any(b => inside(p, b))
          )).len() * 60
          let length = range(19).fold(0, (acc, k) => {
            let (a, b) = (if k == 0 { p0 } else { pts.at(k - 1) }, pts.at(k))
            acc + calc.sqrt(calc.pow(b.at(0) - a.at(0), 2) + calc.pow(b.at(1) - a.at(1), 2))
          })
          let score = hits + length + extra
          if best == none or score < best.score { best = (score: score, p0: p0, c: c, p2: p2) }
        }
      }
    }
    if best == none {
      // overlapping boxes: straight from the label's centre to the frame's
      let p0 = (cx(l), if cy(l) < cy(f) { l.bottom } else { l.top })
      let p2 = (clamp(p0.at(0), f.left, f.right), if cy(l) < cy(f) { f.top } else { f.bottom })
      best = (p0: p0, c: ((p0.at(0) + p2.at(0)) / 2, (p0.at(1) + p2.at(1)) / 2), p2: p2)
    }
    best
  }
  for n in nodes {
    let r = route(n)
    let pt(p) = (p.at(0) * 1pt, p.at(1) * 1pt)
    place(top + left, curve(
      stroke: (paint: n.a.color.transparentize(40%), thickness: 1.2pt, dash: (3pt, 2pt)),
      curve.move(pt(r.p0)),
      curve.quad(pt(r.c), pt(r.p2)),
    ))
  }
  for n in nodes {
    at(n.x, n.y, label(n.a, n.w))
    // the label's box, for the dev server's shift-O editor
    if is-web {
      [#metadata((
          key: n.a.key,
          target: n.a.target,
          id: n.a.id,
          page: pg,
          slide: n.a.slide,
          x: n.x,
          y: n.y,
          w: n.w,
          h: n.h,
          tx: n.t.left,
          ty: n.t.top,
        ))<annot-box>]
    }
  }
}

/// The settings of a deck, given to its theme (they replace the course's,
/// the template's `annotations:`):
///   #show: course-theme.with(config-info(…), annot-config(handout: "none"))
/// - handout: what a handout (`--input handout=1`, one page per slide, its
///   last step) shows: "all" (default) every annotation of the slide, whatever
///   its step; "steps" those of the last step (not an `only:` one of an
///   earlier step); "none" none. An annotation's `handout: true / false`
///   overrides it.
/// (A Touying page setting rather than a state: content before the title
/// slide would make an empty slide.)
#let annot-config(..args) = config-page(foreground: annot-layer(defaults: args.named()))

// ------------------------------------------------------- "in detail" slides
/// Depth on demand (slide-app's <Details>, docs/details.md): slides written
/// right after the slide they explain, laid out in an appendix section at the
/// end of the deck ("In detail"), each group behind its own title card:
///
///   === FlashAttention
///   Never materialise $Q K^top$ … #details-link("flash")[How it works]
///
///   #details("flash", title: [FlashAttention])[
///     === Why attention is memory-bound
///     …
///     === Tiling and online softmax
///     …
///   ]
///
/// `#details` lays out nothing where it is written: the template collects
/// the groups (`collect-details`) and lays them out after the deck
/// (`details-appendix`), as an appendix (Touying: no slide number added to
/// the total). A group may hold `#include "module.typ"`, links to other groups
/// and groups of its own. In the PDF, a link goes to the group's title card and
/// the footer of each slide of the group links back to the (first) slide
/// linking to it; in the browser, the viewer returns to the step the talk was
/// at (Esc or I) and does not walk from the talk into the details, nor from a
/// group into the next one.
#let details(id, title: none, body) = {
  if type(id) != str { panic("details: the id is a string: details(\"flash\", title: […])[…]") }
  [#metadata((id: id, title: title, body: body))<details-src>]
}

/// The groups of `body` (`#details`), in document order, those inside a group
/// right after it. Called by the template on the whole deck.
#let collect-details(c) = {
  if type(c) != content { return () }
  if c.func() == metadata {
    if c.at("label", default: none) == <details-src> {
      return (c.value,) + collect-details(c.value.body)
    }
    return ()
  }
  let out = ()
  if c.has("children") { for x in c.children { out += collect-details(x) } }
  if c.has("child") { out += collect-details(c.child) }
  if c.has("body") and type(c.body) == content { out += collect-details(c.body) }
  out
}

/// The group the current page is in: its id, "" on the appendix's own title
/// card, none in the talk. Needs `context`.
#let current-details() = {
  let start = query(<details-start>)
  if start == () or here().page() < start.first().location().page() { return none }
  let groups = query(selector(<details-group>).before(here()))
  if groups == () { "" } else { groups.last().value.id }
}

/// A link from a slide to a group of "in detail" slides: `#details-link("flash")[How it works]`.
#let details-link(id, body) = context {
  [#metadata((id: id, page: here().page(), slide: utils.slide-counter.get().first()))<details-ref>]
  if query(label("details-" + id)) == () {
    panic("details-link: no #details(\"" + id + "\") in the deck")
  }
  link(label("details-" + id), text(fill: link-color, {
    text(size: 0.85em, fa(0xf0a9)) // circle-arrow-right
    h(0.3em)
    body
  }))
}

/// The footer of an "in detail" slide (the template's `slide` calls it): a
/// link back to the slide linking to the group, or nothing in the talk.
#let details-back(back: [Back to slide]) = context {
  let id = current-details()
  if id == none or id == "" { return }
  let refs = query(<details-ref>).filter(m => m.value.id == id)
  if refs == () { return }
  let r = refs.first()
  link(r.location(), text(fill: link-color, [#fa(0xf0a8) #back #r.value.slide]))
  h(0.6em)
}

/// The "in detail" appendix: one section (`title`) with every group of
/// `groups` (`collect-details`), each behind a sub-section card holding the
/// links' target; nothing when there is none. The template adds it after the deck.
#let details-appendix(groups, title: [In detail]) = if groups.len() > 0 {
  show: appendix
  [= #title]
  [#metadata(none)<details-start>]
  for g in groups {
    [== #(if g.title == none { g.id } else { g.title })]
    [#metadata((id: g.id))<details-group>]
    [#metadata(g.id)#label("details-" + g.id)]
    g.body
  }
}

// ------------------------------------------------------------ image overlays
/// Shapes and labels drawn over an image at %-coordinates of the image (slide-app's
/// <Overlay>, <CircleOverlay>, <RectOverlay>):
///
///   #overlay(img(path("images/x.png"), zoom: 0.6),
///     circle-at(x: 30%, y: 40%, size: 8%, step: 2),
///     rect-at(x: 10%, y: 60%, width: 30%, height: 15%, step: "cls", color: blue),
///     note-at(x: 60%, y: 5%, step: 3)[the head])
///
/// x, y: from the image's left and top edge (a ratio; a length is from the corner too).
/// Each shape takes `step` (a number or a step name, 1 = from the start),
/// `only: true` (on that step only) and `until` (the step it disappears on);
/// steps are declared with `#steps` as for `#frag`.
/// - circle-at: centred on (x, y); `size`: its diameter (a ratio is of the
///   image width), `color`, `thickness`, `fill`
/// - rect-at: top-left corner at (x, y), `width` / `height` (ratios of the
///   image's), `color`, `thickness`, `fill`, `radius`
/// - note-at: any content, its top-left corner at (x, y); `width` (auto),
///   `fill` (white), `color` (the frame, none for none)
#let circle-at(x: 50%, y: 50%, size: 8%, color: red, thickness: 2pt, fill: none, step: 1, only: false, until: none) = (
  kind: "circle", x: x, y: y, size: size, color: color, thickness: thickness, fill: fill,
  step: step, only: only, until: until,
)
#let rect-at(x: 0%, y: 0%, width: 20%, height: 20%, color: red, thickness: 2pt, fill: none, radius: 2pt, step: 1, only: false, until: none) = (
  kind: "rect", x: x, y: y, width: width, height: height, color: color, thickness: thickness,
  fill: fill, radius: radius, step: step, only: only, until: until,
)
#let note-at(x: 0%, y: 0%, width: auto, fill: white, color: red, step: 1, only: false, until: none, body) = (
  kind: "note", x: x, y: y, width: width, fill: fill, color: color, body: body,
  step: step, only: only, until: until,
)
#let overlay(body, ..shapes) = {
  // the shapes' steps, seen by Touying (they are drawn in a `layout`)
  let shapes-d = shapes.pos().filter(s => type(s) == dictionary)
  step-mark(
    ..shapes-d.map(s => (s.at("step", default: 1), s.at("until", default: none))).flatten(),
    _last-step((body,) + shapes-d.map(s => s.at("body", default: none))),
  )
  layout(avail => {
  // the image's size, as laid out here
  let size = measure(body, width: avail.width)
  box(width: size.width, height: size.height, {
  body
    // a ratio of the image's width (w) or height (h); a length as is
    let rel(v, ref) = if type(v) == ratio { v / 100% * ref } else if type(v) == relative {
      v.ratio / 100% * ref + v.length
    } else { v }
    for s in shapes.pos() {
      if type(s) != dictionary or "kind" not in s {
        panic("overlay: the shapes are circle-at(…), rect-at(…) or note-at(…)[…], not " + repr(s))
      }
      let (x, y) = (rel(s.x, size.width), rel(s.y, size.height))
      let shape = if s.kind == "circle" {
        let d = rel(s.size, size.width)
        place(top + left, dx: x - d / 2, dy: y - d / 2, circle(
          radius: d / 2, stroke: s.thickness + s.color, fill: s.fill,
        ))
      } else if s.kind == "rect" {
        place(top + left, dx: x, dy: y, rect(
          width: rel(s.width, size.width), height: rel(s.height, size.height),
          stroke: s.thickness + s.color, fill: s.fill, radius: s.radius,
        ))
      } else {
        place(top + left, dx: x, dy: y, box(
          width: if s.width == auto { auto } else { rel(s.width, size.width) },
          fill: s.fill, inset: 0.3em, radius: 3pt,
          stroke: if s.color == none { none } else { 1pt + s.color },
          text(size: 0.8em, s.body),
        ))
      }
      context {
        let k = current-step()
        let n = step-no(s.step)
        let end = if s.until == none { none } else { step-no(s.until) }
        uses-step("overlay", n, end)
        if (if s.only { k == n } else { k >= n }) and (end == none or k < end) { shape }
      }
    }
  })
  })
}

// ------------------------------------------------------ interactive SVG
/// An SVG shown live in the browser (its links, hover styles and scripts
/// work: slide-app's `<object>`), as a picture in the PDF:
/// `#svg-object(path("images/x.svg"), zoom: 0.8)`. Sized as `#img` (zoom,
/// width, height: the natural size, 1 px = 1/700 of the page height).
/// -> content
#let svg-object(
  /// The SVG: `path("…")`. -> path | str
  src,
  /// As `#img`'s. -> auto | relative
  width: auto,
  /// As `#img`'s. -> auto | relative
  height: auto,
  /// A factor on the natural size. -> int | float
  zoom: 1,
  /// Centred horizontally. -> bool
  center: false,
) = {
  let svg = read(src)
  let body = layout(size => context {
    let natural = measure(image(bytes(svg), format: "svg"))
    let px = page.height / 700
    let ratio = natural.height / natural.width
    let (w, h) = if width != auto and height != auto { (width, height) } else if width != auto {
      let w = if type(width) == ratio { width / 100% * size.width } else { width }
      (w, w * ratio)
    } else if height != auto { (height / ratio, height) } else {
      let w = calc.min(natural.width / 1pt * px * zoom, size.width)
      (w, w * ratio)
    }
    interactive("svg-object", width: w, height: h, props: (svg: svg), snapshot: false, fallback: image(
      bytes(svg),
      format: "svg",
      width: 100%,
      height: 100%,
    ))
  })
  if center { align(std.center, body) } else { body }
}
