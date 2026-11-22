import Reveal from "reveal.js";
import "reveal.js/dist/reveal.css";
import "reveal.js-plugins/chalkboard/plugin.js"; // sets window.RevealChalkboard
import "reveal.js-plugins/chalkboard/style.css";
import React from "react";
import { createRoot, Root } from "react-dom/client";
// the course's widgets (widgets.js, built from its widgets/index.ts)
import { loadCourseWidgets } from "./course-widgets";
import { EditChain, editUrl, index, openApp, Outline, StructureBrowser } from "./StructureBrowser";
import "./structure-browser.css";
import { Help, loadDocs } from "./Help";
import { openAnnotEditor } from "./AnnotEditor";
import { initMorph, morphUpdate } from "./morph";
import { devEvent, editWork, initExtras } from "./extras";
import { t } from "./i18n";
import { showLoading } from "./toasts";
import { SvgObject } from "./engine-widgets";
import { loadSvgManifest, mountSvgPage, unmountSvgPage } from "./svg-pages";
import { applyShown, flash, initSlideTypes, initTodoMask, isTodoMasked, removeHidden, toggleTodoMask } from "./slide-types";

showLoading();

// Registry: Typst `interactive("<id>", props: …)` -> React component, and for
// an animation the number of steps it needs for given props (Reveal fragments).
export type Widget = { component: React.FC<any>; steps?: (props: any) => number };
const widgets: Record<string, Widget> = {
  ...((await loadCourseWidgets()) as Record<string, Widget>),
  // #todo("…") on the web (lib/slides.typ): hidden by M
  "todo-note": { component: TodoNote },
  // #svg-object(…): an SVG with its links, hover and scripts (engine-widgets.tsx)
  "svg-object": { component: SvgObject },
};

// kind: "todo" (red, 🚧) or "check" (#to-check: amber, 👀)
function TodoNote({ note, kind }: { note: string; kind?: string }) {
  const check = kind === "check";
  const dev = document.body.dataset.dev === "true";
  const color = check ? "#a35a00" : "#cc0000";
  return (
    <div style={{ display: "flex", justifyContent: "flex-end" }}>
      <span
        // dev server: a click changes the work state (shift-W, extras.tsx)
        onClick={dev ? (e) => editWork(Number((e.currentTarget.closest("section[data-g]") as HTMLElement)?.dataset.g)) : undefined}
        title={dev ? t("work.title") + " (shift-W)" : undefined}
        style={{ cursor: dev ? "pointer" : undefined, background: check ? "#fff6e0" : "#fff0f0", border: `1px solid ${color}`, borderRadius: 3, padding: "1px 5px", color, fontSize: 11, whiteSpace: "nowrap" }}>
        {check ? "👀" : "🚧"} {note}
      </span>
    </div>
  );
}

// The pages: inline SVG (svg-pages.ts), the files build.mjs writes
const svgManifest = await loadSvgManifest(document.body.dataset.version!);
if (!svgManifest) throw new Error("svg.json: the deck's pages are missing (build it again)");
const first = { width: svgManifest.w, height: svgManifest.h };

// ---------------------------------------------------------------- pages
// Pages are mounted around the current slide and unmounted far from it: an
// SVG page is DOM (about a thousand nodes), not a picture.
const mountedPages = new Set<HTMLElement>();
function mountPage(el: HTMLElement) {
  mountedPages.add(el);
  return mountSvgPage(el);
}
function unmountPage(el: HTMLElement) {
  if (!mountedPages.delete(el)) return;
  unmountSvgPage(el);
}
// The leaf slides (a main section is a vertical stack of them), in deck order;
// `data-g` is the slide's group index, the key of the outline.
const leaves = (root: ParentNode = document.querySelector(".reveal .slides")!) => [
  ...root.querySelectorAll<HTMLElement>("section[data-g]"),
];
const pagesOf = (leaf: HTMLElement) => [...leaf.querySelectorAll<HTMLElement>(":scope > .page")];
// the leaves around leaf i whose pages stay mounted
const NEAR = (j: number, i: number) => j >= i - 3 && j <= i + 4;

