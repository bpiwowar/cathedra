# Interactive widgets (React or plain JS)

A slide can hold a live component, drawn over the page in the browser: a
React component, which can also wrap plain JavaScript (D3, a canvas, a
library that wants a DOM node). The printable PDF shows a static fallback
instead.

## In the slide

```typst
#interactive("wand", height: 9.2cm,
  props: (terms: wand-terms, k: 1),
  fallback: [a static version, for the printable PDF])
```

- `id`: the widget's name in the course's `widgets/index.ts`;
- `width` (default 100%), `height` (default 5cm): the slot it is drawn in,
  laid out by Typst like any box (in a column, a frame…);
- `props`: passed to the component, as JSON: numbers, strings, booleans,
  arrays, dictionaries (not content: `[…]` does not survive); e.g. data read
  with `json("data/x.json")`;
- `steps`: the number of animation steps, when the component does not say;
- `fallback`: what the PDF shows (default: a dashed frame naming the
  widget). On the web the slot is left empty under the widget.

### In the PDF and the handout

`make pdf` and `make handout` show pictures of the widget, taken in headless
Chrome. A picture is of a widget **state**: props added to the widget's
`props` for the picture. The widget reaches that state by itself: steps
shown, epochs trained, a simulation run… A number `n` is short for
`(step: n)`; `(:)` is the widget as it is (its final step). The component
also receives `snapshot: true`, to leave out what only makes sense live (a
play button, a slider).

| | The PDF shows |
|---|---|
| (default) | a picture of `(:)`, unless there is a `fallback` |
| `snapshot: true` / `false` | the same, even with a `fallback` / never a picture |
| `snapshot: (epochs: 50)` | that state |
| `snapshots: ((:), (epochs: 10), (epochs: 50))` | one state per step of the slide, in order (steps 1, 2, 3) |
| `snapshots: ("1": 0, two: 2, all: 4)` | the same, by step name (`"1"`: the unnamed first step) |

With `snapshots`, the slide has as many steps in print (counted by
themselves; named ones are declared with `#steps("…")`): its pages in the
PDF are its steps, and each picture shows from its step on. A handout shows
the last one.

```typst
// a word2vec with a play button: three moments of the training
#steps("ten", "fifty")
#interactive("word2vec", height: 9cm, props: (corpus: "fr"),
  snapshots: ("1": (epochs: 0), ten: (epochs: 10), fifty: (epochs: 50)))
```

```tsx
// the widget: live, a play button; for a picture, train up to `epochs`
export function Word2Vec({ corpus, epochs, snapshot, onReady }: Props) {
  const [model, epoch, train] = useTraining(corpus);
  useEffect(() => {
    if (epochs === undefined) return;
    if (epoch < epochs) train(1); else onReady(); // reached: take the picture
  }, [epoch, epochs]);
  return <>{!snapshot && <PlayButton onClick={…} />}<Plot model={model} /></>;
}
// widgets/index.ts:  word2vec: { component: Word2Vec, async: true }
```

