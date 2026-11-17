//! The web pages of a deck: typst's SVG of each page, completed with what the
//! viewer needs (the contract is described in docs/viewer.md, "SVG pages"):
//!
//! - the page body in `<g class="typst-page">`, in an `<svg class="typst-svg"
//!   viewBox="0 0 w h">`, content-addressed (its hash names its file);
//! - the glyph outlines (`<symbol id="g…">`) moved out of the pages into one
//!   shared file, referenced by `<use xlink:href="#g…">`;
//! - images as files `img-<hash>.<ext>` (`xlink:href="svg/img-…"`) instead of
//!   data: URIs;
//! - a transparent text layer for selection, find-in-page and copy: one
//!   `<foreignObject>` per text run, holding a `<div class="tsel">` with the
//!   run's text, sized to the run (font-size = the run's size);
//! - links, above the text layer (so that it does not cover them):
//!   external ones open a new tab (`target="_blank"`, except zotero://),
//!   internal ones call `handleTypstLocation(this, page, x, y)`.
//!
//! The pages are rendered in parallel, and a page already rendered (same
//! frame, same link targets) is taken from the cache of the previous build.

use std::collections::{BTreeMap, HashMap};
use std::fmt::Write;
use std::sync::Arc;

use base64::Engine;
use rayon::prelude::*;
use typst::introspection::Introspector;
use typst::layout::{Frame, FrameItem, Point, Transform};
use typst::model::Destination;
use typst::text::TextItem;
use typst::utils::hash128;
use typst_layout::{Page, PagedDocument};

/// One rendered page.
pub struct RenderedPage {
    /// Content hash (names svg/<hash>.svg).
    pub hash: String,
    /// The page's SVG file.
    pub svg: String,
    /// Its glyph definitions: id -> `<symbol>` markup.
    pub glyphs: Vec<(String, String)>,
    /// Its images: file name -> bytes.
    pub images: Vec<(String, Arc<Vec<u8>>)>,
}

/// The rendered pages of a document.
pub struct Rendered {
    pub width: f64,
    pub height: f64,
    pub pages: Vec<Arc<RenderedPage>>,
    /// The shared glyph file: (name, content).
    pub glyphs: (String, String),
}

/// Pages rendered by earlier builds, by key (frame + link targets).
#[derive(Default)]
pub struct PageCache {
    pages: HashMap<u128, Arc<RenderedPage>>,
}

pub fn short_hash(data: impl std::hash::Hash) -> String {
    format!("{:032x}", hash128(&data))[..12].to_owned()
}

pub fn render(doc: &PagedDocument, cache: &mut PageCache) -> Rendered {
    let introspector = doc.introspector();
    let pages = doc.pages();
    // the links of each page, in the order the SVG writes them
    let links: Vec<Vec<PlacedLink>> = pages
        .par_iter()
        .map(|p| {
            let mut out = vec![];
            collect_links(&p.frame, Transform::identity(), &mut out, &**introspector);
            out
        })
        .collect();
    let keys: Vec<u128> = pages
        .par_iter()
        .zip(&links)
        .map(|(p, l)| hash128(&(hash128(p), l)))
        .collect();
    let rendered: Vec<Arc<RenderedPage>> = pages
        .par_iter()
        .zip(&links)
        .zip(&keys)
        .map(|((page, links), key)| match cache.pages.get(key) {
            Some(r) => r.clone(),
            None => Arc::new(render_page(page, links)),
        })
        .collect();
    cache.pages = keys.into_iter().zip(rendered.iter().cloned()).collect();

    let mut glyphs: BTreeMap<&str, &str> = BTreeMap::new();
    for p in &rendered {
        for (id, sym) in &p.glyphs {
            glyphs.entry(id).or_insert(sym);
        }
    }
    let defs: String = glyphs.values().copied().collect();
    let name = format!("glyphs-{}.svg", short_hash(&defs));
    let content = format!(
        "<svg {SVG_NS} class=\"typst-glyphs\" width=\"0\" height=\"0\" \
         style=\"position:absolute;width:0;height:0\" aria-hidden=\"true\"><defs>{defs}</defs></svg>"
    );
    let (width, height) = pages
        .first()
        .map(|p| (p.frame.width().to_pt(), p.frame.height().to_pt()))
        .unwrap_or((842.0, 474.0));
    Rendered {
        width,
        height,
        pages: rendered,
        glyphs: (name, content),
    }
}

const SVG_NS: &str =
    "xmlns=\"http://www.w3.org/2000/svg\" xmlns:xlink=\"http://www.w3.org/1999/xlink\"";

#[derive(Hash, Clone)]
enum Link {
    Url(String),
    /// page (1-based), x, y in pt
    Internal(usize, i64, i64),
    None,
}

/// A link and its box on the page: its transform (page coordinates, as
/// hashable thousandths) and its size (hundredths of a point).
#[derive(Hash, Clone)]
struct PlacedLink {
    link: Link,
    matrix: [i64; 6],
    size: (i64, i64),
}

