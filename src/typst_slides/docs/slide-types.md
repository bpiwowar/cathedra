# Slide types and todo markers

## Slide types

```typst
=== A digression
#slide-type("optional")
```

Types: `todo` 🚧 (work in progress), `optional` ◇, `practical` 💻. The mark
renders as nothing; the outline and the structure browser show a badge.

Leave a type out of the deck:

- in the structure browser (**T**), the *In the deck* checkboxes (one per
  type the deck uses), then **OK**: the deck reloads, and the choice is
  remembered for this deck;
- in the URL: `?hide=optional`, `?show=todo,optional` (beats what was
  remembered).

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
`--input todo=0`.
