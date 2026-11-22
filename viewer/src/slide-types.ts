// Slide types and work-in-progress markers, as in slide-app
// (slide-app/src/slide-types.ts and todo-mask.ts).
//
// - M hides the todo and to-check markers (the red / amber frame, the 🚧 note, the structure
//   browser's todo badges) and shows them again. The choice is remembered;
//   `?todo=0` / `?todo=1` in the URL starts masked / marked.
// - A slide type (todo, optional, practical, main) can be left out of the deck:
//   checkboxes in the structure browser (T), or `?show=a,b` / `?hide=a` in the
//   URL, which beat what the browser remembered (per deck). A change reloads.
//   Hidden slides are removed before Reveal starts (and from a live update's
//   new sections), so numbering and navigation skip them, and so do the
//   (sub)sections they leave empty, unless "empty sections" is ticked
//   (`?show=empty`).

export const SLIDE_TYPES: Record<string, { label: string; icon: string; show: boolean }> = {
  // a slide with no other type (title and section pages are never left out)
  main: { label: "main", icon: "▪", show: true },
  todo: { label: "work in progress", icon: "🚧", show: true },
  check: { label: "to check", icon: "👀", show: true },
  optional: { label: "optional", icon: "◇", show: true },
  practical: { label: "practical", icon: "💻", show: true },
  // the slides of the "in detail" appendix (#details)
  details: { label: "in detail", icon: "🔍", show: true },
};

const MASK_KEY = "typst-slides.todo-masked";
const typesKey = () => "typst-slides.slide-types:" + window.location.pathname;

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}
function write(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* not fatal: the choice just does not survive a reload */
  }
}

// ------------------------------------------------------------- todo mask
let masked = false;

export function initTodoMask() {
  const v = new URLSearchParams(window.location.search).get("todo");
  masked = v !== null ? /^(0|no|off|false|hidden)$/i.test(v) : read(MASK_KEY, false) === true;
  document.body.classList.toggle("todo-masked", masked);
}
export const isTodoMasked = () => masked;
export function toggleTodoMask() {
  masked = !masked;
  document.body.classList.toggle("todo-masked", masked);
  write(MASK_KEY, masked);
  return masked;
}

// ---------------------------------------------------------- slide types
let overrides: Record<string, boolean> = {};

function fromUrl() {
  const params = new URLSearchParams(window.location.search);
  const out: Record<string, boolean> = {};
  for (const [param, shown] of [["show", true], ["hide", false]] as const)
    for (const value of params.getAll(param))
      for (const name of value.split(",").map((s) => s.trim()).filter(Boolean)) out[name] = shown;
  return out;
}

export function initSlideTypes() {
  overrides = { ...read<Record<string, boolean>>(typesKey(), {}), ...fromUrl() };
}
// options stored with the types: "empty" keeps the sections whose slides are
// all left out (off by default: they go too)
const OPTION_DEFAULTS: Record<string, boolean> = { empty: false };
const byDefault = (type: string) => SLIDE_TYPES[type]?.show ?? OPTION_DEFAULTS[type] ?? true;
export const isShown = (type: string) => overrides[type] ?? byDefault(type);
/** Whether the sections left empty by the hidden types go too. */
export const dropEmpty = () => !isShown("empty");
/** A slide's types, "main" when it has none (title and section pages: none). */
export const typesOf = (n: { kind: string; types: string[] }) =>
  n.kind === "slide" && n.types.length === 0 ? ["main"] : n.types;
export const hiddenTypes = () => Object.keys(SLIDE_TYPES).filter((t) => !isShown(t));

/** Remove the leaf slides of hidden types under `root`, the (sub)sections
 *  they leave empty (unless kept), and the stacks left empty; returns the removed g. */
export function removeHidden(root: ParentNode): Set<number> {
  const removed = new Set<number>();
  // the section / subsection pages open at each leaf, with their slide counts
  const open: { el: HTMLElement; level: number; total: number; kept: number }[] = [];
  const headings: typeof open = [];
  root.querySelectorAll<HTMLElement>("section[data-g]").forEach((el) => {
    const level = el.dataset.level;
    if (level !== undefined) {
      const lv = Number(level);
      while (open.length && open[open.length - 1].level >= lv) open.pop();
      if (lv > 0) {
        const h = { el, level: lv, total: 0, kept: 0 };
        open.push(h);
        headings.push(h);
      }
      return;
    }
    const hidden = (el.dataset.types ?? "").split(" ").some((t) => t && !isShown(t));
    for (const h of open) {
      h.total++;
      if (!hidden) h.kept++;
    }
    if (hidden) {
      removed.add(Number(el.dataset.g));
      el.remove();
    }
  });
  if (dropEmpty())
    for (const h of headings)
      if (h.total > 0 && h.kept === 0) {
        removed.add(Number(h.el.dataset.g));
        h.el.remove();
      }
  root.querySelectorAll<HTMLElement>("section:not([data-g])").forEach((stack) => {
    if (!stack.querySelector("section[data-g]")) stack.remove();
  });
  return removed;
}

/** Show or hide types, remember it for this deck, and reload (on the same hash). */
export function applyShown(choice: Record<string, boolean>) {
  const stored = { ...read<Record<string, boolean>>(typesKey(), {}), ...fromUrl(), ...choice };
  for (const [t, v] of Object.entries(stored)) if (byDefault(t) === v) delete stored[t];
  write(typesKey(), stored);
  const url = new URL(window.location.href);
  url.searchParams.delete("show");
  url.searchParams.delete("hide");
  if (url.toString() === window.location.href) window.location.reload();
  else window.location.replace(url.toString());
}

// ----------------------------------------------------------------- toast
let flashTimer: number | undefined;
export function flash(message: string) {
  let el = document.getElementById("flash");
  if (!el) {
    el = document.body.appendChild(document.createElement("div"));
    el.id = "flash";
  }
  el.textContent = message;
  el.classList.add("on");
  window.clearTimeout(flashTimer);
  flashTimer = window.setTimeout(() => el!.classList.remove("on"), 1600);
}