/// The links of a frame, with their place on the page.
fn collect_links(
    frame: &Frame,
    ts: Transform,
    out: &mut Vec<PlacedLink>,
    introspector: &dyn Introspector,
) {
    for (pos, item) in frame.items() {
        let ts = ts.pre_concat(Transform::translate(pos.x, pos.y));
        match item {
            FrameItem::Group(g) => {
                collect_links(&g.frame, ts.pre_concat(g.transform), out, introspector)
            }
            FrameItem::Link(dest, size) => {
                let link = match dest {
                    Destination::Url(url) => Link::Url(url.as_str().to_owned()),
                    Destination::Position(p) => position(p.page.get(), p.point),
                    Destination::Location(loc) => introspector
                        .position(*loc)
                        .and_then(|p| p.as_paged().map(|p| position(p.page.get(), p.point)))
                        .unwrap_or(Link::None),
                };
                let m = [
                    ts.sx.get(),
                    ts.ky.get(),
                    ts.kx.get(),
                    ts.sy.get(),
                    ts.tx.to_pt(),
                    ts.ty.to_pt(),
                ];
                out.push(PlacedLink {
                    link,
                    matrix: m.map(|v| (v * 1000.0).round() as i64),
                    size: (
                        (size.x.to_pt() * 100.0).round() as i64,
                        (size.y.to_pt() * 100.0).round() as i64,
                    ),
                });
            }
            _ => {}
        }
    }
}

fn position(page: usize, point: Point) -> Link {
    // (hashable: hundredths of a point)
    Link::Internal(
        page,
        (point.x.to_pt() * 100.0).round() as i64,
        (point.y.to_pt() * 100.0).round() as i64,
    )
}

fn render_page(page: &Page, links: &[PlacedLink]) -> RenderedPage {
    let svg = typst_svg::svg(page, &typst_svg::SvgOptions::default());
    let (w, h) = (page.frame.width().to_pt(), page.frame.height().to_pt());

    // the body (between the root tag and the definitions)
    let start = svg.find('>').map(|i| i + 1).unwrap_or(0);
    let end = svg.rfind("</svg>").unwrap_or(svg.len());
    let (body, defs) = match svg[start..end].find("<defs") {
        Some(i) => (&svg[start..start + i], &svg[start + i..end]),
        None => (&svg[start..end], ""),
    };

    let mut images = vec![];
    let body = extract_images(body, &mut images);
    let body = drop_links(&body);
    let link_layer = link_layer(links);
    let (glyphs, defs) = split_glyphs(defs);
    let glyphs = glyphs
        .into_iter()
        .map(|(id, s)| (id, extract_images(&s, &mut images)))
        .collect();
    let defs = extract_images(&defs, &mut images);

    let mut text = String::new();
    text_layer(&page.frame, Transform::identity(), &mut text);

    let file = format!(
        "<svg {SVG_NS} class=\"typst-svg\" viewBox=\"0 0 {w} {h}\" preserveAspectRatio=\"none\">\
         <g class=\"typst-page\">{body}{text}{link_layer}</g>{defs}</svg>"
    );
    RenderedPage {
        hash: short_hash(&file),
        svg: file,
        glyphs,
        images,
    }
}

/// `<symbol id="g…">…</symbol>` out of the definitions: (glyphs, the rest).
fn split_glyphs(defs: &str) -> (Vec<(String, String)>, String) {
    let mut glyphs = vec![];
    let mut rest = String::new();
    let mut i = 0;
    while let Some(k) = defs[i..].find("<symbol id=\"g") {
        let s = i + k;
        rest.push_str(&defs[i..s]);
        let Some(e) = defs[s..].find("</symbol>") else {
            break;
        };
        let e = s + e + "</symbol>".len();
        let id_start = s + "<symbol id=\"".len();
        let id_end = id_start + defs[id_start..].find('"').unwrap_or(0);
        glyphs.push((defs[id_start..id_end].to_owned(), defs[s..e].to_owned()));
        i = e;
    }
    rest.push_str(&defs[i..]);
    // definitions emptied of their glyphs
    let rest = rest.replace("<defs></defs>", "");
    (glyphs, rest)
}

/// data: URIs -> svg/img-<hash>.<ext> (the bytes into `images`).
fn extract_images(s: &str, images: &mut Vec<(String, Arc<Vec<u8>>)>) -> String {
    const MARK: &str = "href=\"data:";
    let mut out = String::with_capacity(s.len());
    let mut i = 0;
    while let Some(k) = s[i..].find(MARK) {
        let at = i + k;
        let data_start = at + MARK.len();
        let Some(end) = s[data_start..].find('"') else {
            break;
        };
        let end = data_start + end;
        let uri = &s[data_start..end];
        let parsed = uri.split_once(";base64,").and_then(|(mime, b64)| {
            let ext = match mime {
                "image/png" => "png",
                "image/jpeg" | "image/jpg" => "jpg",
                "image/gif" => "gif",
                "image/webp" => "webp",
                "image/svg+xml" => "svg",
                _ => return None,
            };
            let bytes = base64::engine::general_purpose::STANDARD.decode(b64).ok()?;
            Some((ext, bytes))
        });
        out.push_str(&s[i..at]);
        match parsed {
            Some((ext, bytes)) => {
                let name = format!("img-{}.{ext}", short_hash(&bytes));
                write!(out, "href=\"svg/{name}\"").unwrap();
                if !images.iter().any(|(n, _)| n == &name) {
                    images.push((name, Arc::new(bytes)));
                }
            }
            None => out.push_str(&s[at..=end]),
        }
        i = end + 1;
    }
    out.push_str(&s[i..]);
    out
}

