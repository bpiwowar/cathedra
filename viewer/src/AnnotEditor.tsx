// shift-O (dev server): move an element annotation's label, change its width,
// and write the result into the Typst source (docs/annotations.md).
//
// Two stages, as slide-app's overlay editor (slide-app/src/overlay-editor.ts):
// 1. pick: every label of the step page shown is outlined; hover (or Tab)
//    one, Enter or click picks it, Esc cancels;
// 2. drag: the label (a copy of its part of the page; the page underneath is covered)
//    follows the mouse, its right edge handle sets the width; arrows nudge it
//    (shift: by 10), + / - change the width; Enter writes `dx:`/`dy:` (and
//    `width:` if it changed) on the #annot call (POST annot, build.mjs), Esc
//    cancels.
// The label boxes come from the build (annots.json: <annot-box> metadata of
// lib/slides.typ, in page units, 1 unit = 1 pt = 1 slide px).

type AnnotBox = {
  key: string;
  target: string;
  id: string | null;
  page: number;
  slide: number;
  x: number;
  y: number;
  w: number;
  h: number;
  tx: number;
  ty: number;
};

const BLUE = "#2563eb";
const round = (v: number) => Math.round(v * 2) / 2;

/** The step page shown in `section`: the last visible one. */
function shownPage(section: HTMLElement): HTMLElement | null {
  const pages = [...section.querySelectorAll<HTMLElement>(":scope > .page")];
  const shown = pages.filter((p) => !p.classList.contains("fragment") || p.classList.contains("visible"));
  return shown.at(-1) ?? null;
}

function div(parent: HTMLElement, style: Partial<CSSStyleDeclaration>, cls?: string) {
  const el = parent.appendChild(document.createElement("div"));
  if (cls) el.className = cls;
  Object.assign(el.style, style);
  return el;
}

/**
 * Opens the editor on `section` (the current Reveal slide). `scale`: Reveal's
 * current scale (screen px per slide unit); `flash` shows a message; `onClose`
 * is called once, when the editor is gone.
 */
