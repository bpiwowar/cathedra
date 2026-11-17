# Upgrading a course

The engine's API changes are numbered: `VERSION` (`src/cathedra/typst/VERSION`) is the current
API version, [`CHANGELOG.md`](CHANGELOG.md) lists what changed in each.
A course records the version its `.typ` files are migrated to in
`.cathedra-version` (a single integer, at the root of the course's typst
directory; a missing file means 1). Commit it.

## Upgrade = four steps

```bash
uvx cathedra@latest --version      # 1. update the engine (or the cathedra submodule:
                                   #    git -C cathedra pull)
make migrate DRY=1                 # 2. what would change: a diff, nothing written
make migrate                       # 3. rewrite the sources, write .cathedra-version
make check                         # 4. every deck compiles; look at the slides, commit
```

(When cathedra is a submodule of the course repository, commit the new
pointer with the migrated files.)

`make migrate` applies every migration between the course's version and the
engine's to each `.typ` file of the course (`modules/`, `lectures/`,
`common/`, …; not `cathedra/`, `out/`, `.cache/`), prints what it changed per
file, then the cases it **skipped**, with `file:line`: patterns it does not
know how to rewrite. They are left as is (deprecated aliases still work) and
are fixed by hand, using the CHANGELOG's *Migration* notes. It is idempotent:
running it again changes nothing.

## From typst-slides / slide-app

The engine was called `typst-slides` (the command, the Python package) and
lived in a course as `slide-app` (a link or a submodule). A course using the
old names keeps working: a `slide-app` link or submodule is used as is (the
decks keep importing `/slide-app/…`), `.slide-app-version` is read (`make
migrate` writes `.cathedra-version` and removes it), the Makefile's
`TYPST_SLIDES` still sets the command, its `# --- slide-app: …` block is
refreshed by `make update-makefile`, templates may keep
`[tool.typst-slides]`, and `--input typst-slides=1` still means `generated`.
To move to the new names: replace `typst-slides` with `cathedra` in the
Makefile; rename the link or the submodule (`git mv slide-app cathedra`) and
`/slide-app/` with `/cathedra/` in the imports and the `include` line.

`make serve`, `html`, `site` and `pdf` print a warning, without failing, while
the course is behind the engine.

## Adding a migration (engine side)

Bump `VERSION`, add a section to the CHANGELOG, and register the functions in
`MIGRATIONS` of `src/cathedra/migrate.py`: `{to_version: [(name, fn)]}` with
`fn(text, path) -> (new_text, count, skipped)`, `skipped` being
`(offset, message)` pairs. `cathedra migrate --check` tells whether a course
is behind (exit status 1).
