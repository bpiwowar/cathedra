import React from "react";
import { dropEmpty, isShown, SLIDE_TYPES, typesOf } from "./slide-types";
import { t as tr } from "./i18n";

// slide-app's structure browser (T) and edit links (E, shift-E), over the
// outline built by tools/outline.mjs. Nodes are identified by their group
// index `g` (one per Reveal leaf slide).

export type Src = { file: string; line: number };
export type Node = {
  kind: "title" | "section" | "subsection" | "slide";
  title: string | null;
  g: number;
  slide: number;
  src: Src | null;
  chain: Src[];
  types: string[];
  synopsis?: string | null;
  children: Node[];
};
export type Outline = { title: string | null; file: string; root: string | null; children: Node[] };

const TYPE_ICONS: Record<string, string> = Object.fromEntries(Object.entries(SLIDE_TYPES).map(([k, v]) => [k, v.icon]));

// case and accents folded both ways: "gen" finds "Génération"
const fold = (s: string) => s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export const editUrl = (root: string, src: Src) => `vscode://file${root.startsWith("/") ? "" : "/"}${root}/${src.file}:${src.line}`;

/** Hands an app URL (vscode://, zotero://) to the OS, by clicking a link to
 *  it: the page stays (setting location or window.open(…, "_self") is ignored
 *  by some browsers, and a hidden iframe keeps the keyboard focus). */
export function openApp(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.click();
}

/** Parent links and the flat document order of an outline. */
export function index(outline: Outline) {
  const parent = new Map<Node, Node | null>();
  const order: Node[] = [];
  const walk = (n: Node, p: Node | null) => {
    parent.set(n, p);
    order.push(n);
    n.children.forEach((c) => walk(c, n));
  };
  outline.children.forEach((n) => walk(n, null));
  return { parent, order, byG: new Map(order.map((n) => [n.g, n])) };
}

const label = (n: Node) => n.title ?? (n.kind === "title" ? tr("sb.title") : tr("sb.untitled"));
// a slide type's name, in the deck's language
const typeLabel = (t: string) => (tr("type." + t) !== "type." + t ? tr("type." + t) : SLIDE_TYPES[t]?.label ?? t);

function Highlight({ text, terms }: { text: string; terms: string[] }) {
  if (!terms.length) return <>{text}</>;
  // folding keeps one char per char for Latin text: mark on the folded copy
  const f = fold(text);
  const marks = new Array(text.length).fill(false);
  for (const t of terms) for (let i = f.indexOf(t); i >= 0; i = f.indexOf(t, i + 1)) marks.fill(true, i, i + t.length);
  const out: React.ReactNode[] = [];
  let i = 0;
  while (i < text.length) {
    let j = i;
    while (j < text.length && marks[j] === marks[i]) j++;
    out.push(marks[i] ? <mark key={i}>{text.slice(i, j)}</mark> : text.slice(i, j));
    i = j;
  }
  return <>{out}</>;
}

type Row = { node: Node; depth: number; context: boolean };

