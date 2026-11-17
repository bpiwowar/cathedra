# Templates

A template is what a course looks like: the title slide, the section cards,
the slide frame, the fonts. It is configured once, in the course's
`common/course.typ`, and returns the functions the decks use.

## academic

The `academic` template: the title slide on the course artwork, the
course line and the title in dark red; section and sub-section cards; on
every slide the main section › sub-section above and the slide number below.

```typst
#import "/slide-app/templates/academic.typ": academic

#let (theme: course-theme, title-slide: title-slide) = academic(
  course: [Information Retrieval],
  background: read("/common/background.svg", encoding: none),
  url: "https://example.org/slides",
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
| `lang` | `"en"` | hyphenation, quotes, the viewer's language (`"fr"`, `"en"`), the title of the "in detail" appendix |
| `details-title` | `auto` | the title of the ["in detail"](details.md) appendix (*In detail*, *Compléments* in French) |

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
