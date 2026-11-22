# Citations

## Citing

```typst
#reference("doi://10.48550/arXiv.2410.06205")      // by DOI
#reference("https://openreview.net/forum?id=Gtvu") // by URL (no DOI)
#reference("arXiv:2410.06205")                     // by arXiv id (or arxiv.org link)
#reference("isbn:978-0-262-03561-3")               // a book, by ISBN
#reference(<SaltonVectorSpaceModel1975>)           // by bib key
#reference("doi://10.1/a", <KeyB>)                 // several
#cite(<SaltonVectorSpaceModel1975>)                // inline (bib key only)
```

`#reference` prints the full reference, small, at the end of a slide. Cite
by a **portable identifier** (DOI, URL, arXiv, a book's ISBN) rather than by
a key: anyone can resolve it, or import it into their own Zotero.

**Keep the text.** After the identifier (or `<key>`, in the string), the
reference's text, `Author et al. year, Title`, as the Zotero action below
copies it:

```typst
#reference("doi://10.48550/arXiv.2410.06205 Barbero et al. 2024, Round and Round We Go!")
#reference("<SaltonVectorSpaceModel1975> Salton et al. 1975, A Vector Space Model…")
#reference("Doe and Roe 2019, A Paper With No Identifier")    // the text alone
```

The full reference comes from the bibliography as before; the text is what
is left when nothing else works: shown when the bibliography does not have
the entry (a collaborator finds the paper by its title), found by (its
title) when there is no identifier. `cathedra sync --annotate --src=<SRC>
<BIB>` gives the references of the sources their text, from the
bibliography: `<key>` becomes `"<key> text"`, `"doi://…"` becomes
`"doi://… text"` (a reference with a text, or not in the bibliography, is
left alone). A `"<key> …"` is cited as `<key>` is, also with plain `typst
compile`. The identifier is looked
up in the course's bibliography (`BIB` in its Makefile, e.g. `src/main.bib`,
a file of the course in git) by the entries' `doi`, `url` and `eprint`
fields. These forms are the same identifier:

- DOI: `doi://10.…`, `doi:10.…`, `10.…`, `https://doi.org/10.…` (any case);
- arXiv: `arXiv:2410.06205`, `https://arxiv.org/abs/2410.06205v2`, the
  `/pdf/` link, the DOI `10.48550/arXiv.2410.06205` (version ignored);
- ISBN: `isbn:978-…` (hyphens and spaces ignored), for a book only: the
  ISBN of a paper or a chapter is that of its proceedings or book, shared;
- URL: without its scheme, `www.` or final `/`.

An identifier that no entry has is shown as a link (doi.org, arxiv.org,
openlibrary.org, the URL), and when cathedra compiles, marked "not in the
bibliography" and the slide `check` (the W list): add the paper to the
bibliography.

## Where the bibliography comes from

Every reference comes from Zotero: never type a bib entry by hand. With the
course option `ZOTERO=1` (its Makefile), `cathedra sync --zotero` (run by
every make target that compiles, so also before `make serve`) completes the
bibliography:

- each reference cited in the sources and missing from the .bib is looked
  up in the local Zotero app (every library, groups included), by its
  identifier, else by its title (the one item with that title and year:
  none, or several, is a warning), exported as
  biblatex and **appended** to the .bib, without its user-specific fields
  (`file`: local paths, `keywords`: tags). Commit the .bib: others get the
  entry without Zotero;
- not in Zotero (or Zotero not running): a warning, and the slide shows the
  link until the paper is there.

