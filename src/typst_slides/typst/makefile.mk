# makefile.mk — the make targets of a Typst slide course (typst-slides).
#
# The course Makefile sets the options it needs, then includes this file. Its
# directory is Typst's root (lib/, .cache/, out/); the sources (lectures/,
# modules/, common/, widgets/) are there too, or in SRC:
#
#   SLIDES_SCHEDULE := ../../course.yaml
#   BIB             := ../src/main.bib
#   include slide-app/makefile.mk          (the link `typst-slides setup` makes)
#   include slide-app/typst/makefile.mk    (slide-app as a git submodule)
#
# The targets run the `typst-slides` command (TYPST_SLIDES): the released
# package through uvx by default, or, when this file is in a checkout of
# slide-app (e.g. the course's submodule), that checkout's own version through
# `uv run --project` (edits are picked up at once; Rust edits rebuild the
# extension). See docs/course.md.
#
# Options (set before the include):
#   BIB              the Zotero / Better BibTeX bibliography (required)
#   SLIDES_SCHEDULE  YAML with `lectures: [{id, title, target}]`: deck titles,
#                    order and target times for `make outline` (optional)
#   DECK             the deck `make serve` shows (default: the first one)
#   PORT             dev server port (default 8000)
#   SOCKET           serve on this Unix socket instead of PORT
#   MDX_SRC          slide-app MDX modules, for `make convert` (../src/modules)
#   MDX_MACROS       their MathJax macros (../src/lectures/common/macros.tex)
#   MDX_LECTURES     slide-app MDX decks, for `make convert LECTURE=` (../src/lectures)
#   OUT              output directory (out)
#   SRC              the sources' directory, under the course's (.)
#   DECKS            the decks html / pdf / check build (all of $(SRC)/lectures/:
#                    a deck <id> is lectures/<id>.typ or lectures/<id>/<id>.typ)
#   DEV              DEV=1: `make html` builds for the author (E opens the
#                    sources, references link to Zotero), as `make serve` does

#@option BIB the Zotero / Better BibTeX bibliography (required) {set by the course}
#@option SOCKET serve on this Unix socket instead of PORT {none}
#@option DEV DEV=1: `make html` builds for the author (E opens the sources, references link to Zotero) {unset}
TYPST_APP       := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
# the checkout of slide-app this file is in, if any (textually: TYPST_APP may
# be a link)
SLIDE_APP_DEV   := $(patsubst %/,%,$(dir $(TYPST_APP)))
#@option TYPST_SLIDES the typst-slides command {uv run --project <checkout> typst-slides in a checkout of slide-app, else uvx typst-slides}
ifneq ($(wildcard $(SLIDE_APP_DEV)/src/typst_slides/__init__.py),)
TYPST_SLIDES    ?= uv run --quiet --all-extras --project $(SLIDE_APP_DEV) typst-slides
else
TYPST_SLIDES    ?= uvx typst-slides
endif
#@option SRC the sources (lectures/, modules/, common/, widgets/); this directory stays Typst's root (lib/, .cache/, out/)
SRC             ?= .
export SLIDES_SRC := $(SRC)
# A deck <id>: $(SRC)/lectures/<id>/<id>.typ, or $(SRC)/lectures/<id>.typ
deck-file = $(firstword $(wildcard $(SRC)/lectures/$(1)/$(1).typ) $(SRC)/lectures/$(1).typ)
#@option DECKS the decks html / pdf / check build {every deck of $(SRC)/lectures/}
DECKS           ?= $(sort $(patsubst $(SRC)/lectures/%.typ,%,$(wildcard $(SRC)/lectures/*.typ)) \
                     $(foreach d,$(patsubst %/,%,$(wildcard $(SRC)/lectures/*/)),$(if $(wildcard $(d)/$(notdir $(d)).typ),$(notdir $(d)))))
