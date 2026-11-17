// Morphing (morph.ts) on the SVG pages (svg-pages.ts): the transition from
// step page A to step page B moves the parts' own SVG elements (copies of
// them, in an overlay), no pixels.
//
// - Parts: an element of a page belongs to the smallest part whose box
//   (morph.json, padded) holds its bounding box; a group that straddles a
//   box is split into its children (a leaf that straddles stays in the
//   background). typst.ts's SVG carries no label of Typst content, so the
//   boxes are the only link from a part to its elements.
// - Each part is FLIP-animated as a whole: same size -> a translation, else a
//   translation + scale of the whole part (A's and B's elements cross-fading
//   around the middle); a part on one page only fades in or out.
// - The rest: an element (with its place on the page) found on both pages
//   stays still; what is only on A fades out, what is only on B fades in.
import type { Box } from "./morph";

const PAD = 2; // pt: strokes are outside the CeTZ bounds
const NS = "http://www.w3.org/2000/svg";

type Placed = { el: SVGGraphicsElement; m: DOMMatrix }; // m: parent -> page

// What an element gets from its ancestors in the page (typst.ts puts the fill
// of a text on its group, the glyphs inside have none): a copy of it alone
// needs them
const INHERITED = [
  "fill", "fill-rule", "fill-opacity", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin",
  "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "stroke-opacity", "color",
];
const inheritedCache = new WeakMap<Element, string>();
function inherited(el: Element): string {
  const parent = el.parentElement;
  if (!parent || parent.tagName === "svg") return "";
  let s = inheritedCache.get(parent);
  if (s == null) {
    const attrs: Record<string, string> = {};
    let opacity = 1;
    for (let a: Element | null = parent; a && a.tagName !== "svg"; a = a.parentElement) {
      for (const k of INHERITED) if (!(k in attrs) && a.hasAttribute(k)) attrs[k] = a.getAttribute(k)!;
      if (a.hasAttribute("opacity")) opacity *= Number(a.getAttribute("opacity"));
    }
    if (opacity !== 1) attrs.opacity = String(opacity);
    s = JSON.stringify(attrs);
    inheritedCache.set(parent, s);
  }
  return s;
}
type Split = { parts: Map<string, Placed[]>; rest: Placed[] };

const area = (q: Box) => (q[2] - q[0]) * (q[3] - q[1]);
const pad = (q: Box): Box => [q[0] - PAD, q[1] - PAD, q[2] + PAD, q[3] + PAD];
const within = (r: Box, q: Box) => r[0] >= q[0] && r[1] >= q[1] && r[2] <= q[2] && r[3] <= q[3];
const meets = (r: Box, q: Box) => r[0] < q[2] && r[2] > q[0] && r[1] < q[3] && r[3] > q[1];

function toPage(svg: SVGSVGElement): (el: SVGGraphicsElement) => DOMMatrix {
  const inv = DOMMatrix.fromMatrix(svg.getScreenCTM()!).inverse();
  return (el) => inv.multiply(DOMMatrix.fromMatrix(el.getScreenCTM()!));
}

