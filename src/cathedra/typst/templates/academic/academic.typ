// The `academic` template: a title slide on the course artwork, section and sub-section cards, slides
// with the current headings above and the slide number below.
//
// A course configures it once, in its common/course.typ:
//
//   #import "/cathedra/templates/academic.typ": academic
//   #let (theme: course-theme, title-slide: title-slide) = academic(
//     course: [Statistical Learning],
//     background: read("/common/background.svg", encoding: none),
//   )
//
// and a deck then writes `#show: course-theme.with(config-info(…))` and
// `#title-slide(url: …)`.
#import "../../lib/slides.typ": *

// The engine API this template is written for (typst.toml,
// [tool.cathedra] api): checked when a deck compiles.
#assert-api(3, 5, who: "cathedra-academic 1.0.0")

// The slide title, as shown above a slide.
#let title-block(t) = block(below: 0.8em, text(size: 1.25em, weight: "bold", fill: primary, t))

// One slide: the main section › sub-section above, the slide title as the
// preamble of every step, the page marker and the number below.
#let slide(config: (:), repeat: auto, setting: body => body, composer: auto, ..bodies) = touying-slide-wrapper(self => {
  let header(self) = {
    set text(size: 0.5em, fill: muted)
    utils.display-current-heading(level: 1)
    context {
      let sub = utils.current-heading(level: 2)
      if sub != none [ #sym.space.thin › #sub.body]
    }
  }
  let footer(self) = {
    set text(size: 0.5em, fill: muted)
    page-marker()
    h(1fr)
    // an "in detail" slide: back to the slide linking to it
    details-back(back: self.store.at("details-back", default: [Back to slide]))
    context utils.slide-counter.display() + " / " + utils.last-slide-number
  }
  let self = utils.merge-dicts(self, config-page(header: header, footer: footer), config-common(
    subslide-preamble: self.store.subslide-preamble,
  ))
  touying-slide(self: self, config: config, repeat: repeat, setting: setting, composer: composer, ..bodies)
})

#let new-section-slide(config: (:), level: 1, body) = touying-slide-wrapper(self => {
  let self = utils.merge-dicts(self, config-page(footer: page-marker(kind: "section")))
  touying-slide(self: self, config: config, align(horizon, {
    text(size: 1.6em, weight: "bold", fill: primary, utils.display-current-heading(level: 1))
    v(0.2em)
    line(length: 60%, stroke: 2pt + accent)
    body
  }))
})

#let new-subsection-slide(config: (:), level: 2, body) = touying-slide-wrapper(self => {
  let self = utils.merge-dicts(self, config-page(footer: page-marker(kind: "subsection")))
  touying-slide(self: self, config: config, align(horizon, {
    text(size: 0.8em, fill: muted, utils.display-current-heading(level: 1))
    linebreak()
    text(size: 1.4em, weight: "bold", fill: accent, utils.display-current-heading(level: 2))
    body
  }))
})