export function StructureBrowser(props: {
  outline: Outline;
  current: number; // g of the current slide
  onGo: (g: number) => void;
  onClose: () => void;
  todoMasked?: boolean; // M: no todo badges
  onTypes?: (choice: Record<string, boolean>) => void; // show / hide slide types (reloads)
}) {
  const { outline, current, onGo, onClose, todoMasked, onTypes } = props;
  // the types a slide shows as badges (todo / check ones gone under M)
  const shownTypes = (n: Node) => n.types.filter((t) => !(todoMasked && (t === "todo" || t === "check")));
  const { parent, order, byG } = React.useMemo(() => index(outline), [outline]);
  // the slides left out, and the (sub)sections they leave empty
  const removed = React.useMemo(() => {
    const out = new Set<Node>();
    const walk = (n: Node): [number, number] => {
      if (n.kind === "slide") {
        const hidden = typesOf(n).some((t) => !isShown(t));
        if (hidden) out.add(n);
        return [1, hidden ? 0 : 1];
      }
      let total = 0;
      let kept = 0;
      for (const c of n.children) {
        const [t, k] = walk(c);
        total += t;
        kept += k;
      }
      if (dropEmpty() && n.kind !== "title" && total > 0 && kept === 0) out.add(n);
      return [total, kept];
    };
    outline.children.forEach(walk);
    return out;
  }, [outline]);
  const hiddenSlide = (n: Node) => removed.has(n);
  const ancestors = (n: Node | undefined | null) => {
    const out: Node[] = [];
    for (let p = n ? parent.get(n) : null; p; p = parent.get(p)) out.push(p);
    return out;
  };
  const [open, setOpen] = React.useState<Set<number>>(() => new Set(ancestors(byG.get(current)).map((n) => n.g)));
  const [query, setQuery] = React.useState("");
  const [sel, setSel] = React.useState(current);
  const [only, setOnly] = React.useState<Set<string>>(new Set());
  const input = React.useRef<HTMLInputElement>(null);
  const list = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => input.current?.focus(), []);

  const terms = fold(query).split(/\s+/).filter(Boolean);
  const filtering = terms.length > 0 || only.size > 0;
  const types = React.useMemo(() => [...new Set(order.flatMap(shownTypes))], [order, todoMasked]);
  // every type of the deck, for the show / hide checkboxes
  const deckTypes = React.useMemo(() => [...new Set(order.flatMap(typesOf))], [order]);
  // the ticked "in the deck" boxes, applied (reloading the deck) by the button
  const [pending, setPending] = React.useState<Record<string, boolean>>({});
  const changed = Object.fromEntries(Object.entries(pending).filter(([t, v]) => v !== isShown(t)));

  const rows: Row[] = React.useMemo(() => {
    const depth = (n: Node) => ancestors(n).length;
    if (!filtering) {
      const out: Row[] = [];
      const walk = (n: Node) => {
        out.push({ node: n, depth: depth(n), context: false });
        if (open.has(n.g)) n.children.forEach(walk);
      };
      outline.children.forEach(walk);
      return out;
    }
    // every term somewhere in the entry (title, file); sections kept as context
    const hit = (n: Node) =>
      terms.every((t) => fold(`${label(n)} ${n.src?.file ?? ""}`).includes(t)) &&
      (only.size === 0 || n.types.some((t) => only.has(t)));
    const keep = new Set<Node>();
    const ctx = new Set<Node>();
    for (const n of order)
      if (hit(n)) {
        keep.add(n);
        ancestors(n).forEach((a) => keep.has(a) || ctx.add(a));
      }
    return order
      .filter((n) => keep.has(n) || ctx.has(n))
      .map((n) => ({ node: n, depth: depth(n), context: !keep.has(n) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [outline, open, query, only]);

  // a new filter selects its first match (not a context row)
  React.useEffect(() => {
    const first = rows.find((r) => !r.context);
    if (filtering && first) setSel(first.node.g);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, only]);
  // keep the selection on a visible row
  const selIndex = Math.max(0, rows.findIndex((r) => r.node.g === sel));
  React.useEffect(() => {
    list.current?.querySelector(".sb-row.selected")?.scrollIntoView({ block: "nearest" });
  });

  const counts = (n: Node) => {
    const c: Record<string, number> = {};
    const walk = (x: Node) => {
      if (x.kind === "slide") shownTypes(x).forEach((t) => (c[t] = (c[t] ?? 0) + 1));
      x.children.forEach(walk);
    };
    walk(n);
    return c;
  };
  const toggle = (n: Node, value?: boolean) =>
    setOpen((o) => {
      const s = new Set(o);
      (value ?? !s.has(n.g)) ? s.add(n.g) : s.delete(n.g);
      return s;
    });

  const onKey = (e: React.KeyboardEvent) => {
    const r = rows[selIndex];
    const move = (d: number) => {
      const i = Math.min(rows.length - 1, Math.max(0, selIndex + d));
      if (rows[i]) setSel(rows[i].node.g);
    };
    const inText = e.target === input.current && query !== "";
    switch (e.key) {
      case "Escape":
        onClose();
        break;
      case "ArrowDown":
        move(1);
        break;
      case "ArrowUp":
        move(-1);
        break;
      case "PageDown":
        move(10);
        break;
      case "PageUp":
        move(-10);
        break;
      case "Enter":
        if (r && !hiddenSlide(r.node)) onGo(r.node.g);
        break;
      case "ArrowRight":
        if (inText || !r) return;
        if (r.node.children.length && !open.has(r.node.g)) toggle(r.node, true);
        else if (r.node.children.length) setSel(r.node.children[0].g);
        break;
      case "ArrowLeft":
        if (inText || !r) return;
        if (open.has(r.node.g)) toggle(r.node, false);
        else {
          const p = parent.get(r.node);
          if (p) setSel(p.g);
        }
        break;
      default:
        return;
    }
    e.preventDefault();
  };

  const allContainers = order.filter((n) => n.children.length);
  return (
    <div className="sb-overlay" onKeyDown={onKey} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sb-panel">
        <div className="sb-header">
          <strong>{outline.title ?? tr("sb.outline")}</strong>
          <span className="sb-spacer" />
          <button onClick={() => setOpen(new Set(allContainers.map((n) => n.g)))}>{tr("sb.expand")}</button>
          <button onClick={() => setOpen(new Set())}>{tr("sb.collapse")}</button>
          <button onClick={onClose} title={tr("sb.closeEsc")}>✕</button>
        </div>
        <input
          ref={input}
          className="sb-filter"
          placeholder={tr("sb.filter")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        {onTypes && deckTypes.length > 0 && (
          <div className="sb-only sb-show">
            {tr("sb.inDeck")}
            {deckTypes.map((t) => (
              <label key={t}>
                <input
                  type="checkbox"
                  checked={pending[t] ?? isShown(t)}
                  onChange={(e) => setPending((p) => ({ ...p, [t]: e.target.checked }))}
                />
                {TYPE_ICONS[t] ?? "•"} {typeLabel(t)}
              </label>
            ))}
            <label title={tr("sb.emptyNote")}>
              <input
                type="checkbox"
                checked={!(pending.empty ?? isShown("empty"))}
                onChange={(e) => setPending((p) => ({ ...p, empty: !e.target.checked }))}
              />
              {tr("sb.dropEmpty")}
            </label>
            <button
              className="sb-apply"
              disabled={Object.keys(changed).length === 0}
              title={tr("sb.applyNote")}
              onClick={() => onTypes(changed)}
            >
              {tr("sb.apply")}
            </button>
          </div>
        )}
        {types.length > 0 && (
          <div className="sb-only">
            {tr("sb.only")}
            {types.map((t) => (
              <button
                key={t}
                className={only.has(t) ? "on" : ""}
                onClick={() =>
                  setOnly((o) => {
                    const s = new Set(o);
                    s.has(t) ? s.delete(t) : s.add(t);
                    return s;
                  })
                }
              >
                {TYPE_ICONS[t] ?? "•"} {typeLabel(t)}
              </button>
            ))}
          </div>
        )}
        <div className="sb-list" ref={list}>
          {rows.map(({ node: n, depth, context }, i) => {
            const c = n.kind === "slide" ? {} : counts(n);
            const isOpen = filtering || open.has(n.g);
            return (
              <div
                key={n.g}
                className={`sb-row sb-${n.kind}${i === selIndex ? " selected" : ""}${n.g === current ? " current" : ""}${context ? " context" : ""}${hiddenSlide(n) ? " hidden" : ""}`}
                style={{ paddingLeft: `${0.6 + depth * 1.2}em` }}
                onClick={() => setSel(n.g)}
                onDoubleClick={() => hiddenSlide(n) || onGo(n.g)}
                title={hiddenSlide(n) ? tr("sb.leftOut") : undefined}
              >
                <span
                  className="sb-handle"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (n.children.length && !filtering) toggle(n);
                  }}
                >
                  {n.children.length ? (isOpen ? "▾" : "▸") : ""}
                </span>
                <span className="sb-title">
                  <Highlight text={label(n)} terms={terms} />
                </span>
                {shownTypes(n).map((t) => (
                  <span key={t} className={`sb-badge sb-type-${t}`} title={t}>
                    {TYPE_ICONS[t] ?? "•"} {t === "todo" ? "todo" : t === "check" ? "check" : ""}
                  </span>
                ))}
                {Object.entries(c).map(([t, k]) => (
                  <span key={t} className={`sb-badge sb-type-${t}`}>
                    {TYPE_ICONS[t] ?? "•"} {t} {k}
                  </span>
                ))}
                {/* dev builds: where a module starts (its file differs from the parent's) */}
                {outline.root && n.src && n.src.file !== (parent.get(n)?.src?.file ?? outline.file) && (
                  <span className="sb-file">{n.src.file}</span>
                )}
                <span className="sb-number">{n.kind === "slide" ? n.slide : ""}</span>
              </div>
            );
          })}
        </div>
        <div className="sb-help">{tr("sb.help")}{outline.root ? tr("sb.helpDev") : ""}</div>
      </div>
    </div>
  );
}

/** shift-E: where the current slide comes from (slide, then each #include). */
export function EditChain(props: { outline: Outline; node: Node; onClose: () => void }) {
  const { outline, node, onClose } = props;
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => ref.current?.focus(), []);
  const steps = [...(node.src ? [{ ...node.src, role: "slide" }] : []), ...node.chain.map((c) => ({ ...c, role: "#include" }))];
  return (
    <div
      className="sb-overlay"
      tabIndex={-1}
      ref={ref}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
        const k = Number(e.key);
        if (k >= 1 && k <= steps.length) {
          openApp(editUrl(outline.root!, steps[k - 1]));
          onClose();
        }
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="sb-panel sb-chain">
        <div className="sb-header">
          <strong>{tr("chain.title", { title: label(node) })}</strong>
          <span className="sb-spacer" />
          <button onClick={onClose}>✕</button>
        </div>
        <ol>
          {steps.map((s, i) => (
            <li key={i}>
              <a
                href={editUrl(outline.root!, s)}
                onClick={(e) => {
                  e.preventDefault();
                  openApp(editUrl(outline.root!, s));
                  onClose();
                }}
              >
                {s.file}:{s.line}
              </a>{" "}
              <span className="sb-file">{s.role}</span>
            </li>
          ))}
        </ol>
        <div className="sb-help">{tr("chain.help", { n: steps.length })}</div>
      </div>
    </div>
  );
}
