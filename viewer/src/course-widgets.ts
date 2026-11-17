// The course's own React widgets: widgets.js next to the page, bundled by
// cathedra from the course's widgets/index.ts (`export default { id:
// {component, steps?, async?} }`) when it has one (`data-widgets` on the
// body). The bundle does not carry React: its `react`, `react-dom` and
// `react/jsx-runtime` imports are shims (data/viewer-shims/) reading the
// viewer's copy from the global set here, so that there is one React.
import React from "react";
import * as ReactDOM from "react-dom";
import * as ReactDOMClient from "react-dom/client";
import * as jsxRuntime from "react/jsx-runtime";

(globalThis as any).__typstSlides = { React, ReactDOM, ReactDOMClient, jsxRuntime };

/** The course's widgets ({} without a widgets.js). */
export async function loadCourseWidgets(): Promise<Record<string, unknown>> {
  const version = document.body.dataset.widgets;
  if (!version) return {};
  try {
    const url = new URL(`widgets.js?v=${version}`, location.href).href;
    return ((await import(/* @vite-ignore */ url)) as { default?: Record<string, unknown> }).default ?? {};
  } catch (e) {
    console.error("widgets.js:", e);
    return {};
  }
}
