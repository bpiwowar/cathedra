-- Pandoc Lua filter for mdx2typ.py: the fenced divs and spans it writes for
-- slide-app components, HTML elements and CSS classes -> calls to the
-- functions of lib/slides.typ.
--
-- A div's first class says what it was (`.ul`, `.li`, `.cols`, `.frame`,
-- `.definition`…, `.div` for a plain <div>, `.cell` for a grid's cell); the other classes are its
-- className, applied around it by `styled` (styles, spacing, steps). Steps
-- are `#frag(«F»)[…]` (from that step on) / `#frag(«O», only: true)[…]`, numbered by
-- mdx2typ.py once the document is written, in document order.

local blocks = {
  definition = true, observation = true, alert = true, idea = true,
  remark = true, goal = true, motivation = true, question = true,
  problem = true, solution = true, theorem = true, example = true,
}

-- CSS classes -> slides.typ functions of one content argument
local styles = {
  hand = "hand", comment = "comment", warning = "warning",
  ["positive-aspect"] = "pro", ["negative-aspect"] = "con",
  boxed = "boxed", boxbox = "boxed", small = "small",
  red = "text(fill: red)", blue = "text(fill: blue)",
  bold = "strong", center = "align(center)", centered = "align(center)",
  ["h-center"] = "align(center)", ["v-center"] = "align(center + horizon)",
  ["two-columns"] = "columns(2)", sup = "super", sub = "sub",
  ["strike-through"] = "strike", code = 'text(font: "DejaVu Sans Mono", size: 0.85em)',
}
-- the course's own classes (mdx2typ.py --classes)
local course = {}
if os.getenv("MDX_CLASSES") then course = pandoc.json.decode(os.getenv("MDX_CLASSES")) end
-- classes that only matter to the structure, or that have no Typst meaning
local handled = {
  fragment = true, only = true, exclusive = true, space = true, space2x = true, spaced = true,
  spaced2x = true, cell = true, div = true, ul = true, ol = true, li = true, dl = true, dt = true,
  dd = true, p = true, h = true, cols = true, frame = true, focus = true,
  synopsis = true, citation = true, todo = true,
}
for k in pairs(blocks) do handled[k] = true end