/// The SVG's own `<a>` taken out: the links are written again above the text
/// layer (link_layer), so that the text layer does not cover them.
fn drop_links(body: &str) -> String {
    let mut out = String::with_capacity(body.len());
    let mut i = 0;
    while let Some(k) = body[i..].find("<a") {
        let at = i + k;
        let next = body.as_bytes().get(at + 2).copied();
        if !matches!(next, Some(b' ') | Some(b'>')) {
            out.push_str(&body[i..at + 2]);
            i = at + 2;
            continue;
        }
        out.push_str(&body[i..at]);
        match body[at..].find("</a>") {
            Some(e) => i = at + e + "</a>".len(),
            None => {
                i = at;
                break;
            }
        }
    }
    out.push_str(&body[i..]);
    out
}

/// The links, in page coordinates: external ones open a new tab (zotero://
/// ones go to the app), internal ones call handleTypstLocation().
fn link_layer(links: &[PlacedLink]) -> String {
    let mut out = String::new();
    for l in links {
        let m = l.matrix.map(|v| fmt(v as f64 / 1000.0));
        let transform = format!(
            "matrix({} {} {} {} {} {})",
            m[0], m[1], m[2], m[3], m[4], m[5]
        );
        let open = match &l.link {
            Link::Url(url) => {
                let url = escape_attr(url);
                if url.starts_with("zotero:") {
                    format!("<a transform=\"{transform}\" xlink:href=\"{url}\">")
                } else {
                    format!(
                        "<a target=\"_blank\" transform=\"{transform}\" href=\"{url}\" xlink:href=\"{url}\">"
                    )
                }
            }
            Link::Internal(page, x, y) => format!(
                "<a transform=\"{transform}\" xlink:href=\"#\" onclick=\"handleTypstLocation(this, {page}, {}, {}); return false\">",
                fmt(*x as f64 / 100.0),
                fmt(*y as f64 / 100.0)
            ),
            Link::None => continue,
        };
        write!(
            out,
            "{open}<rect width=\"{}\" height=\"{}\" fill=\"transparent\" stroke=\"none\"/></a>",
            fmt(l.size.0 as f64 / 100.0),
            fmt(l.size.1 as f64 / 100.0)
        )
        .unwrap();
    }
    out
}

fn escape_attr(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('"', "&quot;")
        .replace('<', "&lt;")
}

fn escape_text(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
}

/// The transparent text of a frame: a `.tsel` per text run, in page
/// coordinates (the run's transform on its foreignObject).
fn text_layer(frame: &Frame, ts: Transform, out: &mut String) {
    for (pos, item) in frame.items() {
        let ts = ts.pre_concat(Transform::translate(pos.x, pos.y));
        match item {
            FrameItem::Group(g) => text_layer(&g.frame, ts.pre_concat(g.transform), out),
            FrameItem::Text(text) => text_run(text, ts, out),
            _ => {}
        }
    }
}

fn text_run(text: &TextItem, ts: Transform, out: &mut String) {
    if text.text.trim().is_empty() {
        return;
    }
    let size = text.size.to_pt();
    let metrics = text.font.metrics();
    let ascent = metrics.ascender.at(text.size).to_pt();
    let descent = -metrics.descender.at(text.size).to_pt();
    let width = text.width().to_pt();
    let height = ascent + descent;
    if width <= 0.0 || height <= 0.0 {
        return;
    }
    let m = [
        ts.sx.get(),
        ts.ky.get(),
        ts.kx.get(),
        ts.sy.get(),
        ts.tx.to_pt(),
        ts.ty.to_pt(),
    ];
    write!(
        out,
        "<foreignObject transform=\"matrix({} {} {} {} {} {})\" x=\"0\" y=\"{:.2}\" \
         width=\"{:.2}\" height=\"{:.2}\"><div class=\"tsel\" style=\"font-size: {}px\">{}</div></foreignObject>",
        fmt(m[0]),
        fmt(m[1]),
        fmt(m[2]),
        fmt(m[3]),
        fmt(m[4]),
        fmt(m[5]),
        -ascent,
        width,
        height,
        fmt(size),
        escape_text(&text.text),
    )
    .unwrap();
}

fn fmt(v: f64) -> String {
    let s = format!("{v:.3}");
    let s = s.trim_end_matches('0').trim_end_matches('.');
    if s == "-0" {
        "0".into()
    } else {
        s.into()
    }
}
