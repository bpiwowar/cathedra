# Citations

## Citing

```typst
#reference(<SaltonVectorSpaceModel1975>)          // full reference, small, end of slide
#reference(<KeyA>, <KeyB>)                        // several
#cite(<SaltonVectorSpaceModel1975>)               // inline
```

Keys are those of `lib/refs.bib`. Every reference
comes from Zotero (Better BibTeX export): never type a bib entry by hand. A
missing paper goes into Zotero first, then into the bibliography.

## Where the bibliography comes from

`tools/sync.py <BIB>` (run by `make setup`, and by any make target when the
course's `BIB` changed) writes, in the course:

- `lib/refs.bib`: the shared bibliography, as Typst reads it;
- `lib/refs-links.json`: for each key, its Zotero link, DOI and URL;
- `lib/refs.csl`: the citation style.

A deck prints its references on the slides; it still needs the bibliography
loaded once, hidden, e.g. at its end:

```typst
#place(hide(bibliography("/lib/refs.bib", style: "/lib/refs.csl", title: none)))
```

## The link on the icon

The newspaper icon in front of a reference is a link:

- in the dev server (`make serve`): to the item in **Zotero**;
- otherwise (built deck, PDF): to the **DOI**, or else the URL.

The Zotero links depend on the machine. `sync.py` asks the running Zotero app
for its user id: an item of another user's library gets no Zotero link (its
DOI is used), a group item opens in the group. When Zotero is not running,
every personal item is taken as the local user's. Run `./tools/sync.py` again
once Zotero is open (from the course directory, with the bibliography as
argument). The generated files are not versioned.
