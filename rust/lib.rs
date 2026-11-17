//! typst_slides._native: Typst for typst-slides.
//!
//! - `Compiler(root, main, font_paths, inputs)`: a warm compiler for one deck
//!   (the course directory as Typst's root). Each `compile()` reads the files
//!   again; typst's memoization (shared by every compiler of the process)
//!   redoes only what changed. The GIL is released while compiling and
//!   exporting, so decks compile in parallel from Python threads.
//! - `Document`: `pages()` (the web pages, see pages.rs), `pdf()`,
//!   `query(selector, field)`.
//! - diagnostics as the typst CLI prints them.

mod pages;
mod world;

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Arc;

use comemo::Track;
use parking_lot::Mutex;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict};
use typst::diag::{Severity, SourceDiagnostic, Warned};
use typst::engine::Sink;
use typst::foundations::{Context, IntoValue, LocatableSelector, Scope};
use typst::introspection::{EmptyIntrospector, Introspector};
use typst::routines::SpanMode;
use typst::syntax::{Span, SyntaxMode};
use typst::World;
use typst_layout::PagedDocument;

use world::SlidesWorld;

fn err(e: impl std::fmt::Display) -> PyErr {
    PyRuntimeError::new_err(e.to_string())
}

/// A diagnostic: severity ("error" | "warning"), message, and the text the
/// typst CLI prints for it (location, source excerpt, hints).
#[pyclass(frozen, get_all, module = "typst_slides._native")]
#[derive(Clone)]
struct Diagnostic {
    severity: String,
    message: String,
    text: String,
}

#[pymethods]
impl Diagnostic {
    fn __repr__(&self) -> String {
        format!("Diagnostic({}: {})", self.severity, self.message)
    }
}

fn diagnostics(world: &SlidesWorld, diags: &[SourceDiagnostic]) -> Vec<Diagnostic> {
    diags
        .iter()
        .map(|d| {
            let mut w = termcolor::NoColor::new(Vec::new());
            let text = match typst_kit::diagnostics::emit(
                &mut w,
                world,
                std::iter::once(d),
                typst_kit::diagnostics::DiagnosticFormat::Human,
            ) {
                Ok(()) => String::from_utf8_lossy(&w.into_inner()).into_owned(),
                Err(_) => d.message.to_string(),
            };
            Diagnostic {
                severity: match d.severity {
                    Severity::Error => "error",
                    Severity::Warning => "warning",
                }
                .to_owned(),
                message: d.message.to_string(),
                text: text.trim_end().to_owned(),
            }
        })
        .collect()
}

/// A compiled document.
#[pyclass(frozen, module = "typst_slides._native")]
struct Document {
    doc: Arc<PagedDocument>,
    world: Arc<Mutex<SlidesWorld>>,
    cache: Arc<Mutex<pages::PageCache>>,
}

#[pymethods]
impl Document {
    #[getter]
    fn num_pages(&self) -> usize {
        self.doc.pages().len()
    }

    /// The web pages: a dict {width, height, pages: [(hash, svg)], glyphs:
    /// (name, svg), images: {name: bytes}}.
    fn pages<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyDict>> {
        let doc = self.doc.clone();
        let cache = self.cache.clone();
        let r = py.allow_threads(move || pages::render(&doc, &mut cache.lock()));
        let out = PyDict::new(py);
        out.set_item("width", r.width)?;
        out.set_item("height", r.height)?;
        let list: Vec<(String, String)> = r
            .pages
            .iter()
            .map(|p| (p.hash.clone(), p.svg.clone()))
            .collect();
        out.set_item("pages", list)?;
        out.set_item("glyphs", r.glyphs)?;
        let images = PyDict::new(py);
        for p in &r.pages {
            for (name, bytes) in &p.images {
                if !images.contains(name)? {
                    images.set_item(name, PyBytes::new(py, bytes))?;
                }
            }
        }
        out.set_item("images", images)?;
        Ok(out)
    }