function pageBox(el: SVGGraphicsElement, m: DOMMatrix): Box | null {
  let b: DOMRect;
  try {
    b = el.getBBox();
  } catch {
    return null;
  }
  if (!b.width && !b.height) return null;
  const pts = [
    m.transformPoint({ x: b.x, y: b.y }),
    m.transformPoint({ x: b.x + b.width, y: b.y }),
    m.transformPoint({ x: b.x, y: b.y + b.height }),
    m.transformPoint({ x: b.x + b.width, y: b.y + b.height }),
  ];
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

const graphics = (el: Element) =>
  [...el.children].filter(
    (c): c is SVGGraphicsElement => c instanceof SVGGraphicsElement && c.tagName !== "foreignObject",
  );

// The page's elements, sorted into its parts and the rest (cached per mounted SVG).
const splits = new WeakMap<SVGSVGElement, { key: string; split: Split }>();
function split(svg: SVGSVGElement, boxes: Record<string, Box>): Split {
  const key = JSON.stringify(boxes);
  const cached = splits.get(svg);
  if (cached?.key === key) return cached.split;
  const ctm = toPage(svg);
  const ids = Object.keys(boxes);
  const padded = Object.fromEntries(ids.map((id) => [id, pad(boxes[id])]));
  const parts = new Map<string, Placed[]>(ids.map((id) => [id, []]));
  const rest: Placed[] = [];
  const walk = (el: SVGGraphicsElement) => {
    const m = ctm(el.parentElement as unknown as SVGGraphicsElement);
    const b = pageBox(el, ctm(el));
    if (!b) {
      // nothing drawn (an empty group, a clip path's holder…): its children may still be
      const kids = graphics(el);
      if (kids.length) kids.forEach(walk);
      else rest.push({ el, m });
      return;
    }
    const holders = ids.filter((id) => within(b, padded[id])).sort((u, v) => area(boxes[u]) - area(boxes[v]));
    const kids = graphics(el);
    const leaf = !kids.length || el.tagName === "use" || el.tagName === "image";
    if (holders.length) {
      const owner = holders[0];
      // a smaller part (inside the owner) it overlaps: look at its children
      const inner = ids.some((id) => id !== owner && area(boxes[id]) < area(boxes[owner]) && meets(b, boxes[id]));
      if (!inner || leaf) return void parts.get(owner)!.push({ el, m });
    } else if (leaf || !ids.some((id) => meets(b, padded[id]))) return void rest.push({ el, m });
    kids.forEach(walk);
  };
  const root = svg.querySelector<SVGGraphicsElement>(":scope > g.typst-page");
  if (root) graphics(root).forEach(walk);
  const out = { parts, rest };
  splits.set(svg, { key, split: out });
  return out;
}

// what makes an element the same on both pages: its place and its markup
const fmt = (m: DOMMatrix) => [m.a, m.b, m.c, m.d, m.e, m.f].map((v, i) => v.toFixed(i < 4 ? 5 : 2)).join(",");
const sig = (p: Placed) => fmt(p.m) + inherited(p.el) + p.el.outerHTML;

// A copy of placed elements, in page coordinates
function copy(list: Placed[]): SVGGElement {
  const g = document.createElementNS(NS, "g");
  for (const { el, m } of list) {
    const w = document.createElementNS(NS, "g");
    w.setAttribute("transform", `matrix(${[m.a, m.b, m.c, m.d, m.e, m.f].join(",")})`);
    for (const [k, v] of Object.entries(JSON.parse(inherited(el) || "{}"))) w.setAttribute(k, v as string);
    const c = el.cloneNode(true) as Element;
    c.querySelectorAll("foreignObject").forEach((f) => f.remove());
    w.append(c);
    g.append(w);
  }
  return g;
}

// The rest of a page: groups of A (B) that are not on B (A) are opened, so that
// what did not change is found inside them
function diff(a: Placed[], b: Placed[], ctmA: (e: SVGGraphicsElement) => DOMMatrix, ctmB: (e: SVGGraphicsElement) => DOMMatrix) {
  const deep = (list: Placed[], ctm: (e: SVGGraphicsElement) => DOMMatrix) => {
    const s = new Set<string>();
    const add = (p: Placed) => {
      s.add(sig(p));
      for (const k of graphics(p.el)) add({ el: k, m: ctm(p.el) });
    };
    list.forEach(add);
    return s;
  };
  const sa = deep(a, ctmA);
  const sb = deep(b, ctmB);
  const same: Placed[] = [];
  const only = (list: Placed[], other: Set<string>, ctm: (e: SVGGraphicsElement) => DOMMatrix, keep: boolean) => {
    const out: Placed[] = [];
    const walk = (p: Placed) => {
      if (other.has(sig(p))) {
        if (keep) same.push(p);
        return;
      }
      const kids = graphics(p.el);
      if (!kids.length || p.el.tagName === "use") out.push(p);
      else kids.forEach((k) => walk({ el: k, m: ctm(p.el) }));
    };
    list.forEach(walk);
    return out;
  };
  return { onlyA: only(a, sb, ctmA, false), onlyB: only(b, sa, ctmB, true), same };
}

/**
 * The overlay of a transition from page A to page B (their SVGs) and its
 * animations, or null if a page is not mounted.
 */
export function svgTransition(
  fromEl: HTMLElement,
  toEl: HTMLElement,
  pa: Record<string, Box>,
  pb: Record<string, Box>,
  width: number,
  height: number,
  duration: number,
): { layer: HTMLElement; anims: Animation[] } | null {
  const sa = fromEl.querySelector<SVGSVGElement>(":scope > svg");
  const sb = toEl.querySelector<SVGSVGElement>(":scope > svg");
  if (!sa || !sb) return null;
  // page A is hidden (a step page covers it): measure it shown
  const vis = fromEl.style.visibility;
  fromEl.style.visibility = "visible";
  const A = split(sa, pa);
  const B = split(sb, pb);
  const { onlyA, onlyB, same } = diff(A.rest, B.rest, toPage(sa), toPage(sb));
  fromEl.style.visibility = vis;

  const layer = document.createElement("div");
  layer.className = "morph-overlay";
  Object.assign(layer.style, {
    position: "absolute", inset: "0", zIndex: "5", pointerEvents: "none", background: "white", overflow: "hidden",
  });
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "typst-svg");
  svg.setAttribute("preserveAspectRatio", "none");
  Object.assign(svg.style, { position: "absolute", inset: "0", width: "100%", height: "100%", overflow: "hidden" });
  layer.append(svg);

  const opts: KeyframeAnimationOptions = { duration, easing: "ease-in-out", fill: "forwards" };
  const quick = { ...opts, duration: duration * 0.4 };
  const anims: Animation[] = [];
  // the rest under the parts, but what is drawn over a part on the page
  // (an arrow across a frame) over them
  const ta = toPage(sa);
  const tb = toPage(sb);
  const over = (p: Placed, parts: Map<string, Placed[]>, boxes: Record<string, Box>, ctm: typeof ta) => {
    const b = pageBox(p.el, ctm(p.el));
    if (!b) return false;
    for (const [id, list] of parts)
      if (list.length && meets(b, pad(boxes[id])) && list[0].el.compareDocumentPosition(p.el) & Node.DOCUMENT_POSITION_FOLLOWING)
        return true;
    return false;
  };
  const layers = (list: Placed[], parts: Map<string, Placed[]>, boxes: Record<string, Box>, ctm: typeof ta) => {
    const up = new Set(list.filter((p) => over(p, parts, boxes, ctm)));
    return [copy(list.filter((p) => !up.has(p))), copy([...up])];
  };
  const [sameLow, sameHigh] = layers(same, B.parts, pb, tb);
  const [aLow, aHigh] = layers(onlyA, A.parts, pa, ta);
  const [bLow, bHigh] = layers(onlyB, B.parts, pb, tb);
  svg.append(sameLow, aLow, bLow);
  for (const g of [aLow, aHigh]) anims.push(g.animate([{ opacity: 1 }, { opacity: 0 }], quick));
  for (const g of [bLow, bHigh]) anims.push(g.animate([{ opacity: 0 }, { opacity: 1 }], quick));

  // the largest parts first: a part inside another is drawn over it
  const ids = [...new Set([...Object.keys(pa), ...Object.keys(pb)])].sort(
    (u, v) => Math.max(pb[v] ? area(pb[v]) : 0, pa[v] ? area(pa[v]) : 0) - Math.max(pb[u] ? area(pb[u]) : 0, pa[u] ? area(pa[u]) : 0),
  );
  for (const id of ids) {
    const la = A.parts.get(id);
    const lb = B.parts.get(id);
    const ga = la?.length ? copy(la) : null;
    const gb = lb?.length ? copy(lb) : null;
    if (ga) svg.append(ga);
    if (gb) svg.append(gb);
    if (ga && gb) {
      // FLIP: the part moves as a whole (one transform, never a tween of its coordinates)
      const [ax0, ay0, ax1, ay1] = pa[id];
      const [bx0, by0, bx1, by1] = pb[id];
      const close = (u: number, v: number) => Math.abs(u - v) < Math.max(0.5, 0.01 * Math.max(u, v));
      const sameSize = close(ax1 - ax0, bx1 - bx0) && close(ay1 - ay0, by1 - by0);
      const sx = sameSize || ax1 === ax0 ? 1 : (bx1 - bx0) / (ax1 - ax0);
      const sy = sameSize || ay1 === ay0 ? 1 : (by1 - by0) / (ay1 - ay0);
      ga.style.transformOrigin = `${ax0}px ${ay0}px`;
      gb.style.transformOrigin = `${bx0}px ${by0}px`;
      ga.style.transformBox = gb.style.transformBox = "view-box";
      const toB = `translate(${bx0 - ax0}px, ${by0 - ay0}px) scale(${sx}, ${sy})`;
      const fromA = `translate(${ax0 - bx0}px, ${ay0 - by0}px) scale(${1 / sx}, ${1 / sy})`;
      const none = "translate(0px, 0px) scale(1, 1)";
      if (sameSize)
        anims.push(
          ga.animate([{ transform: none, opacity: 1 }, { opacity: 1, offset: 0.5 }, { transform: toB, opacity: 0 }], opts),
          gb.animate([{ transform: fromA, opacity: 0 }, { opacity: 1, offset: 0.5 }, { transform: none, opacity: 1 }], opts),
        );
      else
        anims.push(
          ga.animate([{ transform: none, opacity: 1 }, { opacity: 1, offset: 0.35 }, { opacity: 0, offset: 0.65 }, { transform: toB, opacity: 0 }], opts),
          gb.animate([{ transform: fromA, opacity: 0 }, { opacity: 0, offset: 0.35 }, { opacity: 1, offset: 0.65 }, { transform: none, opacity: 1 }], opts),
        );
    } else if (ga) anims.push(ga.animate([{ opacity: 1 }, { opacity: 0 }], opts));
    else if (gb) anims.push(gb.animate([{ opacity: 0 }, { opacity: 1 }], opts));
  }
  svg.append(sameHigh, aHigh, bHigh);
  return { layer, anims };
}