// Mount the current slide and its neighbours in deck order (all step pages),
// unmount the pages far from here (the overview keeps those on screen).
function renderAround(current: HTMLElement | undefined = deck?.getCurrentSlide() as HTMLElement) {
  const all = leaves();
  const i = Math.max(0, all.indexOf(current));
  for (const j of [i, i + 1, i - 1, i + 2]) if (all[j]) pagesOf(all[j]).forEach((el) => mountedPages.has(el) || mountPage(el));
  if (overview) return;
  all.forEach((leaf, j) => NEAR(j, i) || pagesOf(leaf).forEach(unmountPage));
}

// Overview (Esc): only the slides on screen (or close to it) get a page, the
// step shown; those that leave the screen are unmounted again. 179 pages
// mounted at once would be ~170k DOM nodes.
let overview: IntersectionObserver | null = null;
const shownPage = (leaf: HTMLElement) =>
  pagesOf(leaf).filter((p, k) => k === 0 || p.classList.contains("visible")).at(-1);
function showOverview() {
  overview?.disconnect();
  overview = new IntersectionObserver(
    (entries) => {
      const all = leaves();
      const i = all.indexOf(deck.getCurrentSlide());
      for (const e of entries) {
        const leaf = e.target as HTMLElement;
        if (e.isIntersecting) {
          const el = shownPage(leaf);
          if (el && !mountedPages.has(el)) mountPage(el);
        } else if (!NEAR(all.indexOf(leaf), i)) pagesOf(leaf).forEach(unmountPage);
      }
    },
    { rootMargin: "25%" },
  );
  leaves().forEach((leaf) => overview!.observe(leaf));
}
function hideOverview() {
  overview?.disconnect();
  overview = null;
  renderAround();
}

// --------------------------------------------------------------- widgets
// Widget slots carry only `data-widget` (component) and `data-key`; position
// and props come from the layout map, so they can change without remounting.
// Animated widgets re-render with `step` = number of their step fragments
// currently shown, so they follow Reveal navigation (incl. ←).
type Layout = Record<string, { x: number; y: number; w: number; h: number; props: any }>;
let layout: Layout = JSON.parse(document.getElementById("widget-layout")!.textContent!);
const mounted = new Map<string, { el: HTMLElement; root: Root; update: () => void }>();

function applyLayout(el: HTMLElement) {
  const l = layout[el.dataset.key!];
  if (l) Object.assign(el.style, { left: `${l.x}px`, top: `${l.y}px`, width: `${l.w}px`, height: `${l.h}px` });
}

// Mount the slots under `container`; a slot whose key is already mounted is
// replaced by the live node, so the component keeps its state.
// the snapshot page's readiness signal (src/snapshot.tsx): nothing to wait for here
const noop = () => {};
function mountWidgets(container: ParentNode) {
  for (const slot of container.querySelectorAll<HTMLElement>("[data-widget]")) {
    const key = slot.dataset.key!;
    let entry = mounted.get(key);
    if (entry && entry.el !== slot) slot.replaceWith(entry.el);
    if (!entry) {
      const entry0 = widgets[slot.dataset.widget!];
      if (!entry0) continue;
      const Component = entry0.component;
      const root = createRoot(slot);
      const update = () => {
        const steps = slot.parentElement?.querySelectorAll(`.widget-step[data-for="${key}"]`) ?? [];
        const step = [...steps].filter((s) => s.classList.contains("visible")).length;
        root.render(<Component {...(layout[key]?.props ?? {})} step={step} onReady={noop} />);
      };
      mounted.set(key, (entry = { el: slot, root, update }));
    }
    applyLayout(entry.el);
    const reg = widgets[slot.dataset.widget!];
    const section = (entry.el.parentElement ?? slot.parentElement)!;
    if (reg?.steps && !section.querySelector(`.widget-step[data-for="${key}"]`)) {
      const n = reg.steps(layout[key]?.props ?? {});
      for (let i = 0; i < n; i++) {
        const span = document.createElement("span");
        span.className = "fragment widget-step";
        span.dataset.for = key;
        section.append(span);
      }
    }
  }
  // widgets that disappeared from the deck
  for (const [key, { el, root }] of mounted)
    if (!el.isConnected && !container.contains(el)) {
      root.unmount();
      mounted.delete(key);
    }
}
const updateWidgets = () => mounted.forEach((m) => m.update());

