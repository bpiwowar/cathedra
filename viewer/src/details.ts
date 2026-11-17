// "In detail" slides in the viewer (slide-app's src/details.ts, for the
// Typst engine; authoring: `#details` / `#details-link`, lib/slides.typ).
//
// The groups are laid out by Typst in an appendix section at the end of the
// deck; each page marker says which group a page is in (outline nodes:
// `details`: the group id, "" on the appendix's title card, null in the
// talk), and outline.details gives each group's card and the slides linking
// to it. Here:
// - internal links (a `#details-link`, the "back to slide" link in the
//   footer of a details slide) move the deck: a link into a group remembers
//   where the talk was (slide and step); a link back, Esc or I return there;
// - I on a slide with a details link opens it (a picker when there are several);
// - the talk does not walk into the details, nor a group into the next one
//   (→ ↓ space… hold and say so); `T`, the overview, links get there;
// - a group's slides have a coloured bar on the left.
import { t } from "./i18n";

type Outline = {
  details?: Record<string, { g: number; refs: number[] }>;
  children: any[];
};
type Pos = { g: number; f: number };

export type DetailsContext = {
  deck: any; // Reveal
  outline: () => Outline;
  goTo: (g: number, f?: number) => void;
  currentG: () => number;
  // title and number of slide g (pickers)
  slideLabel: (g: number) => string;
  pick: (title: string, items: string[], onPick: (i: number) => void) => void;
  panelOpen: () => boolean;
  flash: (msg: string) => void;
};

let ctx: DetailsContext;
let stack: Pos[] = [];
let returning = false;

const leaves = () => [...document.querySelectorAll<HTMLElement>(".reveal .slides section[data-g]")];

// the node of slide g (the leaf node: deepest with that g)
function nodeOf(g: number): any {
  let found: any = null;
  const walk = (n: any) => {
    if (n.g === g) found = n;
    n.children?.forEach(walk);
  };
  ctx.outline().children.forEach(walk);
  return found;
}
/** The group of slide g: its id, "" (the appendix's card), null (the talk). */
export const zoneOf = (g: number): string | null => nodeOf(g)?.details ?? null;
const inGroup = (z: string | null) => z != null && z !== "";

/** Slide and step of page `page` in the deck (null if not in it). */
function posOfPage(page: number): Pos | null {
  const el = document.querySelector<HTMLElement>(`.reveal .slides section[data-g] > .page[data-page="${page}"]`);
  const section = el?.parentElement as HTMLElement | undefined;
  if (!el || !section) return null;
  const pages = [...section.querySelectorAll(":scope > .page")];
  return { g: Number(section.dataset.g), f: pages.indexOf(el) - 1 };
}
const here = (): Pos => ({ g: ctx.currentG(), f: ctx.deck.getIndices().f ?? -1 });

function go(p: Pos) {
  ctx.goTo(p.g, p.f);
}

/** Open group `id`, remembering where the talk is. */
export function enter(id: string) {
  const d = ctx.outline().details?.[id];
  if (!d) return;
  stack.push(here());
  go({ g: d.g, f: -1 });
}

/** Back from a group: to where it was opened, else to a slide linking to it. */
export function back() {
  const z = zoneOf(ctx.currentG());
  const saved = stack.pop();
  if (saved) {
    returning = true;
    go(saved);
    returning = false;
    return;
  }
  const refs = (z && ctx.outline().details?.[z]?.refs) || [];
  if (refs.length === 1) go({ g: refs[0], f: -1 });
  else if (refs.length > 1)
    ctx.pick(t("details.pickBack"), refs.map(ctx.slideLabel), (i) => go({ g: refs[i], f: -1 }));
}

/** An internal link of a page was clicked (svg-pages.ts): it goes to page `page`. */
export function followLink(page: number) {
  const target = posOfPage(page);
  if (!target) return;
  const from = zoneOf(ctx.currentG());
  const to = zoneOf(target.g);
  const top = stack.at(-1);
  if (top && inGroup(from) && to !== from && zoneOf(top.g) === to) back();
  else if (inGroup(to) && to !== from) {
    stack.push(here());
    go(target);
  } else go(target);
}

