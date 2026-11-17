// The pages of the deck, as inline SVG (docs/viewer.md). build.mjs cuts
// typst.ts's SVG of the deck into svg/<hash>.svg per page,
// svg/glyphs-<hash>.svg (glyph outlines shared by every page, put once in the
// document) and the images; svg.json lists them. A page shown is the page's
// <svg> inside its `.page` div:
// - text selection and find-in-page: typst.ts's transparent text (`.tsel`
//   divs in foreignObjects); a copy joins the pieces of a line (below);
// - links: the SVG's own <a>; internal ones call handleTypstLocation(), set
//   here (-> details.ts followLink);
// - morphing (morph-svg.ts) moves the parts' SVG elements.
// main.tsx mounts the pages around the current slide and unmounts the others.
import { followLink } from "./details";

export type SvgManifest = { w: number; h: number; glyphs: string; pages: string[] };

let manifest: SvgManifest | null = null;
let glyphsUrl = "";
let glyphHost: HTMLElement | null = null;

// page text, by hash (a small cache: a page remounted soon after is not fetched again)
const cache = new Map<string, Promise<string>>();
const CACHE = 120;
function fetchPage(hash: string): Promise<string> {
  let p = cache.get(hash);
  if (p) {
    cache.delete(hash);
    cache.set(hash, p);
    return p;
  }
  p = fetch(`svg/${hash}.svg`).then((r) => {
    if (!r.ok) throw new Error(`svg/${hash}.svg: ${r.status}`);
    return r.text();
  });
  p.catch(() => cache.delete(hash));
  cache.set(hash, p);
  while (cache.size > CACHE) cache.delete(cache.keys().next().value!);
  return p;
}

/** svg.json of deck `version`, or null (missing). */
export async function loadSvgManifest(version: string | number): Promise<SvgManifest | null> {
  try {
    const r = await fetch(`svg.json?v=${version}`);
    if (!r.ok) return null;
    const m = (await r.json()) as SvgManifest;
    await setManifest(m);
    return m;
  } catch {
    return null;
  }
}

async function setManifest(m: SvgManifest) {
  manifest = m;
  if (m.glyphs !== glyphsUrl) {
    const text = await (await fetch(m.glyphs)).text();
    if (!glyphHost) {
      glyphHost = document.createElement("div");
      glyphHost.id = "typst-glyphs";
      glyphHost.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
      document.body.prepend(glyphHost);
    }
    glyphHost.innerHTML = text;
    glyphsUrl = m.glyphs;
  }
}

/** Mount page `el.dataset.page` (its SVG) into `el`. */
export async function mountSvgPage(el: HTMLElement) {
  if (!manifest) return;
  const hash = manifest.pages[Number(el.dataset.page) - 1];
  if (!hash) return;
  if (el.dataset.svg === hash) return;
  el.dataset.svg = hash;
  const text = await fetchPage(hash);
  if (el.dataset.svg !== hash) return; // unmounted or replaced meanwhile
  el.innerHTML = text;
  addOverflowBar(el);
}

/** Dev server: a step that overflows (`data-overflow`, set by extras.tsx)
 *  gets a thin bar at its bottom; hovering it shows the details. Re-added
 *  each time the page's SVG is mounted (which replaces the page's children). */
export function addOverflowBar(el: HTMLElement) {
  el.querySelector(":scope > .overflow-bar")?.remove();
  if (!el.dataset.overflow) return;
  const bar = document.createElement("div");
  bar.className = "overflow-bar";
  bar.textContent = el.dataset.overflow;
  el.append(bar);
}

export function unmountSvgPage(el: HTMLElement) {
  delete el.dataset.svg;
  el.replaceChildren();
}


// internal links of typst.ts's SVG: <a onclick="handleTypstLocation(this, page, x, y)">
(window as any).handleTypstLocation = (_el: Element, page: number) => followLink(page);

// Copy: typst.ts's text is a block (`.tsel` div) per run of text, so the
// browser puts a line break between every two pieces, even on the same line.
// Joined here instead: a space between pieces of the same line that are
// apart, nothing if they touch, a line break between lines.
document.addEventListener("copy", (e) => {
  const sel = getSelection();
  if (!sel?.rangeCount || !e.clipboardData) return;
  const range = sel.getRangeAt(0);
  const host = range.commonAncestorContainer;
  const el = host instanceof Element ? host : host.parentElement;
  if (!el?.closest(".reveal .slides")) return;
  // (the step pages hidden under the one shown are left out)
  const pieces = [...el.querySelectorAll<HTMLElement>(".tsel")].filter(
    (d) => range.intersectsNode(d) && d.checkVisibility({ visibilityProperty: true }),
  );
  if (pieces.length < 2) return;
  let text = "";
  let last: DOMRect | null = null;
  for (const d of pieces) {
    const r = document.createRange();
    r.selectNodeContents(d);
    if (range.compareBoundaryPoints(Range.START_TO_START, r) > 0) r.setStart(range.startContainer, range.startOffset);
    if (range.compareBoundaryPoints(Range.END_TO_END, r) < 0) r.setEnd(range.endContainer, range.endOffset);
    const piece = r.toString();
    if (!piece) continue;
    // the box of the piece: its foreignObject (the div is `position: fixed`)
    const box = (d.parentElement ?? d).getBoundingClientRect();
    if (last) {
      const mid = (box.top + box.bottom) / 2;
      const sameLine = mid > last.top && mid < last.bottom;
      if (!sameLine) text += "\n";
      else if (box.left - last.right > 0.15 * box.height && !/\s$/.test(text) && !/^\s/.test(piece)) text += " ";
    }
    text += piece;
    last = box;
  }
  e.clipboardData.setData("text/plain", text);
  e.preventDefault();
});