// ----------------------------------------------------------------- Reveal
// The slide size is the Typst page size: Reveal scales it as one unit, so the
// rendered pages, text layers, widget overlays and chalkboard stay aligned.
// M (todo markers) and the slide types left out (T, ?show= / ?hide=), before
// Reveal counts the slides
initTodoMask();
initSlideTypes();
removeHidden(document.querySelector(".reveal .slides")!);
mountWidgets(document.querySelector(".reveal .slides")!);
// eslint-disable-next-line prefer-const
let deck: any;
deck = new Reveal({
  width: first.width,
  height: first.height,
  margin: 0,
  center: false,
  hash: true,
  transition: "none",
  controls: false,
  plugins: [(window as any).RevealChalkboard],
  // @ts-ignore plugin option
  chalkboard: {
    storage: "typst-proto-chalkboard", // sessionStorage: survives JS reloads too
    toggleNotesButton: false,
    toggleChalkboardButton: false,
    transition: 0,
    chalkWidth: 3,
  },
});
deck.on("ready", (e: any) => renderAround(e.currentSlide));
deck.on("slidechanged", (e: any) => renderAround(e.currentSlide));
deck.on("overviewshown", showOverview);
deck.on("overviewhidden", hideOverview);
for (const ev of ["fragmentshown", "fragmenthidden", "slidechanged", "ready"]) deck.on(ev, updateWidgets);
await deck.initialize();
// animated transitions between the step pages of morphing figures (morph.ts)
initMorph(deck, document.body.dataset.version!);

// ------------------------------------------------- outline: T, E, shift-E
let outline: Outline = JSON.parse(document.getElementById("deck-outline")!.textContent!);
let outlineIndex = index(outline);
const setOutline = (o: Outline) => {
  outline = o;
  outlineIndex = index(o);
};

/** Show leaf slide `g` (at fragment `f`). */
function goTo(g: number, f?: number) {
  const leaf = document.querySelector<HTMLElement>(`.reveal .slides section[data-g="${g}"]`);
  if (!leaf) return;
  const { h, v } = deck.getIndices(leaf);
  deck.slide(h, v, f);
  renderAround(leaf);
}

/** Group index, in outline `next`, of the slide that is `g` in the current outline. */
function sameSlide(g: number, next: Outline | null): number | null {
  const node = outlineIndex.byG.get(g);
  if (!next || !node?.src) return null;
  const nodes = index(next).order.filter((n) => n.src?.file === node.src!.file && n.kind === node.kind);
  const exact = nodes.filter((n) => n.title === node.title);
  if (exact.length) return exact.reduce((a, b) => (Math.abs(b.src!.line - node.src!.line) < Math.abs(a.src!.line - node.src!.line) ? b : a)).g;
  const above = nodes.filter((n) => n.src!.line <= node.src!.line).at(-1);
  return above?.g ?? null;
}