// ------------------------------------------------------------------ keys
// The slide a key would move to (null: a step of this slide, or nowhere).
function target(key: string, shift: boolean): { el: HTMLElement; forward: boolean } | null {
  const all = leaves();
  const cur = ctx.deck.getCurrentSlide() as HTMLElement;
  const i = all.indexOf(cur);
  const frags = ctx.deck.availableFragments();
  const k = key.length === 1 ? key.toLowerCase() : key;
  const linearNext = (k === " " && !shift) || k === "n" || k === "PageDown";
  const linearPrev = (k === " " && shift) || k === "p" || k === "PageUp";
  const right = k === "ArrowRight" || k === "l";
  const left = k === "ArrowLeft";
  const down = k === "ArrowDown" || k === "j";
  const up = k === "ArrowUp" || k === "k";
  const forward = linearNext || right || down;
  if (!forward && !linearPrev && !left && !up) return null;
  if (forward ? frags.next : frags.prev) return null;
  const stacks = [...document.querySelectorAll<HTMLElement>(".reveal .slides > section")];
  const first = (s: HTMLElement | undefined) => (s?.matches("[data-g]") ? s : s?.querySelector<HTMLElement>("section[data-g]"));
  let el: HTMLElement | null | undefined = null;
  if (linearNext) el = all[i + 1];
  else if (linearPrev) el = all[i - 1];
  else if (right || left) {
    const h = ctx.deck.getIndices().h;
    el = first(stacks[h + (right ? 1 : -1)]);
  } else {
    const sibs = cur.parentElement?.matches("section:not([data-g])")
      ? [...cur.parentElement.querySelectorAll<HTMLElement>(":scope > section[data-g]")]
      : [cur];
    el = sibs[sibs.indexOf(cur) + (down ? 1 : -1)];
  }
  return el ? { el, forward } : null;
}

function onKey(e: KeyboardEvent) {
  if (ctx.panelOpen() || e.metaKey || e.ctrlKey || e.altKey) return;
  if ((e.target as HTMLElement).closest?.("input, textarea, [contenteditable]")) return;
  if (ctx.deck.isOverview?.()) return;
  const zone = zoneOf(ctx.currentG());
  const stop = () => {
    e.preventDefault();
    e.stopImmediatePropagation();
  };
  // I: open the slide's details, or go back; Esc: back, in a group
  if ((e.key === "i" || e.key === "I") && !e.shiftKey) {
    stop();
    if (inGroup(zone)) return back();
    const g = ctx.currentG();
    const ids = Object.entries(ctx.outline().details ?? {})
      .filter(([, d]) => d.refs.includes(g))
      .map(([id]) => id);
    if (ids.length === 1) enter(ids[0]);
    else if (ids.length > 1)
      ctx.pick(t("details.pickOpen"), ids.map((id) => ctx.slideLabel(ctx.outline().details![id].g)), (i) => enter(ids[i]));
    else ctx.flash(t("details.none"));
    return;
  }
  if (e.key === "Escape" && inGroup(zone)) {
    stop();
    return back();
  }
  // the walls: the end of the talk, the ends of a group
  if (zone === "") return; // the appendix's title card: free
  const to = target(e.key, e.shiftKey);
  if (!to) return;
  const next = zoneOf(Number(to.el.dataset.g));
  if (next === zone) return;
  if (zone == null && !to.forward) return;
  stop();
  ctx.flash(t(zone == null ? "details.endTalk" : to.forward ? "details.endGroup" : "details.startGroup"));
}

const STYLE = `
.reveal .slides section[data-types~="details"]::before { content: ""; position: absolute;
  left: 0; top: 0; bottom: 0; width: 5px; background: #6366f1; z-index: 4; pointer-events: none; }
`;

export function initDetails(c: DetailsContext) {
  ctx = c;
  const style = document.createElement("style");
  style.textContent = STYLE;
  document.head.append(style);
  // before Reveal's own handler (document, bubbling)
  window.addEventListener("keydown", onKey, true);
  // back in the talk by other means (T, overview, hash): the digression is over
  ctx.deck.on("slidechanged", () => {
    if (!returning && zoneOf(ctx.currentG()) == null) stack = [];
  });
}
