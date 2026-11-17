// Widgets of the engine itself (registered in main.tsx next to `todo-note`),
// used by functions of lib/slides.typ.
import React from "react";

// `#svg-object(path("x.svg"))`: the SVG as a document of its own (slide-app's
// `<object>`), so that its links, hover styles and scripts work. The PDF
// shows it as a picture (the widget's fallback).
export function SvgObject({ svg }: { svg: string }) {
  const url = React.useMemo(() => URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" })), [svg]);
  React.useEffect(() => () => URL.revokeObjectURL(url), [url]);
  return <object type="image/svg+xml" data={url} style={{ width: "100%", height: "100%", display: "block" }} />;
}