const currentG = () => Number((deck.getCurrentSlide() as HTMLElement)?.dataset.g ?? 0);
const panelHost = document.body.appendChild(document.createElement("div"));
const panel = createRoot(panelHost);
let panelOpen = false;
function closePanel() {
  panel.render(null);
  // after the key that closed the panel (Esc, H…) is done: it must not reach
  // Reveal (Esc = overview, H = previous slide or the help again)
  setTimeout(() => {
    panelOpen = false;
    deck.configure({ keyboard: true });
  });
}
function openPanel(content: React.ReactElement) {
  panelOpen = true;
  deck.configure({ keyboard: false }); // no key reaches the deck meanwhile
  panel.render(content);
}

// H: the authoring documentation, in the dev server (as in slide-app). A Reveal
// binding, since Reveal's own H (previous slide) would run first otherwise.
if (outline.root)
  deck.addKeyBinding({ keyCode: 72, key: "H", description: t("key.help") }, () => {
    if (!panelOpen) loadDocs().then(() => panelOpen || openPanel(<Help onClose={closePanel} />));
  });

window.addEventListener("keydown", (e) => {
  if (panelOpen || e.metaKey || e.ctrlKey || e.altKey) return;
  if ((e.target as HTMLElement).closest?.("input, textarea, [contenteditable]")) return;
  if (e.key === "t" || e.key === "T") {
    e.preventDefault();
    openPanel(
      <StructureBrowser
        outline={outline}
        current={currentG()}
        todoMasked={isTodoMasked()}
        onTypes={applyShown}
        onGo={(g) => {
          closePanel();
          goTo(g);
        }}
        onClose={closePanel}
      />,
    );
  } else if (e.key === "m" || e.key === "M") {
    e.preventDefault();
    flash(toggleTodoMask() ? t("todo.hidden") : t("todo.shown"));
  } else if (e.key === "H" && e.shiftKey) {
    // shift-H: back to the course index, the parent of the deck's directory
    // (a deck served alone, at the root, has none)
    if (location.pathname.replace(/\/[^/]*$/, "") === "") return;
    e.preventDefault();
    location.href = new URL("../", location.href).href;
  } else if (e.key === "E" && e.shiftKey && outline.root) {
    // shift-E: the #include chain to the slide (Reveal drops shift-modified
    // keys, hence not a Reveal binding)
    const node = outlineIndex.byG.get(currentG());
    if (!node?.src) return;
    e.preventDefault();
    openPanel(<EditChain outline={outline} node={node} onClose={closePanel} />);
  } else if (e.key === "O" && e.shiftKey && document.body.dataset.dev === "true") {
    // shift-O (dev server): move an annotation's label, written back into the
    // source (AnnotEditor.tsx, POST annot in build.mjs)
    e.preventDefault();
    panelOpen = true;
    deck.configure({ keyboard: false });
    openAnnotEditor({
      section: deck.getCurrentSlide() as HTMLElement,
      scale: () => deck.getScale(),
      flash,
      onClose: () =>
        setTimeout(() => {
          panelOpen = false;
          deck.configure({ keyboard: true });
        }),
    });
  }
});

// E: the slide's source in VS Code. A Reveal binding registered after
// initialize(), so that it replaces the chalkboard's own E (clear the board).
if (outline.root)
  deck.addKeyBinding({ keyCode: 69, key: "E", description: t("key.edit") }, () => {
    const node = outlineIndex.byG.get(currentG());
    if (node?.src && outline.root) openApp(editUrl(outline.root, node.src));
  });

// "in detail" slides, O (overflows), Z (Zotero), toasts (extras.tsx)
initExtras({
  deck,
  outline: () => outline as any,
  goTo,
  currentG,
  openPanel,
  closePanel,
  panelOpen: () => panelOpen,
  flash,
  openApp,
  editUrl,
});

// ------------------------------------------------------------- dev: live
type DevMsg =
  | { type: "update"; version: number; changed: number[]; skeleton: boolean; layout: Layout | null; outline: Outline | null }
  | { type: "goto"; g: number }
  | { type: "errors"; errors: string[] }
  | { type: "reload" }
  | { type: "hello"; boot: string }; // sent on (re)connection: which server

