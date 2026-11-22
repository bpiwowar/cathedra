// Syntax highlighting of the help's code blocks (```lang): highlight.js core
// with the languages the docs use, and a small Typst grammar (highlight.js
// has none). An unknown or missing language is left plain.
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import ini from "highlight.js/lib/languages/ini";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import makefile from "highlight.js/lib/languages/makefile";
import python from "highlight.js/lib/languages/python";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import type { HLJSApi, Language } from "highlight.js";

// Typst: markup with `#` code, `$…$` math, comments, strings, labels
// (<label>), references (@key), headings (= …), lengths (2em, 50%).
function typst(hljs: HLJSApi): Language {
  // (not `and`, `or`, `not`, `in`, `as`: words of the markup too)
  const KEYWORDS = [
    "let", "set", "show", "import", "include", "if", "else", "for", "while",
    "break", "continue", "return", "context",
  ];
  const LITERALS = ["none", "auto", "true", "false"];
  const STRING = { scope: "string", begin: /"/, end: /"/, contains: [hljs.BACKSLASH_ESCAPE] };
  const NUMBER = { scope: "number", begin: /\b\d+(?:\.\d+)?(?:pt|mm|cm|in|em|fr|deg|rad|%)?/ };
  return {
    name: "Typst",
    aliases: ["typ"],
    keywords: { keyword: KEYWORDS, literal: LITERALS },
    contains: [
      hljs.C_LINE_COMMENT_MODE,
      hljs.C_BLOCK_COMMENT_MODE,
      { scope: "section", begin: /^=+\s.*$/m },
      STRING,
      { scope: "keyword", begin: new RegExp(`#(?:${KEYWORDS.join("|")})\\b`) },
      // a call: #name(…) / #name[…] / name(…), dotted (cetz.draw.line)
      { scope: "title.function", begin: /#?[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)*(?=[([])/ },
      { scope: "variable", begin: /#[A-Za-z_][\w-]*(?:\.[A-Za-z_][\w-]*)*/ },
      { scope: "symbol", begin: /<[\w:.-]+>/ },
      { scope: "link", begin: /@[\w:.-]+/ },
      { scope: "formula", begin: /\$/, end: /\$/, contains: [hljs.BACKSLASH_ESCAPE] },
      NUMBER,
    ],
  };
}

const LANGUAGES: Record<string, (h: HLJSApi) => Language> = {
  bash, css, ini, javascript, json, makefile, python, typescript, xml, yaml, typst,
};
for (const [name, lang] of Object.entries(LANGUAGES)) hljs.registerLanguage(name, lang);
hljs.registerAliases(["sh", "shell", "zsh", "console"], { languageName: "bash" });
hljs.registerAliases(["ts", "tsx"], { languageName: "typescript" });
hljs.registerAliases(["js", "jsx", "mjs"], { languageName: "javascript" });
hljs.registerAliases(["py"], { languageName: "python" });
hljs.registerAliases(["make", "mk"], { languageName: "makefile" });
hljs.registerAliases(["toml"], { languageName: "ini" });
hljs.registerAliases(["yml"], { languageName: "yaml" });
hljs.registerAliases(["html", "svg"], { languageName: "xml" });

/** The code as highlighted HTML; "" (markdown-it escapes it) when the
 * language is unknown. */
export function highlight(code: string, lang: string): string {
  if (!lang || !hljs.getLanguage(lang)) return "";
  try {
    return hljs.highlight(code, { language: lang, ignoreIllegals: true }).value;
  } catch {
    return "";
  }
}
