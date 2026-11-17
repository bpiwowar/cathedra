// The page `cathedra snapshots` photographs: one widget at a time, at its
// slot's size, in a given state: props added to its own (`step` among them;
// without one, the final step). The component also gets `snapshot: true`, to
// leave out what only makes sense live (a play button…).
// The picture is taken when the widget is ready: at once for a widget that
// draws as it mounts; for one registered with `async: true` (it loads data,
// trains, animates…), when it calls its `onReady` prop. Then the fonts and
// images must be loaded, and (snapshots.py) the network idle.
import React from "react";
import { createRoot, type Root } from "react-dom/client";
import { loadCourseWidgets } from "./course-widgets";

type Widget = { component: React.FC<any>; steps?: (props: any) => number; async?: boolean };
const widgets = (await loadCourseWidgets()) as Record<string, Widget>;
const slot = document.getElementById("slot")!;
let root: Root | null = null;
const frames = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));

declare global {
  interface Window {
    // -> "ok", "missing" (no such widget) or "timeout" (onReady not called)
    renderWidget: (id: string, props: any, state: Record<string, any>, steps: number | null, w: number, h: number, timeout: number) => Promise<string>;
  }
}

window.renderWidget = async (id, props, state, steps, w, h, timeout) => {
  root?.unmount();
  slot.replaceChildren();
  const reg = widgets[id];
  if (!reg) return "missing";
  Object.assign(slot.style, { width: `${w}px`, height: `${h}px` });
  const Component = reg.component;
  const all = { ...(props ?? {}), ...(state ?? {}) };
  const step = all.step ?? steps ?? reg.steps?.(all) ?? 0;
  let onReady = () => {};
  const ready = reg.async ? new Promise<void>((r) => (onReady = r)) : Promise.resolve();
  root = createRoot(slot);
  root.render(<Component {...all} step={step} snapshot onReady={() => onReady()} />);
  let status = "ok";
  await Promise.race([ready, new Promise((r) => setTimeout(() => ((status = "timeout"), r(null)), timeout))]);
  await frames(); // React has committed, the browser has laid out
  await document.fonts.ready;
  await Promise.all([...slot.querySelectorAll("img")].map((i) => i.decode().catch(() => {})));
  await frames();
  return status;
};
