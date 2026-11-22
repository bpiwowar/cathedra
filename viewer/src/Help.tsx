// Help (H, dev server): the authoring documentation, README.md and docs/*.md,
// as slide-app's documentation overlay. Relative links between the pages are
// followed inside the panel, with Home and Back; external links open a tab.
import MarkdownIt from "markdown-it";
import React from "react";
import { t } from "./i18n";

const md = new MarkdownIt({ html: false, linkify: true });
// headings get ids, so that `page.md#anchor` links land on them
const slug = (s: string) => s.toLowerCase().replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-");
md.core.ruler.push("heading_ids", (state) => {
  state.tokens.forEach((t, i) => {
    if (t.type === "heading_open") t.attrSet("id", slug(state.tokens[i + 1].content));
  });
});

// the quick reference: what one needs while writing slides (README: about)
const HOME = "docs/quick.md";
function resolve(from: string, href: string) {
  const out = from.split("/").slice(0, -1);
  for (const part of href.split("/")) {
    if (part === "..") out.pop();
    else if (part && part !== ".") out.push(part);
  }
  return out.join("/");
}

let lastPage = HOME; // reopening H comes back to the page left

// ------------------------------------------------------------------ search
// Every section of every page (the text under a heading, down to the next
// one), searched for all the words of the query.
type Section = { page: string; heading: string; anchor?: string; level: number; text: string };
// (markdown links keep their text: `[text](url)` -> `text`)
const plainText = (s: string) => s.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1").replace(/[`*]/g, "");
// { "README.md": markdown, "docs/x.md": markdown, … }: docs.json next to the
// deck (written by the dev builds of cathedra), loaded when H opens
let docs: Record<string, string> = {};
let sections: Section[] = [];

/** Load docs.json (again: the dev server rewrites it when a page changes). */
export async function loadDocs() {
  try {
    const r = await fetch(`docs.json?t=${Date.now()}`);
    if (r.ok) docs = await r.json();
  } catch {
    // no help pages: the panel says so
  }
  sections = toSections(docs);
}

