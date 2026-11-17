# Templates

A template is what a course looks like: the title slide, the section cards,
the slide frame, the fonts. It is configured once, in the course's
`common/course.typ`, and returns the functions the decks use.

## academic

The `academic` template: the title slide on the course artwork, the
course line and the title in dark red; section and sub-section cards; on
every slide the main section › sub-section above and the slide number below.

```typst
#import "/cathedra/templates/academic/academic.typ": academic

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
| `data` | `(:)` | the course's generated data (`ref-links`, `widget-shots`), read by `common/course.typ` when cathedra compiles (see [course](course.md#commoncoursetyp)) |

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
`typst.toml`: its name (`cathedra-academic`), its version (`1.0.0`), its entry
point, and the engine API versions it works with:

```toml
[tool.cathedra]
api = ">=3, <4"
```

The engine's API version is `VERSION` (`api-version` in `lib/slides.typ`). A
template uses only the engine's public API (`lib/slides.typ`, no `_`-prefixed
name), reads no course file (the course gives it its data), and asserts the
API at compile time (`#assert-api(3, 4, who: "cathedra-academic 1.0.0")`, a
clear error otherwise); `cathedra check` (`make check`) also checks the
`api` range of the templates the decks use.

### Where this is going

Three layers, so that templates evolve on their own:

1. **the engine**: the Python package (the command, the viewer);
2. **the core API**: `lib/slides.typ`, versioned by the API version;
3. **template packages**: `academic` and others, each with its own version
   and API range, possibly in a repository of their own.

Today the templates ship with the engine and are imported by path
(`/cathedra/typst/templates/academic/academic.typ`). The plan, in order:

1. **Name: cathedra.** The core is the Typst package `cathedra`, the
   templates `cathedra-<name>` (`cathedra-academic`). Typst Universe refuses
   "typst" in a name, and `lectern` is taken (`lectern-slides`, a Markdown
   slide tool). The engine follows: PyPI and GitHub `cathedra`, command
   `cathedra` (`cathedra` is gone from PyPI), with old names still read
   where courses use them (`[tool.cathedra]`, `--input cathedra=1`).
2. **Icons as SVG (API 5).** Packages cannot ship fonts, so `fa` and its
   Font Awesome font go: `fa-icon(name, solid: true, ..text-args)` (the
   signature of `@preview/fontawesome`) draws an SVG in the text colour. The
   engine's icons live in the core package (`icons/`), a course's in
   `src/icons/{solid,regular,brands}/`, given by `course.typ`.
   `cathedra icon add [NAME…] [--regular] [--brands]` downloads them from
   `@fortawesome/fontawesome-free` at the version pinned in
   `src/icons/VERSION` (`--upgrade` moves it); without names, it adds the
   icons the decks use and lack (a missing icon leaves a `<fa-missing>`
   marker that `typst query` finds; `check` fails on one). `icon search`
   looks names up, `migrate` turns code points into names. Licence: the
   icons are CC BY 4.0 (fonts OFL, code MIT); each SVG keeps its
   `<!--! Font Awesome … -->` attribution comment, an `icons/LICENSE` and the
   README say so; brand icons stand only for their brand.
3. **Course files given as `path`.** A package resolves a string path in its
   own directory, so whatever the course hands the template is a `path(…)`
   value, e.g. the widget snapshots in `course.typ`:
   `json("/.cache/widgets/manifest.json").pairs().map(((k, v)) => (k, path(v))).to-dict()`.
4. **`setup` installs the packages.** `uvx cathedra setup` builds
   `cathedra` and the templates into Typst's local packages
   (`~/Library/Application Support/typst/packages/local/`,
   `~/.local/share/typst/packages/local/`), the template's
   `import "../../lib/slides.typ"` rewritten to `@local/cathedra:<ver>`;
   copies from the wheel, refreshed by each `setup` from a checkout. The
   sources keep their relative imports, so a course still compiles by path.
   `@local` is for testing what is about to be published, not for courses: a
   course importing it would not compile from a plain clone.
5. **Typst Universe.** `cathedra` and `cathedra-academic` published as
   `@preview` packages (licence file `LICENSE`, the SPDX expression covering
   the icons, a `[template]` section for `typst init`). A course then imports
   `@preview/cathedra-academic:1.0.0`, compiles from a plain clone without
   the submodule, and needs the engine only for the web decks and the site.

A template also declares in `[tool.cathedra]` what the engine should add
to the web decks (e.g. a `viewer.css`).