// Configure the template; returns the deck theme and the title slide.
//
// - course: the course line above the deck title (content)
// - background: the title-slide artwork, as bytes (`read(…, encoding: none)`),
//   or none. It is drawn at the slide height; with content in the corners
//   only, its left half is anchored left and its right half right, so that a
//   4:3 artwork is not cropped on a 16:9 slide.
// - background-ratio: the artwork's width / height
// - title-margin: the title slide's page margins, keeping the text off the
//   artwork (its logos); a dictionary as `page(margin: …)`
// - title-align: where the title block sits between those margins
//   (horizon: centred vertically, top: under the top margin)
// - url: printed under the title (the decks' home page), or none
// - title-color, font, math-font, lang
// - font-size: the body text (20pt; 16–17pt for denser slides)
// - annotations: the element annotations' settings for every deck
//   (`annot-config` in lib/slides.typ), e.g. `(handout: "none")`
// - details-title: the title of the "in detail" appendix (`#details`); auto:
//   "In detail", "Compléments" when `lang` is "fr"
// - data: the course's generated data, read by its common/course.typ when
//   cathedra compiles (`generated`): `(ref-links: json("/lib/refs-links.json"),
//   widget-shots: …)` (see `course-setup` in lib/slides.typ); none of it is
//   required
#let academic(
  course: none,
  background: none,
  background-ratio: 4 / 3,
  title-margin: (top: 18%, right: 10%, bottom: 15%, left: 20%),
  title-align: horizon,
  url: none,
  title-color: rgb("#880000"),
  font: "Libertinus Serif",
  math-font: "New Computer Modern Math",
  font-size: 20pt,
  // the space between the items of a list or enumeration (`-`, `+`)
  list-spacing: 0.9em,
  lang: "en",
  annotations: (:),
  details-title: auto,
  // the page shape, "W-H": "16-9" (default), "16-10", "4-3", …; the page is
  // 841.89pt (A4) wide. A deck's `course-theme.with(aspect-ratio: …)`
  // overrides it, and `--input aspect-ratio=16-10` both
  aspect-ratio: "16-9",
  data: (:),
) = {
  let fr = lang == "fr"
  let details-title = if details-title != auto { details-title } else if fr [Compléments] else [In detail]
  let title-background = if background != none {
    context {
      let (pw, h) = (page.width, page.height)
      let w = h * background-ratio
      let art = image(background, width: w, height: h)
      place(top + left, block(width: w / 2, height: h, clip: true, place(top + left, art)))
      place(top + left, dx: pw - w / 2, block(width: w / 2, height: h, clip: true, place(
        top + left,
        dx: -w / 2,
        art,
      )))
    }
  }

  let title-slide(config: (:), course: course, url: url) = touying-slide-wrapper(self => {
    let info = self.info
    let self = utils.merge-dicts(self, config-common(freeze-slide-counter: true), config-page(
      header: none,
      footer: page-marker(kind: "title"),
      background: title-background,
      margin: title-margin,
    ))
    touying-slide(self: self, config: config, align(title-align, {
      set par(spacing: 0.5em)
      if course != none { text(size: 1.6em, fill: title-color, course); parbreak() }
      text(size: 1.3em, fill: title-color, weight: "bold", info.title)
      if info.subtitle != none { parbreak(); text(size: 1.05em, fill: rgb("#555"), info.subtitle) }
      v(1em)
      if info.author != none { info.author; parbreak() }
      if info.date != none { utils.display-info-date(self); parbreak() }
      if url != none { v(0.6em); text(size: 0.8em, link(url)) }
    }))
  })

  let course-aspect-ratio = aspect-ratio
  let theme(aspect-ratio: auto, ..args, body) = {
    // `--input aspect-ratio=…` wins, then the deck's, then the course's
    let aspect-ratio = sys.inputs.at(
      "aspect-ratio",
      default: if aspect-ratio == auto { course-aspect-ratio } else { aspect-ratio },
    )
    set text(font: (font,), size: font-size, lang: lang)
    show math.equation: set text(font: math-font)
    show link: set text(fill: link-color)
    show raw: set text(size: 0.9em)
    show strong: set text(fill: primary)
    set list(marker: (text(fill: accent)[•], text(fill: accent)[‣], [–]), spacing: list-spacing)
    set enum(spacing: list-spacing)
    set par(justify: false, spacing: 0.75em)
    set table(stroke: 0.5pt + luma(180), inset: 0.35em)
    show table: set text(size: 0.8em)
    show table.cell.where(y: 0): set text(weight: "bold")
    // term lists (`/ Term: description`): the term in bold on its own line,
    // the description indented under it; `#set terms(spacing: 0.9em)` for
    // more room above each term
    show terms: it => {
      let above = if it.spacing == auto { 0.6em } else { it.spacing }
      for item in it.children {
        block(above: above, below: 0.3em, strong(item.term))
        pad(left: 1.2em, block(above: 0.3em, below: 0.3em, item.description))
      }
    }
    // block quotes (`#quote(block: true, attribution: […])`, or a
    // bibliography key: `attribution: <key>`, cited): in italics, between
    // quotes, the attribution under it on the right
    show quote.where(block: true): it => block(width: 100%, inset: (x: 1em), {
      text(style: "italic")["#it.body"]
      if it.attribution != none {
        let a = it.attribution
        align(right, text(size: 0.8em)[— #if type(a) == label { cite(a) } else { a }])
      }
    })
    // figures as on slides: not numbered, a small caption under the body
    // (`#figure(img(path("x.webp")), caption: [Source])`)
    set figure(numbering: none, gap: 0.4em)
    show figure.caption: set text(size: 0.75em)
    show: annot-rules
    // the course data, before the first slide
    course-setup(..data)
    show: touying-slides.with(
      // the foreground draws the element annotations (#mark / #annot); a
      // deck giving its own foreground keeps them with `annot-layer()` in it
      config-page(
        ..utils.page-args-from-aspect-ratio(aspect-ratio),
        margin: (x: 1.6em, top: 2em, bottom: 1.6em),
        foreground: annot-layer(defaults: annotations),
      ),
      config-common(
        // the title's look, for the pages of an allow-breaks slide
        preamble: set-title-block(title-block),
        slide-fn: slide,
        slide-level: 3,
        new-section-slide-fn: new-section-slide,
        new-subsection-slide-fn: new-subsection-slide,
        receive-body-for-new-section-slide-fn: true,
        receive-body-for-new-subsection-slide-fn: true,
        zero-margin-header: false,
        zero-margin-footer: false,
        breakable: false,
        // `--input handout=1`: the last step of each slide only
        handout: is-handout,
      ),
      config-colors(primary: primary, secondary: accent, neutral-light: muted, neutral-lightest: white),
      // the slide title, unless the slide has a #sidebar (which shows it)
      // (an allow-breaks slide repeats it on each of its pages itself)
      config-store(subslide-preamble: context if not has-sidebar() and break-page() == none {
        title-block(slide-title())
      }, details-back: if fr [Retour à la diapositive] else [Back to slide]),
      ..args,
    )
    body
    // the "in detail" slides (#details), in an appendix
    details-appendix(collect-details(body), title: details-title)
  }

  (theme: theme, title-slide: title-slide)
}