const toSections = (docs: Record<string, string>): Section[] => Object.entries(docs).flatMap(([page, src]) => {
  const out: Section[] = [{ page, heading: page, level: 0, text: "" }];
  let fence = false;
  for (const line of src.split("\n")) {
    if (line.startsWith("```")) fence = !fence;
    const h = !fence && /^(#{1,6})\s+(.*)$/.exec(line);
    if (h) out.push({ page, heading: plainText(h[2]), anchor: slug(h[2]), level: h[1].length, text: "" });
    else out[out.length - 1].text += line + "\n";
  }
  return out.filter((x) => x.level > 0 || x.text.trim());
});

function search(query: string) {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const scored = sections.flatMap((x) => {
    const head = x.heading.toLowerCase();
    const all = head + "\n" + x.text.toLowerCase();
    if (!words.every((w) => all.includes(w))) return [];
    // a heading that is the query (an API name) first, then headings that
    // hold the words, then the text
    const score = (head === query.toLowerCase().trim() ? 100 : 0) + words.filter((w) => head.includes(w)).length * 10 - x.level;
    return [{ x, score }];
  });
  return scored.sort((a, b) => b.score - a.score).slice(0, 40).map(({ x }) => x);
}

// A line of the section's text around the first word found.
function snippet(x: Section, query: string) {
  const text = plainText(x.text).replace(/\s+/g, " ").trim();
  const w = query.toLowerCase().split(/\s+/).find((w) => w && text.toLowerCase().includes(w));
  const at = w ? text.toLowerCase().indexOf(w) : 0;
  const from = Math.max(0, at - 60);
  return (from ? "…" : "") + text.slice(from, from + 160) + (from + 160 < text.length ? "…" : "");
}

export function Help(props: { onClose: () => void }) {
  const [history, setHistory] = React.useState<{ page: string; anchor?: string }[]>([{ page: lastPage }]);
  const { page, anchor } = history[history.length - 1];
  const body = React.useRef<HTMLDivElement>(null);
  const overlay = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => overlay.current?.focus(), []);
  React.useEffect(() => {
    lastPage = page;
    const target = anchor && body.current?.querySelector("#" + CSS.escape(anchor));
    if (target) target.scrollIntoView();
    else body.current?.scrollTo(0, 0);
  }, [page, anchor, history.length]);

  const [query, setQuery] = React.useState("");
  const [selected, setSelected] = React.useState(0);
  const searchBox = React.useRef<HTMLInputElement>(null);
  const results = React.useMemo(() => search(query), [query]);
  React.useEffect(() => setSelected(0), [query]);

  const go = (p: string, a?: string) => {
    setQuery("");
    setHistory((h) => [...h, { page: p, anchor: a }]);
    overlay.current?.focus();
  };
  const back = () => setHistory((h) => (h.length > 1 ? h.slice(0, -1) : h));
  const html = React.useMemo(
    () => (docs[page] !== undefined ? md.render(docs[page]) : `<p>${t("help.noPage", { page: `<code>${page}</code>` })}</p>`),
    [page],
  );

  function onClick(e: React.MouseEvent) {
    const a = (e.target as HTMLElement).closest("a");
    const href = a?.getAttribute("href");
    if (!a || !href) return;
    if (/^[a-z]+:/i.test(href) || href.startsWith("//")) {
      a.target = "_blank";
      a.rel = "noopener";
      return;
    }
    e.preventDefault();
    const [p, frag] = href.split("#");
    if (!p) body.current?.querySelector("#" + CSS.escape(frag))?.scrollIntoView();
    else go(resolve(page, p), frag);
  }

  return (
    <div
      className="sb-overlay"
      tabIndex={-1}
      ref={overlay}
      onKeyDown={(e) => {
        if (e.target === searchBox.current) {
          // in the search box: ↑ ↓ pick a result, Enter opens it, Esc clears
          if (e.key === "ArrowDown") setSelected((i) => Math.min(i + 1, results.length - 1));
          else if (e.key === "ArrowUp") setSelected((i) => Math.max(i - 1, 0));
          else if (e.key === "Enter" && results[selected]) go(results[selected].page, results[selected].anchor);
          else if (e.key === "Escape" && query) setQuery("");
          else if (e.key === "Escape") props.onClose();
          else return;
          e.preventDefault();
          return;
        }
        if (e.key === "/") searchBox.current?.focus();
        else if (e.key === "Escape" || e.key === "h" || e.key === "H") props.onClose();
        else if (e.key === "Backspace" || e.key === "ArrowLeft") back();
        else if (e.key === "Home") go(HOME);
        else return;
        e.preventDefault();
      }}
      onClick={(e) => e.target === e.currentTarget && props.onClose()}
    >
      <div className="sb-panel help-panel">
        <div className="sb-header">
          <button onClick={() => go(HOME)} title={t("help.home")}>⌂</button>
          <button onClick={back} disabled={history.length < 2} title={t("help.back")}>←</button>
          <strong>{page}</strong>
          <span className="sb-spacer" />
          <input
            ref={searchBox}
            className="help-search"
            placeholder={t("help.search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button onClick={props.onClose}>✕</button>
        </div>
        {query.trim() ? (
          <div className="help-body help-results">
            {results.length ? (
              results.map((x, i) => (
                <div
                  key={x.page + "#" + (x.anchor ?? "") + i}
                  className={"help-result" + (i === selected ? " selected" : "")}
                  onMouseEnter={() => setSelected(i)}
                  onClick={() => go(x.page, x.anchor)}
                >
                  <div>
                    <strong>{x.heading}</strong> <span className="sb-file">{x.page}</span>
                  </div>
                  <div className="help-snippet">{snippet(x, query)}</div>
                </div>
              ))
            ) : (
              <p>{t("help.none")}</p>
            )}
          </div>
        ) : (
          <div className="help-body" ref={body} onClick={onClick} dangerouslySetInnerHTML={{ __html: html }} />
        )}
        <div className="sb-help">
          {query.trim()
            ? t("help.keysSearch")
            : t("help.keys")}
        </div>
      </div>
    </div>
  );
}