#@option DECK the deck `make serve` shows {the first of DECKS}
DECK            ?= $(firstword $(DECKS))
#@option PORT dev server port
PORT            ?= 8000
#@option OUT output directory
OUT             ?= out
#@option MDX_SRC slide-app MDX modules, for `make convert`
MDX_SRC         ?= ../src/modules
#@option MDX_MACROS their MathJax macros
MDX_MACROS      ?= ../src/lectures/common/macros.tex
#@option MDX_LECTURES slide-app MDX decks, for `make convert LECTURE=`
MDX_LECTURES    ?= ../src/lectures
#@option MDX_BACKUP where `make convert` moves each MDX file it converted {none: left in place}
MDX_BACKUP      ?=
#@option SLIDES_SCHEDULE YAML listing the decks (`lectures:` with id, title, target): titles, order and target times for `make outline` {none}
SLIDES_SCHEDULE ?=
export SLIDES_SCHEDULE

# The course site (`typst-slides site`): the decks of the schedule, the index page,
# the PDFs, deployed by rsync. `dev: true` decks are in the dev site only.
#@option DESTDIR the site `make site` builds and `make deploy` publishes
DESTDIR         ?= $(OUT)/site
#@option DESTDIR_DEV the dev site (with the `dev: true` decks), `make site-dev` / `deploy-dev`
DESTDIR_DEV     ?= $(OUT)/site-dev
#@option STATIC a directory copied as is into the site, e.g. the `externalPdf` files {none}
STATIC          ?=
#@option PRACTICAL_MANIFEST the practicals' JSON manifest (index links), refreshed by the `practical-manifest::` hook {none}
PRACTICAL_MANIFEST ?=
#@option DEPLOY_DEST where `make deploy` rsyncs the site, e.g. host:/var/www/course/ {none}
DEPLOY_DEST     ?=
#@option DEPLOY_DEST_DEV where `make deploy-dev` rsyncs the dev site {none}
DEPLOY_DEST_DEV ?=
#@option DEPLOY_PDF no: deploy without (re)compiling the PDFs
DEPLOY_PDF      ?= yes
#@option ZIP_OUT the archive `make zip` writes {$(DESTDIR).zip}
ZIP_OUT         ?= $(DESTDIR).zip
#@option COURSE_PORT port of `make serve-course` (index + every deck)
COURSE_PORT     ?= 9010

TS       := $(TYPST_SLIDES)
GEN      := lib/refs.bib lib/refs-links.json slide-app

.PHONY: help update-makefile check-makefile unused-media optimize-images compute-svg-bb install-vscode open-slide images check-images setup outline outline-slides duplicates serve html build snapshots pdf handout check format convert space live-test clean migrate check-version

# `make help`: the text below, in sections. A line at column 0 is a section
# title, "  <target>  <description>" an entry, a deeper line its continuation.
# A course adds its own section with HELP_PROJECT (a define, exported; also
# taken from the environment, e.g. from a wrapper Makefile).
define HELP_TEXT
Typst slides (slide-app/typst) — decks: $(DECKS)

Set up
  setup           the engine link (slide-app), bibliography
  install-vscode  VS Code task (show the slide under the cursor) and Tinymist settings

Write and preview
  serve           dev server for DECK=$(DECK) on http://localhost:$(PORT)
                  (live reload; H help, T outline + slide types, M todo markers,
                  E edit slide, shift-E include chain)
  open-slide      FILE=<.typ> LINE=<n>: move the running deck to that slide
  outline         deck structure, slide counts and time vs the schedule's target
  outline-slides  the same, with every slide and its file:line
  duplicates      the files #included more than once (by one deck or several)

Build the decks
  html / build    the web decks, $(OUT)/<deck>/
  pdf             printable PDFs, $(OUT)/<deck>.pdf (every step)
  handout         handouts, $(OUT)/<deck>-handout.pdf (the last step of each slide)
  snapshots       pictures of the React widgets for pdf / handout (headless Chromium,
                  typst-slides[browser])
  clean           remove $(OUT)/

Check
  check           compile every deck, fail on errors or overflowing slides
  live-test       browser checks of the viewer (typst-slides[browser], pytest)

Images and media
  images          fetch the images given by URL / origin (Zotero) into .cache/images,
                  downsampled
  check-images    list the heavy images of the course (> 1 MB or > 2400 px)
  optimize-images  PNG/JPEG/GIF -> WebP, capped in size, references rewritten
                  (DRY=1, PRUNE=1)
  compute-svg-bb  trim SVGs to their content: SVG=<files or dirs> (default
                  $(SRC)/modules $(SRC)/common), APPLY=1 writes
  unused-media    media files no .typ references (CLEAN=1 removes them)

