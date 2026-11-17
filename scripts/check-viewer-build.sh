#!/usr/bin/env sh
# Fail the commit when the viewer's sources (viewer/) changed but the packaged
# build (src/cathedra/data/viewer/) was not rebuilt and staged.
#
# The built viewer is committed so that the Python package installs without
# Node. This guard keeps the committed bundle in step with its sources: edit
# viewer/, rebuild, and stage the result in the same commit.
#
# Bypass intentionally with `git commit --no-verify` when a change under
# viewer/ does not affect the build output (e.g. a comment in build.mjs).
set -eu

staged=$(git diff --cached --name-only --diff-filter=ACMRD)

viewer_changed=$(printf '%s\n' "$staged" \
    | grep -E '^viewer/' \
    | grep -vE '^viewer/(node_modules|README\.md)' || true)
data_changed=$(printf '%s\n' "$staged" \
    | grep -E '^src/cathedra/data/viewer(-shims)?/' || true)

if [ -n "$viewer_changed" ] && [ -z "$data_changed" ]; then
    echo "error: the viewer's sources changed but the built viewer was not updated." >&2
    echo >&2
    echo "Changed under viewer/:" >&2
    printf '  %s\n' $viewer_changed >&2
    echo >&2
    echo "Rebuild and stage the packaged bundle:" >&2
    echo "  (cd viewer && pnpm install && pnpm run build) && git add src/cathedra/data" >&2
    echo >&2
    echo "Or bypass if the change does not affect the build: git commit --no-verify" >&2
    exit 1
fi