-- MathJax-only LaTeX that texmath (pandoc's maths converter) cannot parse:
-- one such command and pandoc gives up on the whole formula, writing it as
-- escaped text (`\$\$\\mathbf{x}…\$\$`). Rewritten before the writer sees it:
--  * `\cssId{id}{x}`, `\htmlId`, `\class`… (highlight targets): x;
--  * `\color{c}` (a switch, up to the end of its group), `\textcolor{c}{x}`,
--    `\scriptsize`, `\small`… (switches): a carrier `\overbrace{x}^{\text{@kind:arg}}`,
--    turned into `#text(fill: c, $x$)` / `script(x)` / `#text(size: …)` by
--    mdx2typ.py once the Typst is written (math_carriers);
--  * `\tilde \mathbf{t}` (an argument that is itself a command with an
--    argument, from macros like `\tilde \tokens`): `\tilde{\mathbf{t}}`.
local wrappers = { cssId = 2, htmlId = 2, class = 2, htmlClass = 2, style = 2, htmlStyle = 2, href = 2 }
local sizes = {
  tiny = "0.5em", scriptsize = "script", footnotesize = "0.8em", small = "0.9em",
  normalsize = "1em", large = "1.2em", Large = "1.44em", LARGE = "1.73em", huge = "2.07em", Huge = "2.49em",
}
local one_arg = {
  tilde = true, hat = true, bar = true, vec = true, dot = true, ddot = true, breve = true,
  check = true, acute = true, grave = true, mathring = true, widetilde = true, widehat = true,
  overline = true, underline = true, overrightarrow = true, mathbf = true, boldsymbol = true,
  bm = true, mathrm = true, mathit = true, mathsf = true, mathtt = true, mathcal = true,
  mathbb = true, mathfrak = true, operatorname = true, sqrt = true,
}

-- the group starting at s[i] == "{": its content, and the index after it
local function group(s, i)
  local depth, j = 0, i
  while j <= #s do
    local c = s:sub(j, j)
    if c == "\\" then
      j = j + 1
    elseif c == "{" then
      depth = depth + 1
    elseif c == "}" then
      depth = depth - 1
      if depth == 0 then return s:sub(i + 1, j - 1), j + 1 end
    end
    j = j + 1
  end
  return s:sub(i + 1), #s + 1
end

-- a command's argument at s[i] (after spaces): its text, and the index after it
local function argument(s, i)
  i = s:find("%S", i) or #s + 1
  local c = s:sub(i, i)
  if c == "{" then return group(s, i) end
  local cs = s:match("^\\%a+", i) or s:sub(i, i + (c == "\\" and 1 or 0))
  return cs, i + #cs
end

-- where a switch (\color, \small) stops: the end of its group, or a cell /
-- row separator, \right or \end at its level
local function scope_end(s, i)
  local depth, j = 0, i
  while j <= #s do
    local c = s:sub(j, j)
    if c == "{" then
      depth = depth + 1
    elseif c == "}" then
      depth = depth - 1
    elseif c == "&" and depth == 0 then
      return j
    elseif c == "\\" then
      local name = s:match("^\\(%a+)", j)
      if name == "left" or name == "begin" then
        depth = depth + 1
      elseif name == "right" or name == "end" then
        if depth == 0 then return j end
        depth = depth - 1
      elseif s:sub(j + 1, j + 1) == "\\" and depth == 0 then
        return j
      end
      j = j + (name and #name or 1)
    end
    j = j + 1
  end
  return #s + 1
end

local function carrier(body, kind, arg)
  if not body:find("%S") then return "" end
  return "\\overbrace{" .. body .. "}^{\\text{@" .. kind .. ":" .. arg .. "}}"
end

local function fix_tex(s)
  local out, i = {}, 1
  while i <= #s do
    local c = s:sub(i, i)
    local name = s:match("^\\(%a+)", i)
    if name and wrappers[name] then
      local j, body = i + 1 + #name, nil
      for _ = 1, wrappers[name] do body, j = argument(s, j) end
      table.insert(out, "{" .. fix_tex(body) .. "}")
      i = j
    elseif name == "textcolor" then
      local color, j = argument(s, i + 1 + #name)
      local body, k = argument(s, j)
      table.insert(out, carrier(fix_tex(body), "color", color))
      i = k
    elseif name == "color" or (name and sizes[name]) then
      local j, kind, arg = i + 1 + #name, "size", sizes[name]
      if name == "color" then
        kind = "color"
        arg, j = argument(s, j)
      end
      local stop = scope_end(s, j)
      table.insert(out, carrier(fix_tex(s:sub(j, stop - 1)), kind, arg))
      i = stop
    elseif name then
      table.insert(out, "\\" .. name)
      i = i + 1 + #name
    elseif c == "\\" then
      table.insert(out, s:sub(i, i + 1))
      i = i + 2
    elseif c == "{" then
      local body, j = group(s, i)
      table.insert(out, "{" .. fix_tex(body) .. "}")
      i = j
    else
      table.insert(out, c)
      i = i + 1
    end
  end
  s = table.concat(out)
  -- `\tilde \mathbf{t}` -> `\tilde{\mathbf{t}}`
  return (s:gsub("\\(%a+)(%s*)(\\%a+%s*%b{})", function(cmd, _, arg)
    if one_arg[cmd] then return "\\" .. cmd .. "{" .. arg .. "}" end
  end))
end

function Math(el)
  el.text = fix_tex(el.text)
  return el
end

local function inline_typst(md)
  -- markdown (with $math$) -> typst markup, without trailing newline
  -- (with the decks' MathJax macros, as the body: mdx2typ.py's MDX_MACROS)
  local doc = pandoc.read((os.getenv("MDX_MACROS") or "") .. "\n\n" .. md, "markdown-auto_identifiers+latex_macros")
    :walk({ Math = Math })
  local out = pandoc.write(doc, "typst")
  return (out:gsub("%s+$", ""))
end

local function raw(s) return pandoc.RawBlock("typst", s) end

local function typst_blocks(bs)
  return (pandoc.write(pandoc.Pandoc(bs), "typst"):gsub("%s+$", ""))
end

local function wrap(open, content, close)
  local out = { raw(open) }
  for _, b in ipairs(content) do table.insert(out, b) end
  table.insert(out, raw(close or "]"))
  return out
end

local function has(classes, c)
  for _, x in ipairs(classes) do if x == c then return true end end
  return false
end

-- the step a fragment appears at, or nil
local function step_of(classes)
  if has(classes, "fragment") then
    return (has(classes, "only") or has(classes, "exclusive")) and "«O»" or "«F»"
  end
end

-- Apply the style classes (and spacing, steps) around `content` (blocks).
-- styles that give inline content: a <div> with one is a block of its own
local inline_styles = {
  comment = true, warning = true, ["positive-aspect"] = true, ["negative-aspect"] = true,
  boxed = true, small = true, red = true, blue = true, bold = true,
}

local function styled(classes, content, skip_step, inline)
  local out = content
  local unknown = {}
  for i = #classes, 1, -1 do
    local c = classes[i]
    local f = course[c] or styles[c]
    if f then
      out = wrap("#" .. f .. "[", out)
    elseif not handled[c] then
      table.insert(unknown, c)
    end
  end
  if not inline then
    for _, c in ipairs(classes) do
      if inline_styles[c] then out = wrap("#block[", out); break end
    end
  end
  if #unknown > 0 then
    table.insert(out, 1, raw("// TODO-REVIEW: class " .. table.concat(unknown, " ")))
  end
  local space = has(classes, "space2x") and "2em" or (has(classes, "space") and "1em")
  if space then table.insert(out, 1, raw("#v(" .. space .. ")")) end
  local step = not skip_step and step_of(classes)
  if step then
    out = wrap("#frag(" .. step .. (step == "«O»" and ", only: true" or "") .. ")[", out)
  end
  return out
end

local function children(el, cls)
  local out = {}
  for _, b in ipairs(el.content) do
    if b.t == "Div" and b.classes[1] == cls then table.insert(out, b) end
  end
  return out
end

-- A list item's paragraphs as plain text (a tight list), unless two text
-- blocks follow each other (they would merge into one paragraph).
local function tight(bs)
  local out = pandoc.List(bs)
  for i, b in ipairs(out) do
    local nxt = out[i + 1]
    if b.t == "Para" and not (nxt and (nxt.t == "Para" or nxt.t == "Plain")) then
      out[i] = pandoc.Plain(b.content)
    end
  end
  return out
end

local function list(el)
  local numbered = el.classes[1] == "ol"
  local lis = children(el, "li")
  local spacing = has(el.classes, "spaced2x") and "1em" or (has(el.classes, "spaced") and "0.8em")
  local steps = false
  for _, li in ipairs(lis) do if step_of(li.classes) then steps = true end end
  if not steps then
    local items = {}
    for _, li in ipairs(lis) do
      local cls = pandoc.List(li.classes):filter(function(c) return c ~= "li" end)
      table.insert(items, styled(cls, tight(li.content)))
    end
    local l = numbered and pandoc.OrderedList(items, pandoc.ListAttributes(tonumber(el.attributes.start) or 1))
      or pandoc.BulletList(items)
    local out = { l }
    if spacing then
      out = wrap("#[#set " .. (numbered and "enum" or "list") .. "(spacing: " .. spacing .. ")", out)
    end
    return out
  end
  -- items appearing in steps: #items (lib/slides.typ), so that a hidden
  -- item keeps its place
  local args = {}
  if numbered then table.insert(args, "numbered: true") end
  if el.attributes.start then table.insert(args, "start: " .. el.attributes.start) end
  if el.attributes.depth and el.attributes.depth ~= "1" then
    table.insert(args, "depth: " .. el.attributes.depth)
  end
  if spacing then table.insert(args, "spacing: " .. spacing) end
  local s = "#items(" .. table.concat(args, ", ") .. (#args > 0 and "," or "") .. "\n"
  for _, li in ipairs(lis) do
    local cls = pandoc.List(li.classes):filter(function(c) return c ~= "li" end)
    local body = typst_blocks(styled(cls, tight(li.content), true))
    local step = step_of(li.classes)
    if step == "«O»" then step = "«F»" end -- (no "only" item: it would leave a gap)
    s = s .. "  " .. (step and ("step(" .. step .. ")") or "") .. "[" .. body .. "],\n"
  end
  return { raw(s .. ")") }
end

local function cols(el)
  local widths = ""
  if el.attributes.widths then
    local ws = {}
    for w in el.attributes.widths:gmatch("%S+") do table.insert(ws, w) end
    widths = "widths: (" .. table.concat(ws, ", ") .. (#ws == 1 and "," or "") .. ")"
  end
  local out = { raw("#cols(" .. widths .. ")[") }
  local first = true
  for _, b in ipairs(el.content) do
    if b.t == "Div" and b.classes[1] == "cell" then
      if not first then table.insert(out, raw("][")) end
      first = false
      for _, x in ipairs(b.content) do table.insert(out, x) end
    else
      table.insert(out, b)
    end
  end
  table.insert(out, raw("]"))
  return out
end

local function title_arg(attrs, name)
  name = name or "title"
  if attrs[name] and attrs[name] ~= "" then
    return name .. ": [" .. inline_typst(attrs[name]) .. "]"
  end
end

local function args(...)
  local xs = {}
  for _, x in ipairs({ ... }) do if x then table.insert(xs, x) end end
  return #xs > 0 and ("(" .. table.concat(xs, ", ") .. ")") or ""
end

function Div(el)
  local c = el.classes[1]
  local rest = pandoc.List(el.classes):filter(function(x) return x ~= c end)
  local attrs = el.attributes
  local base
  if c == "li" or c == "cell" then
    return nil -- consumed by the enclosing list / grid
  elseif c == "ul" or c == "ol" then
    base = list(el)
  elseif c == "cols" then
    base = cols(el)
  elseif blocks[c] then
    base = wrap("#" .. c .. args(title_arg(attrs)) .. "[", el.content)
  elseif c == "frame" then
    local kind = attrs.kind and attrs.kind ~= "block" and ('kind: "' .. attrs.kind .. '"') or nil
    base = wrap("#frame" .. args(kind, title_arg(attrs)) .. "[", el.content)
  elseif c == "focus" then
    local w = attrs.width and ("width: " .. attrs.width) or nil
    base = wrap("#focus" .. args(w) .. "[", el.content)
  elseif c == "synopsis" then
    return wrap("#synopsis[", el.content)
  elseif c == "citation" then
    local src = title_arg(attrs, "source")
    return wrap("#quote" .. args("block: true", src and src:gsub("^source:", "attribution:"))  .. "[", el.content)
  elseif c == "h" then
    local level = attrs.level ~= "1" and ("level: " .. attrs.level) or nil
    base = wrap("#subhead" .. args(level) .. "[", el.content)
  elseif c == "figure" then
    -- <figure><img/><figcaption>…</figcaption></figure> -> #figure(img(…), caption: […])
    local img, cap
    for i, b in ipairs(el.content) do
      if not img and b.t == "RawBlock" and b.text:match("^#img%(.*%)$") then img = i end
      if not cap and b.t == "Div" and b.classes[1] == "figcaption" then cap = i end
    end
    if img and cap then
      local call = el.content[img].text
      local out = {}
      for i, b in ipairs(el.content) do
        if i == img then
          table.insert(out, raw("#figure(" .. call:sub(2) .. ", caption: ["))
          for _, x in ipairs(el.content[cap].content) do table.insert(out, x) end
          table.insert(out, raw("])"))
        elseif i ~= cap then
          table.insert(out, b)
        end
      end
      base = out
    else
      base = {}
      for _, b in ipairs(el.content) do
        if b.t == "Div" and b.classes[1] == "figcaption" then
          for _, x in ipairs(wrap("#text(size: 0.75em)[", b.content)) do table.insert(base, x) end
        else
          table.insert(base, b)
        end
      end
    end
  elseif c == "figcaption" then
    return nil -- consumed by its <figure> (filters run on inner divs first)
  elseif c == "dt" then
    -- a term list item, Typst's own: #terms.item([term], [description])
    base = wrap("#terms.item([", el.content, "],")
  elseif c == "dd" then
    base = wrap("[", el.content, "])")
  elseif c == "todo" then
    return wrap("// TODO-REVIEW (slide-app className=todo)\n#[", el.content)
  elseif c == "div" or c == "p" or c == "dl" then
    base = el.content
  else
    rest = el.classes -- a plain <div className=…>: all classes are styles
    base = el.content
  end
  if c == "dl" and (has(rest, "spaced") or has(rest, "spaced2x")) then
    -- more room above each term
    local gap = has(rest, "spaced2x") and "1.2em" or "0.9em"
    base = wrap("#[\n#set terms(spacing: " .. gap .. ")", base)
  end
  return styled(rest, base)
end

function Span(el)
  local out = el.content
  local step
  for i = #el.classes, 1, -1 do
    local c = el.classes[i]
    local f = course[c] or styles[c]
    if f then
      table.insert(out, 1, pandoc.RawInline("typst", "#" .. f .. "["))
      table.insert(out, pandoc.RawInline("typst", "]"))
    end
  end
  step = step_of(el.classes)
  if step then
    table.insert(out, 1, pandoc.RawInline("typst", "#frag(" .. step .. (step == "«O»" and ", only: true" or "") .. ")["))
    table.insert(out, pandoc.RawInline("typst", "]"))
  end
  return out
end

-- {/* comments */} were turned into HTML comments: keep them as Typst comments
function RawBlock(el)
  if el.format == "html" then
    local inner = el.text:match("^<!%-%-%s*(.-)%s*%-%->$")
    if inner then
      local lines = {}
      for l in (inner .. "\n"):gmatch("(.-)\n") do table.insert(lines, "// " .. l) end
      return raw(table.concat(lines, "\n"))
    end
  end
end

-- Simple tables: emit a plain #table (pandoc's default wraps it in a figure)
function Table(el)
  local function cell_typst(cell)
    return typst_blocks(cell.contents)
  end
  local head, body = {}, {}
  local ncols = #el.colspecs
  for _, row in ipairs(el.head.rows) do
    for _, cell in ipairs(row.cells) do table.insert(head, "[" .. cell_typst(cell) .. "]") end
  end
  for _, tb in ipairs(el.bodies) do
    for _, row in ipairs(tb.body) do
      for _, cell in ipairs(row.cells) do table.insert(body, "[" .. cell_typst(cell) .. "]") end
    end
  end
  local aligns = {}
  for _, cs in ipairs(el.colspecs) do
    local a = cs[1]
    table.insert(aligns, a == "AlignRight" and "right" or a == "AlignCenter" and "center" or "left")
  end
  local s = "#table(\n  columns: " .. ncols .. ",\n  align: (" .. table.concat(aligns, ", ") .. (ncols == 1 and "," or "") .. "),\n"
  if #head > 0 then s = s .. "  table.header(" .. table.concat(head, ", ") .. "),\n" end
  local rows = {}
  for i = 1, #body, ncols do
    table.insert(rows, "  " .. table.concat({ table.unpack(body, i, i + ncols - 1) }, ", ") .. ",")
  end
  return raw(s .. table.concat(rows, "\n") .. "\n)")
end

-- Global functions: pandoc runs them bottom-up (a list sees its items, a grid
-- its cells, still as divs), inlines first.
