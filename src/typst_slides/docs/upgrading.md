# Upgrading a course

The engine's API changes are numbered: `VERSION` (`src/typst_slides/typst/VERSION`) is the current
API version, [`CHANGELOG.md`](CHANGELOG.md) lists what changed in each.
A course records the version its `.typ` files are migrated to in
`.slide-app-version` (a single integer, at the root of the course's typst
directory; a missing file means 1). Commit it.

## Upgrade = four steps

```bash
uvx typst-slides@latest --version   # 1. update the engine (or the slide-app submodule:
                                   #    git -C slide-app pull)
make migrate DRY=1                 # 2. what would change: a diff, nothing written
make migrate                       # 3. rewrite the sources, write .slide-app-version
make check                         # 4. every deck compiles; look at the slides, commit
```

(When slide-app is a submodule of the course repository, commit the new
pointer with the migrated files.)

`make migrate` applies every migration between the course's version and the
engine's to each `.typ` file of the course (`modules/`, `lectures/`,
`common/`, …; not `slide-app/`, `out/`, `.cache/`), prints what it changed per
file, then the cases it **skipped**, with `file:line`: patterns it does not
know how to rewrite. They are left as is (deprecated aliases still work) and
are fixed by hand, using the CHANGELOG's *Migration* notes. It is idempotent:
running it again changes nothing.

`make serve`, `html`, `site` and `pdf` print a warning, without failing, while
the course is behind the engine.

## Adding a migration (engine side)

Bump `VERSION`, add a section to the CHANGELOG, and register the functions in
`MIGRATIONS` of `src/typst_slides/migrate.py`: `{to_version: [(name, fn)]}` with
`fn(text, path) -> (new_text, count, skipped)`, `skipped` being
`(offset, message)` pairs. `typst-slides migrate --check` tells whether a course
is behind (exit status 1).
