// Viewer features added to main.tsx, kept apart from it: "in detail" slides
// (details.ts), O (the slides that overflow), W (the slides marked #todo /
// #to-check) and their work state (shift-W, a click on the note: written into
// the source by the dev server), Z (Zotero items of the slide),
// the interface language (i18n.ts) and toasts for the dev server
// (toasts.ts). main.tsx calls `initExtras` once Reveal is ready, and the
// dev-server hooks (`devEvent`) on its messages.
import React from "react";
import { initDetails } from "./details";
import { setLang, t } from "./i18n";
import { Picker } from "./Picker";
import { addOverflowBar } from "./svg-pages";
import { closeToast, loaded, toast } from "./toasts";
import { slideZoteroLinks } from "./zotero";

export type Overflow = { g: number; page: number; message: string };
type Node = { kind: string; title: string | null; g: number; slide: number; types?: string[]; src: { file: string; line: number } | null; children: Node[] };
type Outline = {
  title: string | null;
  root: string | null;
  lang?: string | null;
  overflows?: Overflow[];
  details?: Record<string, { g: number; refs: number[] }>;
  children: Node[];
};

export type ExtrasContext = {
  deck: any;
  outline: () => Outline;
  goTo: (g: number, f?: number) => void;
  currentG: () => number;
  openPanel: (content: React.ReactElement) => void;
  closePanel: () => void;
  panelOpen: () => boolean;
  flash: (msg: string) => void;
  openApp: (url: string) => void;
  editUrl: (root: string, src: { file: string; line: number }) => string;
};

// the language, as soon as the page is read (before any panel is drawn)
try {
  setLang(JSON.parse(document.getElementById("deck-outline")?.textContent ?? "{}").lang);
} catch {
  /* English */
}

let ctx: ExtrasContext;

function nodeOf(g: number): Node | null {
  let found: Node | null = null;
  const walk = (n: Node) => {
    if (n.g === g) found = n;
    n.children?.forEach(walk);
  };
  ctx.outline().children.forEach(walk);
  return found;
}
const slideLabel = (g: number) => {
  const n = nodeOf(g);
  return `${n?.slide ?? g}. ${n?.title ?? t("sb.untitled")}`;
};

function pick(title: string, items: string[], onPick: (i: number) => void) {
  ctx.openPanel(
    <Picker
      title={title}
      items={items.map((label) => ({ label }))}
      onPick={(i) => {
        ctx.closePanel();
        onPick(i);
      }}
      onClose={ctx.closePanel}
    />,
  );
}

/** Slide and step of a page of the deck. */
function stepOfPage(page: number) {
  const el = document.querySelector<HTMLElement>(`.reveal .slides section[data-g] > .page[data-page="${page}"]`);
  const section = el?.parentElement;
  if (!el || !section) return -1;
  return [...section.querySelectorAll(":scope > .page")].indexOf(el) - 1;
}

// ------------------------------------------------------------------- O
export function showOverflows() {
  const o = ctx.outline();
  // one row per slide (the first overflowing step)
  const seen = new Set<number>();
  const list = (o.overflows ?? []).filter((x) => !seen.has(x.g) && seen.add(x.g));
  const edit = (g: number) => {
    const src = nodeOf(g)?.src;
    if (src && o.root) ctx.openApp(ctx.editUrl(o.root, src));
  };
  ctx.openPanel(
    <Picker
      title={`${t("overflow.title")} (${list.length})`}
      empty={t("overflow.none")}
      help={t("overflow.help")}
      items={list.map((x) => {
        const n = nodeOf(x.g);
        return {
          label: slideLabel(x.g),
          detail: n?.src ? `${n.src.file}:${n.src.line}` : undefined,
          actions: o.root && n?.src ? [{ label: t("overflow.edit"), key: "e", run: () => edit(x.g) }] : [],
        };
      })}
      onPick={(i) => {
        ctx.closePanel();
        ctx.goTo(list[i].g, stepOfPage(list[i].page));
      }}
      onClose={ctx.closePanel}
    />,
  );
}

// ------------------------------------------------------------------- W
const WIP_ICONS: Record<string, string> = { todo: "🚧", check: "👀" };
/** The slides marked work in progress (#todo) or to check (#to-check),
 *  in deck order, to go to or edit. */
export function showWip() {
  const o = ctx.outline();
  const list: Node[] = [];
  const walk = (n: Node) => {
    if (n.kind === "slide" && (n.types ?? []).some((x) => x in WIP_ICONS)) list.push(n);
    n.children?.forEach(walk);
  };
  o.children.forEach(walk);
  const edit = (n: Node) => {
    if (n.src && o.root) ctx.openApp(ctx.editUrl(o.root, n.src));
  };
  ctx.openPanel(
    <Picker
      title={`${t("wip.title")} (${list.length})`}
      empty={t("wip.none")}
      help={t(isDev() ? "wip.help" : "overflow.help")}
      items={list.map((n) => ({
        label: `${(n.types ?? []).filter((x) => x in WIP_ICONS).map((x) => WIP_ICONS[x]).join("")} ${slideLabel(n.g)}`,
        detail: n.src ? `${n.src.file}:${n.src.line}` : undefined,
        actions: [
          ...(isDev() && n.src ? [{ label: t("work.change"), key: "s", run: () => editWork(n.g) }] : []),
          ...(o.root && n.src ? [{ label: t("overflow.edit"), key: "e", run: () => edit(n) }] : []),
        ],
      }))}
      onPick={(i) => {
        ctx.closePanel();
        ctx.goTo(list[i].g);
      }}
      onClose={ctx.closePanel}
    />,
  );
}

