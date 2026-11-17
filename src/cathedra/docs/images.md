# Images

## Where they go

Next to the file that shows them: a module's images in
`modules/<topic>/images/`, a deck's in `lectures/images/`.

Formats: SVG, PNG, JPEG, GIF, WebP and PDF (Typst reads them all; a file whose
extension lies about its format fails to load). A draw.io diagram is shown
through the SVG exported next to it.

## `#img`

```typst
#img(path("images/attention.webp"))                    // natural size
#img(path("images/attention.webp"), zoom: 0.6, center: true)
#img(path("images/plot.svg"), width: 60%)               // explicit size
#img(path("images/plot.svg"), height: 8cm)
#img(path("images/plot.svg"), vh: 50%)                 // half the page's height
```

`#img(path, width: auto, height: auto, vh: none, vw: none, zoom: 1, center: false, origin: none, filename: none, resize: none)`

- **path**: `path("…")`, relative to the file that calls `#img`. A plain
  string would be resolved relative to `lib/slides.typ`, where `img` is
  defined, and not be found. `path(…)` resolves the path in the calling
  file. A root-absolute string (`"/modules/x/images/y.png"`) works too.
- **size**: without `width` or `height`, the image keeps its natural size in
  pixels, one pixel being 1/700 of the page height (a 700 px tall image
  fills the slide's height), times `zoom`, and never wider than the space
  available (a column, a frame…). An explicit `width` or `height` (`50%`,
  `8cm`) wins over all that.
- **vh**, **vw**: a fraction of the page's height, width, as in CSS:
  `vh: 50%` is half the page, whatever holds the image. A `%` in `height` or
  `width` is a fraction of the space available instead (the column, the
  frame…), whose height is often not what you expect.
- **center**: centred horizontally.
- **origin**: where the image comes from (a URL, e.g. a Zotero PDF
  annotation); in the dev server, the image is a link to it.

## SVG parts in steps

`#svg-steps(path, reveal: (:), hide: (:), ..)` shows an SVG whose parts
appear or disappear with the steps of the slide (the `svg-selector` /
`svg-deselector` fragments of the MDX decks). The keys are CSS selectors of
the SVG's elements (`.class`, `#id`), the values the step (number or name)
from which they are shown (`reveal`) or hidden (`hide`); the other arguments
are `#img`'s.

```typst
#svg-steps(path("images/teacher-forcing.svg"), reveal: (".generating": 2), center: true)
```

Hidden parts keep their place (`visibility: hidden`), so the image does not
move. The selectors go into a `<style>` added to the SVG, read by Typst's SVG
renderer: give the elements an `id` or a `class` in the drawing program
(Inkscape: Object properties / XML editor).

## Shapes over an image

`#overlay(body, ..shapes)` draws circles, rectangles and notes over an image
(any content: `#img`, `#image`, a figure), at coordinates relative to it
(slide-app's `<Overlay>`, `<CircleOverlay>`, `<RectOverlay>`):

```typst
#steps("head", "cls")
#overlay(img(path("images/attention.webp"), zoom: 0.6),
  circle-at(x: 30%, y: 40%, size: 8%, step: "head"),
  rect-at(x: 10%, y: 60%, width: 30%, height: 15%, color: blue, step: "cls"),
  note-at(x: 62%, y: 5%, step: "cls")[the [CLS] token],
)
```

- `x`, `y`: % of the image's width and height from its top-left corner (a
  length works too); a circle is centred there, a rectangle and a note have
  their top-left corner there.
- `circle-at(size: 8%)`: the diameter (% of the image's width);
  `rect-at(width:, height:)` (% of the image's), `radius`;
  `note-at(width: auto)[…]`, `fill` (white), `color` (its frame, `none`).
- `color` (red), `thickness` (2pt), `fill` (none).
- Steps as for `#frag`: `step` (a number or a name, 1 = from the start),
  `only: true` (that step only), `until` (the step it goes away on).

## Interactive SVG

`#svg-object(path("images/x.svg"), zoom: 0.8, center: true)` shows the SVG
in the browser as a document of its own (slide-app's `<object>`): its links,
`:hover` styles and `<script>`s work. The PDF shows it as a picture. Sized as
`#img` (`zoom`, `width`, `height`). Links in the SVG open in the object
itself unless they say `target="_blank"` (or `_top`). An engine widget
(`svg-object`, see [widgets](widgets.md#the-engines-widgets)).

## Plain `#image`

Typst's own `#image("images/x.png", width: 50%)` resolves its path in the
file it is written in, and sizes as Typst does (the full width by default, or
what is given). Use it for anything `#img` does not cover: `fit`, a figure
inside CeTZ (`content(…, image(…))`), etc.

## Figures

Diagrams drawn in Typst (CeTZ), possibly changing with the steps of the
slide: see [figures](figures.md). Live web components: see
[widgets](widgets.md).

## Fetched images

An image can be fetched from where it comes from, once, instead of being
copied by hand:

```typst
#img(path("images/entity-lens.webp"), origin: "zotero://open-pdf/library/items/ABC?page=3&annotation=XYZ", resize: "800x")
#img(path("images/png-demo.webp"), origin: "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png", vh: 40%)
```

- when the file of `path("…")` does not exist, `make images` fetches
  `origin:` into it; once it exists, it is used as it is (`origin` stays a
  link in the dev server). A Zotero origin needs `annotation=`; the picture
  is the one Zotero rendered, `~/Zotero/cache/library/<annotation>.png` (open
  the annotation in Zotero once). It is never fetched when the library is
  not there: `make images` then fails for that image.
- **resize**: `"800x"` (max width), `"x300"` (max height) or `"500x210"`, in
  pixels. Without it the cap is the slot: `vh: 50%` is 50% of 700 px,
  `vw` likewise (1244 px), else 1920 x 1400, times `IMG_SCALE` (default 2).
  Images are never enlarged.

`make images` (run by `serve`, `html`, `pdf` and `handout`) downloads once
into `.cache/images/raw/` (gitignored), shrinks (Pillow) and writes the
file in the format of its extension (`.webp`: lossy WebP; an SVG is copied).
**Commit the file**: it is a file of the course like any other, and Typst
fetches nothing, so a clone compiles with plain `typst compile`
([building](building.md#without-cathedra)). A file read but ignored by
git makes `make check` fail.

An `http(s)://` string as the image itself, `#img("https://…")`, is not
supported (API 4): Typst cannot load it; give the file and its origin.

Only fetched images are shrunk. `make check-images` lists the images of the
course that are heavy (> 1 MB or wider/taller than 2400 px), which end up at
full size in the PDF and the web pages.