On the web the widget ignores all this: it starts from its `props` (and its
own steps come after the slide's).

`make snapshots`, which `pdf` and `handout` run first, takes the pictures.
One browser serves every deck, and it starts only when a picture is missing.
The pictures go to `.cache/widgets/` (ignored by git), named by the slot
(id, props, steps, size), the state and the widgets' code, so an unchanged
widget is not rendered again.

The picture is taken when the widget is ready, through events, not a delay:

- a widget that draws as it mounts: once React has rendered, the fonts and
  the images are loaded, and the network is idle;
- a widget that takes time to reach the state (it loads data, trains,
  animates): register it with `async: true`, and call the `onReady` prop
  when it is there (on the web `onReady` does nothing). Without the call,
  the picture is taken after `WIDGET_TIMEOUT` ms (default 30000), with a
  warning.

```tsx
export function Embeddings({ url, onReady }: { url: string; onReady: () => void }) {
  const [data, setData] = useState<number[][] | null>(null);
  useEffect(() => { fetch(url).then((r) => r.json()).then(setData); }, [url]);
  useEffect(() => { if (data) onReady(); }, [data]); // drawn: take the picture
  return data ? <Plot points={data} /> : <p>loading…</p>;
}
// widgets/index.ts:  embeddings: { component: Embeddings, async: true }
```

- The pictures are taken by headless Chromium through Playwright
  (`cathedra[browser]`, then `playwright install chromium`; a cathedra
  checkout has the extra), or by Chrome (`$CHROME`, then the usual install
  places) when Playwright has no browser of its own. Without either, the
  PDFs show the fallbacks (or the dashed frame).
- `WIDGET_SCALE` (default 3) sets the picture's pixels per pt.
- The pictures are listed in `.cache/widgets/manifest.json`, which the
  course's `common/course.typ` reads and gives to the template
  (`widget-shots`) when cathedra compiles. A plain `typst compile` shows
  the fallbacks (or the dashed frame).

A widget can stand in for a figure drawn in steps, keeping the figure for the
PDF:

```typst
#interactive("word2vec", height: 10cm, props: json("figures/data/word2vec.json"),
  fallback: at-step(word2vec))
```

## The course's widgets

A course registers its widgets in `widgets/index.ts`, at its root (next to
`common/`, `lectures/`):

```ts
import { Saturation } from "./Saturation";
import { Animation, animationSteps } from "./Animation";

export default {
  saturation: { component: Saturation },
  animation: { component: Animation, steps: (p: any) => animationSteps(p) },
};
```

- `component`: a React function component;
- `steps(props)`, optional: how many steps the animation has, for these
  props;
- `async: true`, optional: the widget calls `onReady` when its picture can
  be taken (see [in the PDF](#in-the-pdf-and-the-handout)).

The build bundles `widgets/index.ts` and what it imports into
`out/<deck>/widgets.js` with [esbuild](https://esbuild.github.io/) (the
course's `node_modules/.bin/esbuild`, else one on the `PATH`, else the
official binary, downloaded once into the user cache: no Node needed);
TypeScript and TSX need no configuration. `react`, `react-dom` and
`react/jsx-runtime` are the viewer's (one copy for the page: the bundle's
imports of them are shims reading the viewer's React). Other packages are
looked up as Node does, from `widgets/` upwards (the `node_modules` of the
nearest package: the course's, or the directory above it): a course whose
widgets use packages (e.g. `d3`) has a `package.json` and installs them
(`pnpm add d3`). A deck of a course without widgets needs none of this. The
dev server rebuilds and reloads when a widget file changes; `make html`
bundles them for the site.

### A React component

```tsx
// widgets/Counter.tsx
import React, { useState } from "react";

export function Counter({ start = 0 }: { start?: number }) {
  const [n, setN] = useState(start);
  return (
    <div style={{ fontSize: 24, display: "flex", gap: 12, alignItems: "center" }}>
      <button onClick={() => setN(n - 1)}>−</button> {n}
      <button onClick={() => setN(n + 1)}>+</button>
    </div>
  );
}
```

```typst
#interactive("counter", height: 2cm, props: (start: 3))
```

### Plain JavaScript

Wrap the code in a component that hands it a DOM node, and cleans up when the
widget goes away:

```tsx
// widgets/Scatter.tsx
import React, { useEffect, useRef } from "react";
import * as d3 from "d3";

export function Scatter({ points }: { points: [number, number][] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const svg = d3.select(ref.current!).append("svg").attr("width", "100%").attr("height", "100%");
    // … draw with d3, plain DOM calls, a canvas…
    return () => svg.remove(); // props changed, or the widget was removed
  }, [points]);
  return <div ref={ref} style={{ width: "100%", height: "100%" }} />;
}
```

## Animations

A widget with steps gets that many Reveal fragments on its slide: → and ←
drive it like any other step. The component receives `step`: the number of
its fragments shown, 0 before the first.

```tsx
export function Grow({ step }: { step: number }) {
  return <div style={{ width: 40 + 60 * step, height: 40, background: "steelblue", transition: "width .3s" }} />;
}
// widgets/index.ts:  grow: { component: Grow, steps: () => 4 }
```

The widget's fragments come after the slide's own steps (`#steps`,
`#pause`…): the page is complete before the animation starts.

## Sizes, positions, keys

- The widget is a `div` placed over the slot, of the slot's size, in slide
  units: 1 CSS px = 1 Typst pt (a 16:9 slide is about 842 × 474 px). Reveal
  scales the whole slide, widget included, to the window: write sizes in px
  as if the slide were its Typst size, or in % of the slot.
- Reveal's slide typography is reset in the slot: fonts and sizes are the
  component's own.
- The widget keeps its state while the deck is live-reloaded, as long as it
  stays on the deck (it is identified by its id and occurrence: the 2nd
  `counter` of the deck…); its position and props are updated in place.
- Keys typed in an `<input>`, `<textarea>` or contenteditable element of the
  widget go to it, not to Reveal.

## The engine's widgets

`todo-note`: the work-in-progress marker of `#todo("…")` (hidden by M).

`svg-object`: an SVG as a document of its own, scripts and links working
(`#svg-object`, see [images](images.md#interactive-svg); props: `svg`, the
file's text). Defined in `src/engine-widgets.tsx`, registered in
`src/main.tsx`.
