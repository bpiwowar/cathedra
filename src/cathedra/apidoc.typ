// The doc comments (`///`) of Typst files, parsed by tidy (apidoc.py).
// sys.inputs: {file name: its source}; one `<api>` metadata per file:
// (file: name, module: tidy's parse-module result).
#import "@preview/tidy:0.4.3"

#for (name, src) in sys.inputs.pairs() {
  [#metadata((file: name, module: tidy.parse-module(src, name: name)))<api>]
}
