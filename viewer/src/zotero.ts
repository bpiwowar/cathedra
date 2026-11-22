// Z (dev server): open the Zotero item(s) behind the current slide (slide-app's
// src/zotero-links.ts). In the dev build an `#img(…, origin: "zotero://…")`
// and a `#reference` icon are zotero:// links of the page (lib/slides.typ),
// the SVG page's own <a> (svg-pages.ts). Z takes those of the step
// page shown, in a picker (even for one).
import { t } from "./i18n";

export type ZoteroLink = { href: string; label: string };

/** A readable shorthand for a zotero:// URL: the item key, the page and annotation. */
function reference(href: string): string {
  const [base, query] = href.split("?");
  const parts = [base.split("/").filter(Boolean).pop() || href];
  const q = new URLSearchParams(query || "");
  if (q.get("page")) parts.push(`p. ${q.get("page")}`);
  if (q.get("annotation")) parts.push(q.get("annotation")!);
  return parts.join(" · ");
}

/** The text of the text layer on the line of `link`, to its right (a
 *  reference's citation, right after its icon). */
function lineText(page: HTMLElement, link: HTMLElement): string {
  const r = link.getBoundingClientRect();
  const mid = (r.top + r.bottom) / 2;
  // the SVG page's transparent text (svg-pages.ts)
  const spans = [...page.querySelectorAll<HTMLElement>(".tsel")].filter((s) => {
    const b = s.getBoundingClientRect();
    return b.top <= mid && b.bottom >= mid && b.left >= r.left - 2;
  });
  spans.sort((a, b) => a.getBoundingClientRect().left - b.getBoundingClientRect().left);
  // (without the icons: Font Awesome glyphs are private-use characters, boxes
  // outside the slide's fonts)
  const text = spans
    .map((s) => s.textContent)
    .join(" ")
    .replace(/[\uE000-\uF8FF]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length > 110 ? text.slice(0, 108) + "…" : text;
}

/** The step page of `section` on screen. */
function shownPage(section: HTMLElement): HTMLElement | null {
  const pages = [...section.querySelectorAll<HTMLElement>(":scope > .page")];
  return pages.filter((p, i) => i === 0 || p.classList.contains("visible")).at(-1) ?? null;
}

/** The zotero:// links of the page shown, without duplicates. */
export function slideZoteroLinks(section: HTMLElement | null): ZoteroLink[] {
  const page = section && shownPage(section);
  if (!page) return [];
  const seen = new Set<string>();
  const out: ZoteroLink[] = [];
  // the SVG page's own links (svg-pages.ts)
  for (const a of page.querySelectorAll<HTMLElement>("svg a")) {
    const href = a.getAttribute("href") ?? a.getAttribute("xlink:href") ?? "";
    if (!href.startsWith("zotero:") || seen.has(href)) continue;
    seen.add(href);
    const r = a.getBoundingClientRect();
    // an icon is small (a reference); a large link is a figure
    const figure = r.height > 40;
    const text = figure ? "" : lineText(page, a);
    out.push({
      href,
      label: text || `${t(figure ? "zotero.figure" : "zotero.reference")} · ${reference(href)}`,
    });
  }
  return out;
}