// ------------------------------------------------- work state (shift-W)
type WorkState = "todo" | "check" | "none";
const isDev = () => document.body.dataset.dev === "true";

/** The note shown on slide `g` (its todo-note widget), if it is mounted. */
function currentNote(g: number): string | null {
  const el = document.querySelector(`.reveal .slides section[data-g="${g}"] .widget[data-widget="todo-note"]`);
  const text = el?.textContent?.trim();
  return text ? text.replace(/^(🚧|👀)\s*/u, "") : null;
}

/** The work state of slide `g` (todo, check or none) and its note, to
 *  change: written into the source (POST work, work.py). Dev server only. */
export function editWork(g: number) {
  if (!isDev()) return ctx.flash(t("work.devOnly"));
  const n = nodeOf(g);
  if (!n?.src) return ctx.flash(t("work.noSource"));
  const types = n.types ?? [];
  const state: WorkState = types.includes("todo") ? "todo" : types.includes("check") ? "check" : "none";
  const save = async (s: WorkState, note: string | undefined) => {
    ctx.closePanel();
    try {
      const res = await fetch("work", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ g, state: s, note }),
      });
      const r = await res.json();
      ctx.flash(r.error ? t("work.failed", { error: r.error }) : t("work.saved", { state: t(`work.${s}`), where: `${r.file}:${r.line}` }));
    } catch (e) {
      ctx.flash(t("work.failed", { error: String(e) }));
    }
  };
  ctx.openPanel(<WorkPanel title={slideLabel(g)} state={state} note={currentNote(g)} onSave={save} onClose={ctx.closePanel} />);
}

const WORK_STATES: { s: WorkState; icon: string }[] = [
  { s: "todo", icon: "🚧" },
  { s: "check", icon: "👀" },
  { s: "none", icon: "✓" },
];

function WorkPanel(props: {
  title: string;
  state: WorkState;
  note: string | null;
  onSave: (s: WorkState, note: string | undefined) => void;
  onClose: () => void;
}) {
  const [state, setState] = React.useState<WorkState>(props.state);
  const [note, setNote] = React.useState(props.note ?? "");
  const [touched, setTouched] = React.useState(false);
  const input = React.useRef<HTMLInputElement>(null);
  React.useEffect(() => input.current?.focus(), []);
  // the note: kept as it is in the source unless edited
  const save = (s = state) => props.onSave(s, touched ? note.trim() : undefined);
  const move = (d: number) => {
    const i = WORK_STATES.findIndex((x) => x.s === state);
    setState(WORK_STATES[(i + d + WORK_STATES.length) % WORK_STATES.length].s);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") props.onClose();
    else if (e.key === "Enter") save();
    else if (e.key === "ArrowDown") move(1);
    else if (e.key === "ArrowUp") move(-1);
    else {
      e.stopPropagation(); // typing in the note
      return;
    }
    e.preventDefault();
    e.stopPropagation();
  };
  return (
    <div className="sb-overlay" tabIndex={-1} onKeyDown={onKey} onClick={(e) => e.target === e.currentTarget && props.onClose()}>
      <div className="sb-panel" style={{ maxWidth: 520, height: "auto" }}>
        <div className="sb-header">
          <strong>
            {t("work.title")} — {props.title}
          </strong>
          <span className="sb-spacer" />
          <button onClick={props.onClose} title={t("close")}>
            ✕
          </button>
        </div>
        <div className="sb-list">
          {WORK_STATES.map((x) => (
            <div
              key={x.s}
              className={`sb-row${x.s === state ? " selected" : ""}`}
              onClick={() => setState(x.s)}
              onDoubleClick={() => save(x.s)}
            >
              <span className="sb-number" style={{ width: "1.5em", textAlign: "left" }}>
                {x.icon}
              </span>
              <span className="sb-title">{t(`work.${x.s}`)}</span>
              {x.s === props.state && <span className="sb-file">{t("work.current")}</span>}
            </div>
          ))}
          <div className="sb-row context" style={{ gap: 8 }}>
            <input
              ref={input}
              style={{ flex: 1, font: "14px system-ui, sans-serif", padding: "4px 6px" }}
              value={note}
              disabled={state === "none"}
              placeholder={t(props.note === null && props.state !== "none" ? "work.noteKept" : "work.note")}
              onChange={(e) => {
                setNote(e.target.value);
                setTouched(true);
              }}
            />
            <button className="picker-action" onClick={() => save()}>
              {t("work.save")}
            </button>
          </div>
        </div>
        <div className="sb-help">{t("work.help")}</div>
      </div>
    </div>
  );
}

