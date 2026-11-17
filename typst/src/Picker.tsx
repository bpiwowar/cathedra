import React from "react";
import { t } from "./i18n";

// A list to pick from (Z: Zotero items, O: overflowing slides, the slide to
// go back to from details): ↑ ↓ or a row number, Enter or a click picks,
// Esc closes. Styled as the structure browser (structure-browser.css).

export type PickItem = {
  label: string;
  detail?: string; // grey, on the right (a file:line, a number)
  // extra actions on the row (e.g. "edit"), with a key
  actions?: { label: string; key?: string; run: () => void }[];
};

export function Picker(props: {
  title: string;
  items: PickItem[];
  onPick: (i: number) => void;
  onClose: () => void;
  empty?: string;
  help?: string;
}) {
  const { title, items, onPick, onClose } = props;
  const [sel, setSel] = React.useState(0);
  const ref = React.useRef<HTMLDivElement>(null);
  React.useEffect(() => ref.current?.focus(), []);
  React.useEffect(() => {
    ref.current?.querySelector(".sb-row.selected")?.scrollIntoView({ block: "nearest" });
  });
  const onKey = (e: React.KeyboardEvent) => {
    const n = Number(e.key);
    if (e.key === "Escape") onClose();
    else if (e.key === "ArrowDown") setSel((i) => Math.min(items.length - 1, i + 1));
    else if (e.key === "ArrowUp") setSel((i) => Math.max(0, i - 1));
    else if (e.key === "Enter" && items[sel]) onPick(sel);
    else if (n >= 1 && n <= Math.min(9, items.length)) onPick(n - 1);
    else {
      const a = items[sel]?.actions?.find((a) => a.key && a.key.toLowerCase() === e.key.toLowerCase());
      if (!a) return;
      a.run();
    }
    e.preventDefault();
    e.stopPropagation();
  };
  return (
    <div className="sb-overlay" tabIndex={-1} ref={ref} onKeyDown={onKey} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sb-panel">
        <div className="sb-header">
          <strong>{title}</strong>
          <span className="sb-spacer" />
          <button onClick={onClose} title={t("close")}>
            ✕
          </button>
        </div>
        <div className="sb-list">
          {items.length === 0 && <div className="sb-row context">{props.empty ?? ""}</div>}
          {items.map((it, i) => (
            <div
              key={i}
              className={`sb-row${i === sel ? " selected" : ""}`}
              onMouseEnter={() => setSel(i)}
              onClick={() => onPick(i)}
            >
              <span className="sb-number" style={{ width: "1.5em", textAlign: "left" }}>
                {i < 9 ? i + 1 : ""}
              </span>
              <span className="sb-title">{it.label}</span>
              {it.detail && <span className="sb-file">{it.detail}</span>}
              {it.actions?.map((a) => (
                <button
                  key={a.label}
                  className="picker-action"
                  onClick={(e) => {
                    e.stopPropagation();
                    a.run();
                  }}
                >
                  {a.label}
                </button>
              ))}
            </div>
          ))}
        </div>
        <div className="sb-help">{props.help ?? t("picker.help")}</div>
      </div>
    </div>
  );
}
