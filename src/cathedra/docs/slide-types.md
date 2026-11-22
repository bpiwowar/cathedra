# Slide types and todo markers

## Slide types

```typst
=== A digression
#slide-type("optional")
```

Types: `todo` 🚧 (work in progress), `check` 👀 (to check), `optional` ◇, `practical` 💻. The
outline and the structure browser show a badge, and the slide a small grey
icon at the top right (a type with no icon shows as its name; `todo` has
its own note, below).

The template draws the icons: `academic` puts `#slide-type-marks()` at the
right of its header, and its `slide-types:` option changes them: `none`
hides them, a function of the types (an array of strings) draws its own:

```typst
#let (theme: course-theme, title-slide: title-slide) = academic(
  slide-types: types => text(fill: red, types.join(", ")),
)
```

Another template calls `#slide-type-marks()` where it wants them, and
`#set-slide-type-display(f)` (in its preamble) to change how they look;
`slide-type-icons` lists the icons, `current-slide-types()` the types of the
slide being laid out.

Leave a type out of the deck:

- in the structure browser (**T**), the *In the deck* checkboxes (one per
  type the deck uses, and *main* for the slides with no type), then **OK**:
  the deck reloads, and the choice is remembered for this deck;
- in the URL: `?hide=optional`, `?show=todo,optional` (beats what was
  remembered); `?hide=main` keeps only the typed slides.

A section or subsection whose slides are all left out goes too (its title
page included), unless *no empty sections* is unticked (`?show=empty`); the
title page and the other sections always stay.

Hidden slides are removed before Reveal starts: numbering and navigation
skip them.

## Work in progress

```typst
=== Boolean retrieval
#todo("Motivate by history (librarians)")
```

Marks the slide `todo`: a red note in the top-right corner and, on the web, a
red frame. **M** hides and shows the markers (remembered; `?todo=0` /
`?todo=1` in the URL). For a PDF without them, compile with
`--input todo=0`. The note is optional (*work in progress* by default).
**W** lists the slides marked `todo` or `check`, to go to or edit; in the
dev server, **shift-W** or a click on the note changes a slide's state
(work in progress, to check, done) and its note, in the source (see
[the viewer](viewer.md)).

## To check

```typst
=== Language models
#to-check()                       // "new slide"
#to-check("check the BLEU numbers")
```

Marks the slide `check` 👀: a slide written or rewritten (e.g. by an
assistant) that still needs its author's review. Drawn like `#todo`, in
amber (an amber frame on the web); **M** and `--input todo=0` hide it too.
`make outline` counts these slides ("N to check").
