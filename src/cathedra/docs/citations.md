# Citations

## Citing

```typst
#reference(<SaltonVectorSpaceModel1975>)          // full reference, small, end of slide
#reference(<KeyA>, <KeyB>)                        // several
#cite(<SaltonVectorSpaceModel1975>)               // inline
```

Keys are those of the course's bibliography (`BIB` in its Makefile, e.g.
`src/main.bib`), a file of the course in git. Every reference comes from
Zotero (Better BibTeX export): never type a bib entry by hand. A missing
paper goes into Zotero first, then into the bibliography.

## Where the bibliography comes from

A deck prints its references on the slides; it loads the course's
bibliography once, hidden, e.g. at its end, with the engine's citation style
(`bib-style`):

```typst
#place(hide(bibliography("/src/main.bib", style: bib-style, title: none)))
```

**No duplicate key.** Typst refuses a `.bib` with a key defined twice, and
the decks read the course's `.bib` itself (no cleaned copy), so that plain
`typst compile` works from a clone. A duplicate is then an error everywhere:
`cathedra sync` (run by `make setup`, and by any make target when `BIB`
changed) lists them with their lines and fails, as does every compilation.
Fix it in Zotero: merge the duplicate items, or give them distinct citation
keys (Better BibTeX: pin the key), then let the export rewrite the file.

`cathedra sync <BIB>` also writes `lib/refs-links.json` (generated,
gitignored): for each key, its Zotero link, DOI and URL, read only when
cathedra compiles.

## The link on the icon

The newspaper icon in front of a reference is a link:

- in the dev server (`make serve`): to the item in **Zotero**;
- otherwise (built deck, PDF): to the **DOI**, or else the URL.

The Zotero links depend on the machine. `sync.py` asks the running Zotero app
for its user id: an item of another user's library gets no Zotero link (its
DOI is used), a group item opens in the group. When Zotero is not running,
every personal item is taken as the local user's. Run `cathedra sync` again
once Zotero is open (from the course directory, with the bibliography as
argument). `lib/refs-links.json` is not versioned: with plain `typst
compile`, the icons are there without a link.
