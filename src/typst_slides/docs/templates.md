# Templates

A template is what a course looks like: the title slide, the section cards,
the slide frame, the fonts. It is configured once, in the course's
`common/course.typ`, and returns the functions the decks use.

## academic

The `academic` template: the title slide on the course artwork, the
course line and the title in dark red; section and sub-section cards; on
every slide the main section › sub-section above and the slide number below.

```typst
#import "/slide-app/templates/academic/academic.typ": academic

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [Information Retrieval],
  background: read("/common/background.svg", encoding: none),
  url: "https://example.org/slides",
  data: course-data,      // the course's generated data (see course.md)
)
```

| Option | Default | |
|---|---|---|
| `course` | none | the course line above the deck title |
| `background` | none | the title-slide artwork, as bytes |
| `background-ratio` | `4 / 3` | the artwork's width / height |
| `url` | none | printed under the title (the decks' home page) |
| `title-color` | dark red | course line and title |
| `font`, `math-font` | Libertinus Serif, New Computer Modern Math | |
| `font-size` | `20pt` | body text; 16–17pt for denser slides |
| `list-spacing` | `0.9em` | space between the items of a list (`-`) or an enumeration (`+`); `0.65em` is Typst's (the line spacing). A slide can set its own: `#set list(spacing: 0.6em)` |
| `lang` | `"en"` | hyphenation, quotes, the viewer's language (`"fr"`, `"en"`), the title of the "in detail" appendix |
| `details-title` | `auto` | the title of the ["in detail"](details.md) appendix (*In detail*, *Compléments* in French) |
| `data` | `(:)` | the course's generated data (`ref-links`, `widget-shots`), read by `common/course.typ` when typst-slides compiles (see [course](course.md#commoncoursetyp)) |

The artwork is drawn at the slide height; with content in its corners only,
its left half is anchored left and its right half right, so that a 4:3
artwork is not cropped on a 16:9 slide.

A deck then uses what it returns:

```typst
#show: course-theme.with(config-info(
  title: [Linear models],
  author: [A. Author],
  date: [Lecture 2],
))

#title-slide()     // or #title-slide(url: …) to override the option
```

## Writing a template

A template is a function returning `(theme: …, title-slide: …)`. It builds on
`lib/slides.typ` and Touying, and must keep what the viewer relies on:

- every page calls `page-marker(kind: …)` (in its footer): `"title"`,
  `"section"`, `"subsection"` or `"slide"`. The web build groups pages into
  Reveal slides with it, and the outline reads the structure from it;
- `slide-level: 3` (`=` section, `==` sub-section, `===` slide).

## Templates and the engine

A template is a Typst package directory, `templates/<name>/` with its
`typst.toml`: its name (`slides-academic`), its version (`1.0.0`), its entry
point, and the engine API versions it works with:

```toml
[tool.typst-slides]
api = ">=3, <4"
```

The engine's API version is `VERSION` (`api-version` in `lib/slides.typ`). A
template uses only the engine's public API (`lib/slides.typ`, no `_`-prefixed
name), reads no course file (the course gives it its data), and asserts the
API at compile time (`#assert-api(3, 4, who: "slides-academic 1.0.0")`, a
clear error otherwise); `typst-slides check` (`make check`) also checks the
`api` range of the templates the decks use.

### Where this is going

Three layers, so that templates evolve on their own:

1. **the engine**: the `typst-slides` package (the command, the viewer);
2. **the core API**: `lib/slides.typ`, versioned by the API version;
3. **template packages**: `slides-academic` and others, each with its own
   version and API range, possibly in a repository of their own.

Today the templates ship with the engine and are imported by path
(`/slide-app/typst/templates/academic/academic.typ`). The intended scheme,
for later: the core and the templates installed as Typst packages
(`@local/typst-slides-core:3.0.0`, `@local/slides-academic:1.0.0`, by e.g.
`typst-slides template install`), a course pinning the template's version in
`common/course.typ` (`#import "@local/slides-academic:1.0.0": academic`), and
a template declaring in `[tool.typst-slides]` what the engine should add to
the web decks (e.g. a `viewer.css`).