    /// The PDF; `tagged`: a tagged PDF (accessibility), as the typst CLI.
    #[pyo3(signature = (tagged = true))]
    fn pdf<'py>(&self, py: Python<'py>, tagged: bool) -> PyResult<Bound<'py, PyBytes>> {
        let doc = self.doc.clone();
        let world = self.world.clone();
        let result = py.allow_threads(move || {
            let options = typst_pdf::PdfOptions {
                tagged,
                ..Default::default()
            };
            typst_pdf::pdf(&doc, &options).map_err(|errors| {
                let world = world.lock();
                diagnostics(&world, &errors)
                    .into_iter()
                    .map(|d| d.text)
                    .collect::<Vec<_>>()
                    .join("\n")
            })
        });
        match result {
            Ok(bytes) => Ok(PyBytes::new(py, &bytes)),
            Err(e) => Err(err(e)),
        }
    }

    /// PNG pictures of the pages (all, or the 0-based `pages`), at `ppi`.
    #[pyo3(signature = (ppi = 144.0, pages = None))]
    fn png<'py>(
        &self,
        py: Python<'py>,
        ppi: f32,
        pages: Option<Vec<usize>>,
    ) -> PyResult<Vec<Bound<'py, PyBytes>>> {
        use rayon::prelude::*;
        let doc = self.doc.clone();
        let encoded = py.allow_threads(move || {
            let all = doc.pages();
            let which: Vec<usize> = pages.unwrap_or_else(|| (0..all.len()).collect());
            which
                .par_iter()
                .map(|&i| {
                    let page = all.get(i).ok_or_else(|| format!("no page {i}"))?;
                    let options = typst_render::RenderOptions {
                        pixel_per_pt: typst::utils::Scalar::new(f64::from(ppi) / 72.0),
                        ..Default::default()
                    };
                    typst_render::render(page, &options)
                        .encode_png()
                        .map_err(|e| e.to_string())
                })
                .collect::<Result<Vec<_>, String>>()
        });
        match encoded {
            Ok(list) => Ok(list.iter().map(|b| PyBytes::new(py, b)).collect()),
            Err(e) => Err(PyValueError::new_err(e)),
        }
    }

    /// The elements matching `selector` (Typst code, e.g. "<page-marker>"),
    /// as JSON: their `field`, or the whole elements (with their label).
    #[pyo3(signature = (selector, field = None))]
    fn query(&self, py: Python<'_>, selector: String, field: Option<String>) -> PyResult<String> {
        let doc = self.doc.clone();
        let world = self.world.clone();
        py.allow_threads(move || {
            let world = world.lock();
            let world: &dyn World = &*world;
            let selector = typst_eval::eval_string(
                world.track(),
                world.library(),
                Sink::new().track_mut(),
                EmptyIntrospector.track(),
                Context::none().track(),
                &selector,
                SpanMode::Uniform(Span::detached()),
                SyntaxMode::Code,
                Scope::default(),
            )
            .map_err(|errors| {
                let msgs: Vec<_> = errors.iter().map(|e| e.message.to_string()).collect();
                PyValueError::new_err(format!("failed to evaluate selector: {}", msgs.join(", ")))
            })?
            .cast::<LocatableSelector>()
            .map_err(|e| PyValueError::new_err(e.message().to_string()))?;
            let values: Vec<_> = doc
                .introspector()
                .query(&selector.0)
                .into_iter()
                .filter_map(|c| match &field {
                    Some(f) => c.get_by_name(f).ok(),
                    None => Some(c.into_value()),
                })
                .collect();
            serde_json::to_string(&values).map_err(err)
        })
    }
}

/// The result of a compilation: the document (None on error), the
/// diagnostics (errors, then warnings) and the files it read.
#[pyclass(frozen, get_all, module = "typst_slides._native")]
struct CompileResult {
    document: Option<Py<Document>>,
    diagnostics: Vec<Diagnostic>,
    dependencies: Vec<PathBuf>,
}

/// A warm compiler for one deck.
#[pyclass(frozen, module = "typst_slides._native")]
struct Compiler {
    world: Arc<Mutex<SlidesWorld>>,
    cache: Arc<Mutex<pages::PageCache>>,
}

#[pymethods]
impl Compiler {
    #[new]
    #[pyo3(signature = (root, main, font_paths = Vec::new(), inputs = HashMap::new()))]
    fn new(
        py: Python<'_>,
        root: PathBuf,
        main: PathBuf,
        font_paths: Vec<PathBuf>,
        inputs: HashMap<String, String>,
    ) -> PyResult<Self> {
        let world = py
            .allow_threads(|| {
                SlidesWorld::new(
                    &root,
                    &main,
                    world::fonts(&font_paths),
                    world::library(&inputs),
                )
            })
            .map_err(PyValueError::new_err)?;
        Ok(Self {
            world: Arc::new(Mutex::new(world)),
            cache: Default::default(),
        })
    }

    /// Changes `sys.inputs` for the next compilations.
    fn set_inputs(&self, inputs: HashMap<String, String>) {
        self.world.lock().set_library(world::library(&inputs));
    }

    /// Compiles the deck (its files read again).
    fn compile(&self, py: Python<'_>) -> PyResult<CompileResult> {
        let world = self.world.clone();
        let (doc, diags, deps) = py.allow_threads(move || {
            let mut w = world.lock();
            w.reset();
            let Warned { output, warnings } = typst::compile::<PagedDocument>(&*w);
            let mut all: Vec<SourceDiagnostic> = vec![];
            let doc = match output {
                Ok(doc) => Some(Arc::new(doc)),
                Err(errors) => {
                    all.extend(errors.iter().cloned());
                    None
                }
            };
            all.extend(warnings.iter().cloned());
            let diags = diagnostics(&w, &all);
            let deps = w.dependencies();
            (doc, diags, deps)
        });
        let document = match doc {
            Some(doc) => Some(Py::new(
                py,
                Document {
                    doc,
                    world: self.world.clone(),
                    cache: self.cache.clone(),
                },
            )?),
            None => None,
        };
        Ok(CompileResult {
            document,
            diagnostics: diags,
            dependencies: deps,
        })
    }
}

/// Evicts typst's memoization cache: results unused for `max_age`
/// compilations are dropped (0: everything).
#[pyfunction]
fn evict_cache(max_age: usize) {
    comemo::evict(max_age);
}

/// The version of the Typst compiler embedded.
#[pyfunction]
fn typst_version() -> &'static str {
    "0.15.1"
}

#[pymodule]
fn _native(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<Compiler>()?;
    m.add_class::<Document>()?;
    m.add_class::<CompileResult>()?;
    m.add_class::<Diagnostic>()?;
    m.add_function(wrap_pyfunction!(evict_cache, m)?)?;
    m.add_function(wrap_pyfunction!(typst_version, m)?)?;
    Ok(())
}
