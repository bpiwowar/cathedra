// Slide types and work-in-progress markers, as in slide-app
// (slide-app/src/slide-types.ts and todo-mask.ts).
//
// - M hides the todo markers (the red frame, the 🚧 note, the structure
//   browser's todo badges) and shows them again. The choice is remembered;
//   `?todo=0` / `?todo=1` in the URL starts masked / marked.
// - A slide type (todo, optional, practical) can be left out of the deck:
//   checkboxes in the structure browser (T), or `?show=a,b` / `?hide=a` in the
//   URL, which beat what the browser remembered (per deck). A change reloads.
//   Hidden slides are removed before Reveal starts (and from a live update's
//   new sections), so numbering and navigation skip them.

export const SLIDE_TYPES: Record<string, { label: string; icon: string; show: boolean }> = {
  todo: { label: "work in progress", icon: "🚧", show: true },
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
export const isShown = (type: string) => overrides[type] ?? SLIDE_TYPES[type]?.show ?? true;
export const hiddenTypes = () => Object.keys(SLIDE_TYPES).filter((t) => !isShown(t));

/** Remove the leaf slides of hidden types under `root` (and stacks left empty); returns the removed g. */
export function removeHidden(root: ParentNode): Set<number> {
  const removed = new Set<number>();
  root.querySelectorAll<HTMLElement>("section[data-types]").forEach((el) => {
    if (el.dataset.types!.split(" ").some((t) => !isShown(t))) {
      removed.add(Number(el.dataset.g));
      el.remove();
    }
  });
  root.querySelectorAll<HTMLElement>("section:not([data-g])").forEach((stack) => {
    if (!stack.querySelector("section[data-g]")) stack.remove();
  });
  return removed;
}

/** Show or hide types, remember it for this deck, and reload (on the same hash). */
export function applyShown(choice: Record<string, boolean>) {
  const stored = { ...read<Record<string, boolean>>(typesKey(), {}), ...fromUrl(), ...choice };
  for (const [t, v] of Object.entries(stored)) if ((SLIDE_TYPES[t]?.show ?? true) === v) delete stored[t];
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