async function applyUpdate(msg: Extract<DevMsg, { type: "update" }>) {
  const t0 = performance.now();
  await loadSvgManifest(msg.version);
  if (msg.layout) layout = msg.layout;

  if (msg.skeleton) {
    // Slide structure changed (slides or steps added/removed): build the new
    // <section>s off-screen, pre-render the pages around the current position,
    // then swap them in, move the live widgets over and let Reveal re-read.
    const { f } = deck.getIndices();
    const g = currentG();
    const fresh = document.createElement("div");
    fresh.innerHTML = await (await fetch(`slides.html?v=${msg.version}`)).text();
    removeHidden(fresh);
    const freshLeaves = leaves(fresh);
    // stay on the same slide, not the same index: same file and title in the
    // new outline, else the nearest one above in that file (or the next shown)
    const want = sameSlide(g, msg.outline) ?? g;
    const next = freshLeaves.findIndex((l) => Number(l.dataset.g) >= want);
    const at = next >= 0 ? next : freshLeaves.length - 1;
    const target = Number(freshLeaves[at]?.dataset.g ?? 0);
    await Promise.all(
      [at - 1, at, at + 1].flatMap((i) =>
        [...(freshLeaves[i]?.querySelectorAll<HTMLElement>(".page") ?? [])].map(mountPage),
      ),
    );
    // the pages of the old sections are gone
    for (const el of mountedPages) if (!fresh.contains(el)) mountedPages.delete(el);
    mountWidgets(fresh);
    document.querySelector(".reveal .slides")!.replaceChildren(...fresh.children);
    deck.sync();
    goTo(target, f);
  } else {
    // Same structure: the mounted pages take their new SVG (a page whose
    // hash did not change is left as it is; the others are mounted lazily)
    await Promise.all([...mountedPages].map(mountSvgPage));
    if (msg.layout) mounted.forEach(({ el }) => applyLayout(el));
  }
  morphUpdate(msg.version);
  if (msg.outline) {
    setOutline(msg.outline);
    devEvent({ type: "outline" });
  }
  updateWidgets();
  console.log(
    `[typst] v${msg.version}: ${msg.skeleton ? "structure" : `pages ${msg.changed.join(",") || "-"}`}` +
      `${msg.layout ? " + widget layout" : ""} updated in ${(performance.now() - t0).toFixed(0)} ms`,
  );
}

if (document.body.dataset.dev === "true") {
  const errorBox = document.getElementById("typst-errors")!;
  let queue = Promise.resolve();
  // relative: the deck may be served under a path (slide-app's dev server
  // forwards /<id>/ to this one)
  let boot: string | null = null;
  const onMessage = (e: MessageEvent) => {
    const msg: DevMsg = JSON.parse(e.data);
    if (msg.type === "hello") {
      // reconnected to another server (restarted when its code changed):
      // its pages and state may differ from what this page was built from
      if (boot && boot !== msg.boot) location.reload();
      boot = msg.boot;
      devEvent({ type: "connected" });
    } else if (msg.type === "reload") location.reload();
    else if (msg.type === "errors") {
      errorBox.textContent = msg.errors.join("\n\n");
      devEvent({ type: "errors", n: msg.errors.length });
    }
    else if (msg.type === "goto") goTo(msg.g);
    else queue = queue.then(() => applyUpdate(msg)).catch((err) => console.error(err));
  };
  // The browser reconnects by itself after a dropped connection, but gives
  // up for good on an error answer (the server restarting behind slide-app's
  // proxy): open a new one then, until the server is back (its `hello`
  // reloads the page if it is another server).
  const listen = () => {
    const events = new EventSource("events");
    events.onmessage = onMessage;
    events.onerror = () => {
      devEvent({ type: "disconnected" });
      if (events.readyState === EventSource.CLOSED) setTimeout(listen, 1000);
    };
  };
  listen();
}