export async function openAnnotEditor(opts: {
  section: HTMLElement;
  scale: () => number;
  flash: (msg: string) => void;
  onClose: () => void;
}) {
  const { section, flash } = opts;
  const pageEl = shownPage(section);
  const page = Number(pageEl?.dataset.page);
  let boxes: AnnotBox[] = [];
  try {
    boxes = (await (await fetch(`annots.json?t=${Date.now()}`)).json()) as AnnotBox[];
  } catch {
    // no annots.json: not the dev server
  }
  boxes = boxes.filter((b) => b.page === page);
  if (!pageEl || !boxes.length) {
    flash("No annotation on this step (shift-O moves #annot labels)");
    opts.onClose();
    return;
  }

  const layer = div(section, { position: "absolute", inset: "0", zIndex: "50", cursor: "default" }, "annot-editor");
  let closed = false;
  const close = () => {
    if (closed) return;
    closed = true;
    layer.remove();
    window.removeEventListener("keydown", onKey, true);
    opts.onClose();
  };

  // ---------------------------------------------------------------- pick
  let hovered = 0;
  const outlines = boxes.map((b, i) => {
    const el = div(layer, {
      position: "absolute",
      left: `${b.x - 3}px`,
      top: `${b.y - 3}px`,
      width: `${b.w + 6}px`,
      height: `${b.h + 6}px`,
      border: `2px dashed ${BLUE}`,
      borderRadius: "4px",
      cursor: "pointer",
    });
    el.title = `annot("${b.target}"${b.id ? `, id: "${b.id}"` : ""})`;
    el.addEventListener("mouseenter", () => setHover(i));
    el.addEventListener("click", (e) => {
      e.stopPropagation();
      pick(i);
    });
    return el;
  });
  const setHover = (i: number) => {
    hovered = i;
    outlines.forEach((el, j) => {
      el.style.background = j === i ? "rgb(37 99 235 / 0.12)" : "transparent";
      el.style.borderStyle = j === i ? "solid" : "dashed";
    });
  };
  setHover(0);
  flash(`${boxes.length} label(s): hover or Tab, Enter to pick, Esc to cancel`);

  // ---------------------------------------------------------------- drag
  let editing: { b: AnnotBox; x: number; y: number; w: number; el: HTMLElement } | null = null;

  function pick(i: number) {
    const b = boxes[i];
    outlines.forEach((el) => el.remove());
    // cover the label drawn on the page, and drag a copy of it
    div(layer, {
      position: "absolute",
      left: `${b.x - 1}px`,
      top: `${b.y - 1}px`,
      width: `${b.w + 2}px`,
      height: `${b.h + 2}px`,
      background: "rgb(255 255 255 / 0.85)",
      outline: "1px dotted #999",
    });
    const el = div(layer, {
      position: "absolute",
      left: `${b.x}px`,
      top: `${b.y}px`,
      width: `${b.w}px`,
      height: `${b.h}px`,
      outline: `2px solid ${BLUE}`,
      outlineOffset: "2px",
      cursor: "move",
      touchAction: "none",
      background: "white",
    });
    // the label: the page's SVG, its view box cut to the label's box (the
    // glyphs it uses are in the document, svg-pages.ts)
    const src = pageEl!.querySelector<SVGSVGElement>(":scope > svg");
    if (src) {
      const copy = src.cloneNode(true) as SVGSVGElement;
      copy.querySelectorAll("foreignObject").forEach((f) => f.remove()); // the text layer
      copy.setAttribute("viewBox", `${b.x} ${b.y} ${b.w} ${b.h}`);
      copy.setAttribute("preserveAspectRatio", "none");
      Object.assign(copy.style, { position: "static", width: "100%", height: "100%", display: "block", pointerEvents: "none" });
      el.append(copy);
    }
    const handle = div(el, {
      position: "absolute",
      right: "-6px",
      top: "50%",
      width: "10px",
      height: "18px",
      marginTop: "-9px",
      background: "white",
      border: `2px solid ${BLUE}`,
      borderRadius: "3px",
      cursor: "ew-resize",
    });
    editing = { b, x: b.x, y: b.y, w: b.w, el };
    drag(el, (dx, dy) => {
      editing!.x += dx;
      editing!.y += dy;
    });
    drag(handle, (dx) => {
      editing!.w = Math.max(20, editing!.w + dx);
    });
    flash("Drag the label (the handle: width); Enter saves to the source, Esc cancels");
  }

  function render() {
    if (!editing) return;
    Object.assign(editing.el.style, { left: `${editing.x}px`, top: `${editing.y}px`, width: `${editing.w}px` });
  }

  // pointer drag in slide units
  function drag(el: HTMLElement, move: (dx: number, dy: number) => void) {
    el.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      e.stopPropagation();
      el.setPointerCapture(e.pointerId);
      let [lx, ly] = [e.clientX, e.clientY];
      const onMove = (ev: PointerEvent) => {
        const s = opts.scale() || 1;
        move((ev.clientX - lx) / s, (ev.clientY - ly) / s);
        [lx, ly] = [ev.clientX, ev.clientY];
        render();
      };
      const onUp = () => {
        el.removeEventListener("pointermove", onMove);
        el.removeEventListener("pointerup", onUp);
      };
      el.addEventListener("pointermove", onMove);
      el.addEventListener("pointerup", onUp);
    });
  }

  async function save() {
    if (!editing) return;
    const { b, x, y, w } = editing;
    const values: Record<string, string> = { dx: `${round(x - b.tx)}pt`, dy: `${round(y - b.ty)}pt` };
    if (Math.abs(w - b.w) >= 0.5) values.width = `${Math.round(w)}pt`;
    close();
    try {
      const res = await fetch("annot", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ page: b.page, key: b.key, values }),
      });
      const r = await res.json();
      flash(r.error ? `Annotation not saved: ${r.error}` : `Annotation "${b.key}" saved: ${r.file}:${r.line}`);
    } catch (e) {
      flash(`Annotation not saved: ${e}`);
    }
  }

  // --------------------------------------------------------------- keys
  // capture phase: nothing reaches Reveal or the viewer's own keys meanwhile
  function onKey(e: KeyboardEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (e.key === "Escape") {
      close();
      flash("Annotation editor closed, nothing changed");
    } else if (!editing) {
      if (e.key === "Enter") pick(hovered);
      else if (e.key === "Tab" || e.key === "ArrowRight" || e.key === "ArrowDown")
        setHover((hovered + (e.shiftKey ? boxes.length - 1 : 1)) % boxes.length);
      else if (e.key === "ArrowLeft" || e.key === "ArrowUp") setHover((hovered + boxes.length - 1) % boxes.length);
    } else {
      const step = e.shiftKey ? 10 : 1;
      if (e.key === "Enter") save();
      else if (e.key === "ArrowLeft") editing.x -= step;
      else if (e.key === "ArrowRight") editing.x += step;
      else if (e.key === "ArrowUp") editing.y -= step;
      else if (e.key === "ArrowDown") editing.y += step;
      else if (e.key === "+" || e.key === "=") editing.w += 5 * step;
      else if (e.key === "-") editing.w = Math.max(20, editing.w - 5 * step);
      render();
    }
  }
  window.addEventListener("keydown", onKey, true);
}