Maintain the sources
  format          indent every .typ of the course (typstyle)
  space           blank lines between slides in every .typ (idempotent)
  migrate         migrate the sources to the engine's API version (DRY=1: diff
                  only, see docs/upgrading.md)
  convert         MODULE=<topic>: port $(MDX_SRC)/<topic>/<topic>.mdx
                  (MODULE=<dir>/<file>: <dir>/<file>.mdx; LECTURE=<id>: the deck
                  $(MDX_LECTURES)/<id>/<id>.mdx -> $(SRC)/lectures/<id>[/<id>].typ)
                  (overwrites hand edits of the .typ: check git diff;
                  MDX_BACKUP=<dir>: moves each converted .mdx there)
  update-makefile / check-makefile  refresh / verify the generated option list
                  of the Makefile

Course site (decks of the schedule + index page)
  serve-course    dev server: index + every deck on http://localhost:$(COURSE_PORT)
  site / site-dev  $(DESTDIR)/ / $(DESTDIR_DEV)/ (dev: with the dev: true decks)
  site-pdf / site-pdf-dev  PDFs of the pdf: true decks into <site>/pdf/
                  (MD5-cached; FORCE=1)
  site-force / site-dev-force  the same, from an empty directory
  deploy / deploy-dev  site + PDFs, rsync to DEPLOY_DEST(_DEV) (DRY=1: rsync -n;
                  DEPLOY_PDF=no)
  zip             $(ZIP_OUT) (the site, PDFs excluded)
endef
export HELP_TEXT
HELP_PROJECT ?=
export HELP_PROJECT

# Colours, when the output is a terminal and NO_COLOR is unset
# (https://no-color.org): a section title in bold, a target in cyan.
# HELP_COLOR=yes|no forces it either way.
HELP_COLOR ?= auto
define HELP_AWK
/^[^ ]/ { print b $$0 r; next }
/^  [^ ]/ { t = substr($$0, 3); n = index(t, "  "); if (!n) n = length(t) + 1; print "  " c substr(t, 1, n - 1) r substr(t, n); next }
{ print }
endef
export HELP_AWK

help:
	@if [ "$(HELP_COLOR)" = yes ] || { [ "$(HELP_COLOR)" = auto ] && [ -t 1 ] && [ -z "$$NO_COLOR" ]; }; then \
		b=$$(printf '\033[1m'); c=$$(printf '\033[36m'); r=$$(printf '\033[0m'); \
	else b=; c=; r=; fi; \
	{ printf '%s\n' "$$HELP_TEXT"; \
	  [ -z "$$HELP_PROJECT" ] || printf '\n%s\n' "$$HELP_PROJECT"; \
	} | awk -v b="$$b" -v c="$$c" -v r="$$r" "$$HELP_AWK"

# The API version the sources are migrated to (.slide-app-version, missing = 1)
# against the engine's (VERSION): a warning, not an error. See docs/upgrading.md.
check-version:
	@have=$$(cat .slide-app-version 2>/dev/null || echo 1); want=$$(cat $(TYPST_APP)/VERSION 2>/dev/null || echo 1); \
	  [ "$$have" -ge "$$want" ] || echo "warning: the course is at slide-app API $$have, the engine at $$want: run 'make migrate DRY=1' then 'make migrate' (docs/upgrading.md)" >&2

migrate:
	@$(TS) migrate $(if $(DRY),--dry-run)

# the engine, as the decks import it (/slide-app/lib/slides.typ: a link to
# the package's Typst files); a course with slide-app as a submodule in its
# directory imports /slide-app/typst/lib/slides.typ, and this rule does nothing
slide-app:
	@$(TS) setup

setup:
	$(TS) setup $(BIB)

# the bibliography and its links, refreshed when the bib changes
lib/refs.bib lib/refs-links.json: $(BIB)
	$(TS) sync $(BIB)

outline: $(GEN)
	@$(TS) outline $(DECKS)

outline-slides: $(GEN)
	@$(TS) outline --slides $(DECKS)