A paper whose key (Zotero's) is already taken by another entry is not added:
cite that entry, or fix the key in Zotero. Zotero 7 must let other apps talk
to it: Settings → Advanced → "Allow other applications on this computer to
communicate with Zotero".

Without `ZOTERO`, nothing talks to Zotero: add the entries to the .bib
yourself (from a Zotero export).

**No duplicate key.** Typst refuses a `.bib` with a key defined twice, and
the decks read the course's `.bib` itself (no cleaned copy), so that plain
`typst compile` works from a clone. A duplicate is then an error everywhere:
`cathedra sync` (run by `make setup`, and by any make target when `BIB`
changed) lists them with their lines and fails, as does every compilation.

A deck loads the bibliography once, hidden, e.g. at its end, with the
engine's citation style (`bib-style`):

```typst
#place(hide(bibliography("/src/main.bib", style: bib-style, title: none)))
```

## The link on the icon

The newspaper icon in front of a reference is a link:

- in the dev server (`make serve`), with `ZOTERO`: to the item in **your
  Zotero**;
- otherwise (built deck, PDF): to the **DOI**, or else the URL.

Zotero items are local (your library, your groups): their ids never go into
the .bib. `cathedra sync --zotero` finds each entry's item from its DOI / URL
/ arXiv id / ISBN, else its title and year, and keeps it in `lib/zotero.json` (gitignored; entries Zotero
does not have are looked up again with `--refresh`). `lib/refs-links.json`
(generated, gitignored) holds, for each key, its Zotero link, DOI, URL and
identifiers; with plain `typst compile` neither is read: the references by
identifier are then links, as if not in the .bib.

## Copying references from Zotero

The [Actions & Tags](https://github.com/windingwind/zotero-actions-tags)
plugin (Zotero 7) can copy the selected items as `#reference` arguments,
ready to paste: for each, its identifier (DOI, else for a book its ISBN,
else its URL) and its text, comma-separated:

```typst
#reference("doi://10.48550/arXiv.2405.04434 DeepSeek-AI 2024, DeepSeek-V2: A Strong, Economical…", "https://openreview.net/forum?id=GtvuNrk58a Barbero et al. 2024, Round and Round We Go!")
```

An item with no identifier gives its text alone (found by its title). A
new action, "Run script", with this script (and a shortcut):

```js
// Copy the selected items as #reference arguments:
//   "doi://<DOI> Author et al. year, Title", … (else, a book, isbn:<ISBN>,
//   else the URL; no identifier: the text alone). Never a zotero:// link:
//   it only opens in your own Zotero.
if (item) return; // run once, on all the selected items
const quote = (s) => '"' + s.replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"';
const seen = new Set();
const out = [];
for (let it of items) {
  // from an annotation or an attachment (PDF, EPUB, snapshot…): its item
  while (it && (it.isAnnotation() || it.isAttachment())) it = it.parentItem;
  if (!it || seen.has(it.id)) continue;
  seen.add(it.id);
  const field = (name) => {
    try {
      return (it.getField(name) || "").trim();
    } catch (e) {
      return ""; // a field this item type does not have
    }
  };
  const doi = field("DOI");
  // a paper's or chapter's ISBN is that of its proceedings / book
  const isbn = it.itemType === "book" ? field("ISBN").split(/[\s,;]+/)[0] : "";
  const id = doi ? `doi://${doi}` : isbn ? `isbn:${isbn}` : field("url");
  // Author et al. year, Title (the authors, else the editors…)
  const creators = it.getCreators();
  const authors = creators.filter(
    (c) => Zotero.CreatorTypes.getName(c.creatorTypeID) === "author",
  );
  const names = (authors.length ? authors : creators).map((c) => c.lastName);
  const who = names.length > 2 ? `${names[0]} et al.` : names.join(" and ");
  const year = Zotero.Date.strToDate(field("date")).year || "";
  const head = [who, year].filter(Boolean).join(" ");
  const text = head ? `${head}, ${field("title")}` : field("title");
  out.push(quote([id, text].filter(Boolean).join(" ")));
}
if (!out.length) return "[Copy references] no item";

const clipboard = new Zotero.ActionsTags.api.utils.ClipboardHelper();
clipboard.addText(out.join(", "), "text/unicode");
clipboard.copy();
return `[Copy references] ${out.length} copied`;
```
