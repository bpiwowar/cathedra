// Notifications over the deck (slide-app's src/notifications.ts): short
// messages stacked in the bottom-right corner, outside the scaled slide.
//
//   toast("Reconnected")                              info, 3 s
//   toast("Typst: 2 errors", { kind: "error" })       stays until replaced
//   toast("3 slides overflow", { action: { label: "O", run } })
//   toast("…", { id: "server" })                      replaces the toast of that id
//
// `flash` (slide-types.ts) is the bigger, centred notice for what happens
// during the talk (M, the end of details); toasts are for the author: the
// dev server, builds, tools.
import { t } from "./i18n";

export type ToastKind = "info" | "success" | "warning" | "error";
export type ToastOptions = {
  kind?: ToastKind;
  // milliseconds before it goes; 0 = until closed or replaced (errors: 0 by default)
  ms?: number;
  // a toast with the same id replaces it
  id?: string;
  action?: { label: string; run: () => void };
};

const STYLE = `
#toasts { position: fixed; right: 14px; bottom: 14px; z-index: 3500; display: flex;
  flex-direction: column; align-items: flex-end; gap: 8px; pointer-events: none;
  font: 14px/1.35 system-ui, sans-serif; }
#toasts .toast { pointer-events: auto; display: flex; gap: 10px; align-items: center;
  max-width: min(460px, calc(100vw - 28px)); padding: 8px 10px 8px 12px; border-radius: 8px;
  background: rgb(20 20 30 / 0.92); color: #fff; box-shadow: 0 6px 20px rgb(0 0 0 / 0.3);
  border-left: 4px solid #6c8cff; opacity: 0; transform: translateY(8px);
  transition: opacity 0.25s, transform 0.25s; }
#toasts .toast.on { opacity: 1; transform: none; }
#toasts .toast.success { border-left-color: #3cb371; }
#toasts .toast.warning { border-left-color: #f0a020; }
#toasts .toast.error { border-left-color: #e04848; }
#toasts .toast button { font: inherit; font-size: 13px; color: #fff; cursor: pointer;
  background: rgb(255 255 255 / 0.14); border: 1px solid rgb(255 255 255 / 0.3);
  border-radius: 5px; padding: 1px 8px; }
#toasts .toast .x { background: none; border: none; opacity: 0.6; padding: 0 2px; }
#deck-loading { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center;
  z-index: 3400; color: #ccc; font: 18px system-ui, sans-serif; pointer-events: none; }
@media print { #toasts, #deck-loading { display: none; } }
`;

function host() {
  let el = document.getElementById("toasts");
  if (!el) {
    const style = document.createElement("style");
    style.textContent = STYLE;
    document.head.append(style);
    el = document.body.appendChild(document.createElement("div"));
    el.id = "toasts";
    el.setAttribute("role", "status");
  }
  return el;
}

/** Show a notification; returns a function that closes it. */
export function toast(message: string, opts: ToastOptions = {}): () => void {
  const kind = opts.kind ?? "info";
  const box = host();
  if (opts.id) box.querySelector(`.toast[data-id="${CSS.escape(opts.id)}"]`)?.remove();
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  if (opts.id) el.dataset.id = opts.id;
  const text = el.appendChild(document.createElement("span"));
  text.textContent = message;
  const close = () => {
    el.classList.remove("on");
    setTimeout(() => el.remove(), 300);
  };
  if (opts.action) {
    const b = el.appendChild(document.createElement("button"));
    b.textContent = opts.action.label;
    b.onclick = () => {
      opts.action!.run();
      close();
    };
  }
  const x = el.appendChild(document.createElement("button"));
  x.className = "x";
  x.textContent = "✕";
  x.title = t("close");
  x.onclick = close;
  box.append(el);
  requestAnimationFrame(() => el.classList.add("on"));
  const ms = opts.ms ?? (kind === "error" ? 0 : kind === "warning" ? 5000 : 3000);
  if (ms > 0) setTimeout(close, ms);
  return close;
}

/** Close the toast of that id, if shown. */
export function closeToast(id: string) {
  document.querySelector(`#toasts .toast[data-id="${CSS.escape(id)}"]`)?.remove();
}

// "Loading…" until the deck is shown (main.tsx calls `loaded()`)
let loading: HTMLElement | null = null;
export function showLoading() {
  host();
  loading = document.body.appendChild(document.createElement("div"));
  loading.id = "deck-loading";
  loading.textContent = t("loading");
}
export function loaded() {
  loading?.remove();
  loading = null;
}