duplicates:
	@$(TS) outline --duplicates $(DECKS)

serve: $(GEN) images check-version
	$(TS) serve $(call deck-file,$(DECK)) --out=$(OUT) $(if $(SOCKET),--socket=$(SOCKET),--port=$(PORT))

html build: $(GEN) images check-version
	@$(TS) build --out=$(OUT) $(if $(DEV),--dev) $(foreach d,$(DECKS),$(call deck-file,$(d)))

# Pictures of the React widgets (#interactive) for the PDFs: one headless
# Chromium for all the decks, only for the pictures not in .cache/widgets yet.
# Without a browser, or if it fails, the PDFs show the widgets' fallbacks.
snapshots: $(GEN)
	@$(TS) snapshots $(foreach d,$(DECKS),$(call deck-file,$(d))) || echo "snapshots failed: the PDFs show the widgets' fallbacks"

# Images fetched at build time (#img with a URL, or an origin and no file):
# downloaded and shrunk into .cache/images, listed in its manifest, which the
# compilations get as `img-cache` (sys.inputs). See docs/images.md.
images:
	@$(TS) images || echo "images: some images could not be fetched"

check-images:
	@$(TS) images --check

pdf: $(GEN) images snapshots check-version
	@$(TS) pdf --out=$(OUT) $(foreach d,$(DECKS),$(call deck-file,$(d)))

handout: $(GEN) images snapshots
	@$(TS) pdf --handout --out=$(OUT) $(foreach d,$(DECKS),$(call deck-file,$(d)))

# Touying reports a slide past the canvas as a warning ("overflow"): an error here.
check: $(GEN)
	@$(TS) check --out=$(OUT) $(foreach d,$(DECKS),$(call deck-file,$(d)))

convert: $(GEN)
	@test -n "$(MODULE)$(LECTURE)" || { echo "usage: make convert MODULE=<topic>[/<file>] | LECTURE=<id>"; exit 2; }
	$(if $(MODULE),$(TS) convert --src $(MDX_SRC) --macros $(MDX_MACROS) $(if $(MDX_BACKUP),--backup $(MDX_BACKUP)) $(MODULE))
	$(if $(LECTURE),$(TS) convert --deck --src $(MDX_LECTURES) --macros $(MDX_MACROS) $(if $(MDX_BACKUP),--backup $(MDX_BACKUP)) $(LECTURE))

