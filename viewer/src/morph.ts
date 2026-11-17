// Animated transitions between the step pages of a slide whose figure has
// morphing parts (`#morph("id", …)`, lib/morph.typ; docs/figures.md).
//
// build.mjs writes morph.json ({page: {id: [x0, y0, x1, y1]}}, in pt). Going
// from step page A to the next (or back), an overlay covers the slide for the
// transition, made of copies of the pages' SVG elements (morph-svg.ts): each
// part moves and resizes from its box on A to its box on B (FLIP), a part on
// one page only fades in or out, the rest of the pages cross-fades.
// Then the overlay is removed and the real page B is there. Pages without
// parts switch instantly as before; so does everything under
// prefers-reduced-motion, a jump of several steps, or a page not mounted yet.

import { svgTransition } from "./morph-svg";

export type Box = [number, number, number, number];
type Boxes = Record<string, Record<string, Box>>; // page -> id -> box

const DURATION = 600; // ms
const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)");

let boxes: Boxes = {};
let running: Animation[] = [];
let overlay: HTMLElement | null = null;
let deck: any;

const hasParts = (page: number) => !!boxes[page] && Object.keys(boxes[page]).length > 0;

async function load(v: string) {
  try {
    const r = await fetch(`morph.json?v=${v}`);
    boxes = r.ok ? await r.json() : {};
  } catch {
    boxes = {};
  }
}

function stop() {
  const r = running;
  running = [];
  r.forEach((a) => a.finish());
  overlay?.remove();
  overlay = null;
}

// From step page `from` to step page `to` (elements of the same section).
function transition(fromEl: HTMLElement, toEl: HTMLElement) {
  stop();
  if (reduced?.matches) return;
  const a = Number(fromEl.dataset.page);
  const b = Number(toEl.dataset.page);
  if (!hasParts(a) && !hasParts(b)) return;
  const cfg = deck.getConfig();
  const r = svgTransition(fromEl, toEl, boxes[a] ?? {}, boxes[b] ?? {}, cfg.width, cfg.height, DURATION);
  if (r) start(toEl, r.layer, r.anims);
}

function start(toEl: HTMLElement, layer: HTMLElement, anims: Animation[]) {
  toEl.parentElement!.append(layer);
  overlay = layer;
  running = anims;
  Promise.all(anims.map((x) => x.finished))
    .then(() => {
      if (overlay === layer) stop();
    })
    .catch(() => {});
}

// Reveal shows / hides one step page: animate from the page shown before.
function onFragment(e: any, shown: boolean) {
  const pages = (e.fragments as HTMLElement[]).filter((f) => f.classList.contains("page"));
  if (pages.length !== 1) return stop(); // none, or a jump of several steps
  const el = pages[0];
  const prev = el.previousElementSibling as HTMLElement | null;
  if (!prev?.classList.contains("page")) return stop();
  if (shown) transition(prev, el);
  else transition(el, prev);
}

/** Set up the transitions on a Reveal deck, for the deck's `version`. */
export async function initMorph(revealDeck: any, v: string) {
  deck = revealDeck;
  deck.on("fragmentshown", (e: any) => onFragment(e, true));
  deck.on("fragmenthidden", (e: any) => onFragment(e, false));
  deck.on("slidechanged", stop);
  deck.on("overviewshown", stop);
  await load(v);
}

/** A live update (dev server): the deck is now at `version`. */
export async function morphUpdate(v: number | string) {
  stop();
  await load(String(v));
}
