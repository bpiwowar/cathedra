//! The Typst world of a deck: the course directory as the project root,
//! packages as the typst CLI finds them (data and cache directories, Typst
//! Universe), fonts shared by every world of the process.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, LazyLock};

use parking_lot::Mutex;
use typst::diag::FileResult;
use typst::foundations::{Bytes, Datetime, Dict, Duration, IntoValue};
use typst::syntax::{FileId, RootedPath, Source, VirtualPath, VirtualRoot};
use typst::text::{Font, FontBook};
use typst::utils::LazyHash;
use typst::{Library, LibraryExt, World};
use typst_kit::datetime::Time;
use typst_kit::diagnostics::DiagnosticWorld;
use typst_kit::downloader::SystemDownloader;
use typst_kit::files::{FileStore, FsRoot, SystemFiles};
use typst_kit::fonts::FontStore;
use typst_kit::packages::SystemPackages;

/// Font stores by font directories: scanning the system fonts takes a while,
/// it is done once per process.
static FONTS: LazyLock<Mutex<HashMap<Vec<PathBuf>, Arc<FontStore>>>> =
    LazyLock::new(Default::default);

pub fn fonts(paths: &[PathBuf]) -> Arc<FontStore> {
    let mut all = FONTS.lock();
    all.entry(paths.to_vec())
        .or_insert_with(|| {
            let mut store = FontStore::new();
            for p in paths {
                store.extend(typst_kit::fonts::scan(p));
            }
            store.extend(typst_kit::fonts::system());
            store.extend(typst_kit::fonts::embedded());
            Arc::new(store)
        })
        .clone()
}

pub fn library(inputs: &HashMap<String, String>) -> LazyHash<Library> {
    let dict: Dict = inputs
        .iter()
        .map(|(k, v)| (k.as_str().into(), v.as_str().into_value()))
        .collect();
    LazyHash::new(Library::builder().with_inputs(dict).build())
}

pub struct SlidesWorld {
    root: PathBuf,
    workdir: PathBuf,
    main: FileId,
    library: LazyHash<Library>,
    fonts: Arc<FontStore>,
    files: FileStore<SystemFiles>,
    now: Time,
}

impl SlidesWorld {
    pub fn new(
        root: &Path,
        main: &Path,
        fonts: Arc<FontStore>,
        library: LazyHash<Library>,
    ) -> Result<Self, String> {
        let root = root
            .canonicalize()
            .map_err(|e| format!("root {}: {e}", root.display()))?;
        let main_path = main
            .canonicalize()
            .map_err(|e| format!("{}: {e}", main.display()))?;
        let vpath = VirtualPath::virtualize(&root, &main_path)
            .map_err(|_| format!("{} is not under {}", main.display(), root.display()))?;
        let main = RootedPath::new(VirtualRoot::Project, vpath).intern();
        let user_agent = concat!("typst-slides/", env!("CARGO_PKG_VERSION"));
        let packages = SystemPackages::new(SystemDownloader::new(user_agent));
        Ok(Self {
            workdir: std::env::current_dir().unwrap_or_else(|_| root.clone()),
            files: FileStore::new(SystemFiles::new(FsRoot::new(root.clone()), packages)),
            root,
            main,
            library,
            fonts,
            now: Time::system(),
        })
    }

    pub fn set_library(&mut self, library: LazyHash<Library>) {
        self.library = library;
    }

    /// Prepares a new compilation: the files are read again (the sources
    /// edited in place, so that typst's incremental compilation applies).
    pub fn reset(&mut self) {
        self.files.reset();
        self.now.reset();
    }

    /// The files the last compilation read.
    pub fn dependencies(&mut self) -> Vec<PathBuf> {
        let (loader, deps) = self.files.dependencies();
        let mut out: Vec<PathBuf> = deps.filter_map(|id| loader.resolve(id).ok()).collect();
        out.sort();
        out
    }
}

impl World for SlidesWorld {
    fn library(&self) -> &LazyHash<Library> {
        &self.library
    }

    fn book(&self) -> &LazyHash<FontBook> {
        self.fonts.book()
    }

    fn main(&self) -> FileId {
        self.main
    }

    fn source(&self, id: FileId) -> FileResult<Source> {
        self.files.source(id)
    }

    fn file(&self, id: FileId) -> FileResult<Bytes> {
        self.files.file(id)
    }

    fn font(&self, index: usize) -> Option<Font> {
        self.fonts.font(index)
    }

    fn today(&self, offset: Option<Duration>) -> Option<Datetime> {
        self.now.today(offset)
    }
}

impl DiagnosticWorld for SlidesWorld {
    fn name(&self, id: FileId) -> String {
        let vpath = id.vpath();
        match id.root() {
            VirtualRoot::Project => vpath
                .realize(&self.root)
                .ok()
                .and_then(|p| pathdiff(&p, &self.workdir))
                .unwrap_or_else(|| vpath.get_without_slash().into()),
            VirtualRoot::Package(package) => format!("{package}{}", vpath.get_with_slash()),
        }
    }
}

/// `path` relative to `base` (both absolute), as the typst CLI prints it.
fn pathdiff(path: &Path, base: &Path) -> Option<String> {
    let p: Vec<_> = path.components().collect();
    let b: Vec<_> = base.components().collect();
    let common = p.iter().zip(&b).take_while(|(x, y)| x == y).count();
    if common == 0 {
        return None;
    }
    let mut out = PathBuf::new();
    for _ in common..b.len() {
        out.push("..");
    }
    for c in &p[common..] {
        out.push(c);
    }
    Some(out.to_string_lossy().into_owned())
}