format:
	@command -v typstyle >/dev/null || { echo "format: needs typstyle (brew install typstyle)"; exit 2; }
	typstyle -i $(wildcard $(addprefix $(SRC)/,common/*.typ lectures/*.typ lectures/*/*.typ lectures/*/figures/*.typ modules/*/*.typ modules/*/figures/*.typ))

space:
	$(TS) space $(wildcard $(SRC)/modules/*/*.typ $(SRC)/lectures/*.typ $(SRC)/lectures/*/*.typ)

# the viewer's browser tests (tests/browser/ of slide-app, a checkout with
# the [browser] extra), against the course's DECK
live-test:
	cd $(SLIDE_APP_DEV) && SLIDES_COURSE=$(CURDIR) SLIDES_DECK=$(DECK) uv run --extra browser pytest -m browser tests

# The generated option list of the course Makefile, from the `#@option` lines
# above; the include line and what the course sets stay.
update-makefile:
	@$(TS) sync-makefile --file $(firstword $(MAKEFILE_LIST)) $(ARGS)

check-makefile:
	@$(TS) sync-makefile --file $(firstword $(MAKEFILE_LIST)) --check $(ARGS)

# Housekeeping on the course's media (the Typst variants of slide-app's CLI).
SVG ?= $(SRC)/modules $(SRC)/common
unused-media:
	@$(TS) unused-media $(if $(CLEAN),--clean)

optimize-images:
	@$(TS) optimize-images --typst --src $(SRC) $(if $(PRUNE),--prune) $(if $(DRY),--dry) $(ARGS)

compute-svg-bb:
	@$(TS) compute-svg-bb $(wildcard $(SVG)) $(if $(APPLY),--apply)

install-vscode:
	@$(TS) install-vscode --typst --course-dir . $(ARGS)

open-slide:
	@test -n "$(FILE)$(LINE)" || { echo "usage: make open-slide FILE=<file.typ> LINE=<n>"; exit 2; }
	@$(TS) open-slide $(FILE) $(LINE) --dir .

# ------------------------------------------------------------ the course site
# `typst-slides site`: deck list and flags from $(SLIDES_SCHEDULE), the
# outlines the builds write, $(PRACTICAL_MANIFEST) for the practical links.
.PHONY: practical practical-manifest site site-dev site-force site-dev-force site-pdf site-pdf-dev deploy deploy-dev zip serve-course
SITE       := $(TS) site
SITE_FLAGS  = $(if $(PRACTICAL_MANIFEST),--practicals=$(PRACTICAL_MANIFEST)) $(if $(STATIC),--static=$(STATIC))

# The practicals hooks (as in slide-app's MDX makefile, docs/practicals.md): a
# course adds its rule with `::`. practical-manifest is cheap (it runs before
# every site build); practical builds them, before `deploy` only.
practical-manifest::
	@:

practical:: practical-manifest
	@:

site: $(GEN) check-version | practical-manifest
	@$(SITE) build --out=$(DESTDIR) $(SITE_FLAGS)

site-dev: $(GEN) | practical-manifest
	@$(SITE) build --dev --out=$(DESTDIR_DEV) $(SITE_FLAGS)

site-force:
	rm -rf $(DESTDIR)
	@$(MAKE) --no-print-directory site

site-dev-force:
	rm -rf $(DESTDIR_DEV)
	@$(MAKE) --no-print-directory site-dev

# compiled again only when the MD5 of what the last compilation read changed
site-pdf: $(GEN) snapshots
	@$(SITE) pdf --out=$(DESTDIR)/pdf $(if $(FORCE),--force)

site-pdf-dev: $(GEN) snapshots
	@$(SITE) pdf --dev --out=$(DESTDIR_DEV)/pdf $(if $(FORCE),--force)

# `practical` first (it may drop files the site copies), then the site and its
# PDFs in a sub-make, checked for local absolute paths, then rsync --delete.
# DRY=1: rsync -n, nothing is sent.
deploy: practical
	@test -n "$(DEPLOY_DEST)" || { echo "ERROR: DEPLOY_DEST is not set — define it in the course Makefile, e.g.  DEPLOY_DEST := host:/var/www/course/"; exit 1; }
	@$(MAKE) --no-print-directory site $(if $(filter no,$(DEPLOY_PDF)),,site-pdf)
	@$(SITE) check --out=$(DESTDIR)
	rsync --delete -az$(if $(DRY),n)v $(DESTDIR)/ $(DEPLOY_DEST)

deploy-dev: practical
	@test -n "$(DEPLOY_DEST_DEV)" || { echo "ERROR: DEPLOY_DEST_DEV is not set — define it in the course Makefile, e.g.  DEPLOY_DEST_DEV := host:/var/www/course-dev/"; exit 1; }
	@$(MAKE) --no-print-directory site-dev $(if $(filter no,$(DEPLOY_PDF)),,site-pdf-dev)
	@$(SITE) check --out=$(DESTDIR_DEV)
	rsync --delete -az$(if $(DRY),n)v $(DESTDIR_DEV)/ $(DEPLOY_DEST_DEV)

zip: site
	@rm -f $(ZIP_OUT)
	@cd $(dir $(abspath $(DESTDIR))) && zip -rq $(abspath $(ZIP_OUT)) $(notdir $(abspath $(DESTDIR))) -x '*.pdf' '*/.*'
	@echo "Wrote $(ZIP_OUT)"

# The whole course: the index on /, each deck's own dev server (live reload,
# E…) started on its first request under /<id>/ (socket $(OUT)/<id>.sock);
# other files from STATIC, then the dev site (its pdf/), then the site.
serve-course: $(GEN) | practical-manifest
	$(SITE) serve --port=$(COURSE_PORT) --sockets=$(OUT) $(SITE_FLAGS) --static=$(DESTDIR_DEV) --static=$(DESTDIR)

clean:
	rm -rf $(OUT) .cache/widgets .cache/images