/** "content height: 512pt, available height: 420pt" -> "height +92pt" */
function excess(message: string) {
  const m = /content (\w+): ([\d.]+)pt, available \1: ([\d.]+)pt/.exec(message);
  return m ? `${t(`overflow.${m[1]}`)} +${Math.round(Number(m[2]) - Number(m[3]))}pt` : "";
}

/** Dev server: a thin bar at the bottom of each overflowing step
 *  (data-overflow; the bar itself: addOverflowBar in svg-pages.ts). */
function markOverflows() {
  const o = ctx.outline();
  if (!o.root) return;
  document.querySelectorAll<HTMLElement>(".reveal .slides .page[data-overflow]").forEach((el) => {
    delete el.dataset.overflow;
    addOverflowBar(el);
  });
  for (const x of o.overflows ?? []) {
    const el = document.querySelector<HTMLElement>(`.reveal .slides section[data-g] > .page[data-page="${x.page}"]`);
    if (!el) continue;
    el.dataset.overflow = `${t("overflow.bar")} ${excess(x.message)}`.trim();
    addOverflowBar(el);
  }
}

// ------------------------------------------------------------------- Z
export function openZotero() {
  if (!ctx.outline().root) return ctx.flash(t("zotero.devOnly"));
  const links = slideZoteroLinks(ctx.deck.getCurrentSlide());
  if (!links.length) return ctx.flash(t("zotero.none"));
  if (links.length === 1) return ctx.openApp(links[0].href);
  ctx.openPanel(
    <Picker
      title={t("zotero.pick")}
      help={t("zotero.help")}
      items={links.map((l) => ({ label: l.label }))}
      onPick={(i) => {
        ctx.closePanel();
        ctx.openApp(links[i].href);
      }}
      onClose={ctx.closePanel}
    />,
  );
}

export function initExtras(c: ExtrasContext) {
  ctx = c;
  loaded();
  initDetails({ deck: c.deck, outline: c.outline, goTo: c.goTo, currentG: c.currentG, slideLabel, pick, panelOpen: c.panelOpen, flash: c.flash });
  // O: Reveal's own O (the overview) is left to Esc
  c.deck.addKeyBinding({ keyCode: 79, key: "O", description: t("key.overflow") }, () => {
    if (!c.panelOpen()) showOverflows();
  });
  c.deck.addKeyBinding({ keyCode: 87, key: "W", description: t("key.wip") }, () => {
    if (!c.panelOpen()) showWip();
  });
  // shift-W (Reveal drops shift-modified keys: a listener of its own)
  window.addEventListener("keydown", (e) => {
    if (e.key !== "W" || !e.shiftKey || e.metaKey || e.ctrlKey || e.altKey || c.panelOpen()) return;
    if ((e.target as HTMLElement).closest?.("input, textarea, [contenteditable]")) return;
    e.preventDefault();
    editWork(c.currentG());
  });
  c.deck.addKeyBinding({ keyCode: 90, key: "Z", description: t("key.zotero") }, () => {
    if (!c.panelOpen()) openZotero();
  });
  c.deck.addKeyBinding({ keyCode: 73, key: "I", description: t("key.details") }, () => {
    /* handled by details.ts (before Reveal); listed in ? */
  });
  if (c.outline().root) overflowToast();
  markOverflows();
}

// ------------------------------------------------- dev server: toasts
let lastOverflows = -1;
function overflowToast() {
  const n = new Set((ctx.outline().overflows ?? []).map((x) => x.g)).size;
  if (n !== lastOverflows && n > 0)
    toast(t("dev.overflows", { n }), { kind: "warning", id: "overflows", action: { label: "O", run: showOverflows } });
  else if (n === 0) closeToast("overflows");
  lastOverflows = n;
}

let hadErrors = false;
let disconnected = false;
let shownLost = false;
/** The dev server's events, for toasts (main.tsx). */
export function devEvent(e: { type: "errors"; n: number } | { type: "outline" } | { type: "disconnected" } | { type: "connected" }) {
  if (e.type === "errors") {
    if (e.n) toast(t("dev.errors", { n: e.n }), { kind: "error", id: "errors", ms: 4000 });
    else if (hadErrors) {
      closeToast("errors");
      toast(t("dev.fixed"), { kind: "success", id: "errors" });
    }
    hadErrors = e.n > 0;
  } else if (e.type === "outline") {
    overflowToast();
    markOverflows();
  }
  else if (e.type === "disconnected" && !disconnected) {
    // a reconnection within a second (or the page being left) says nothing
    disconnected = true;
    setTimeout(() => {
      if (!disconnected) return;
      shownLost = true;
      toast(t("dev.disconnected"), { kind: "warning", id: "server", ms: 0 });
    }, 1500);
  } else if (e.type === "connected") {
    disconnected = false;
    if (shownLost) toast(t("dev.reconnected"), { kind: "success", id: "server" });
    shownLost = false;
  }
}
