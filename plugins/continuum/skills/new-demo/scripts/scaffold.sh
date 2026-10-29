#!/usr/bin/env bash
# Copy a reference fast/slow demo into a fresh repo for re-domaining.
# Usage: scaffold.sh <reference-dir> <target-dir> <slug> [--drop relative/path ...]
#   Copies everything except .git, .env, caches, vendor dirs and .sf; starts a fresh git repo whose
#   first commit is the untouched copy; removes --drop paths (e.g. a second reference solution with no analog).
set -eu
REF="$1"; TGT="$2"; SLUG="$3"; shift 3
DROPS=(); while [ $# -gt 0 ]; do case "$1" in --drop) DROPS+=("$2"); shift;; esac; shift; done
[ -d "$REF" ] || { echo "reference dir not found: $REF"; exit 1; }
[ -e "$TGT" ] && { echo "target exists: $TGT (refusing to overwrite)"; exit 1; }
mkdir -p "$TGT"
if command -v rsync >/dev/null; then
  rsync -a --exclude .git --exclude .env --exclude node_modules --exclude __pycache__ --exclude .venv --exclude .pytest_cache --exclude target --exclude .sf --exclude '*.pyc' --exclude .DS_Store "$REF/" "$TGT/"
else
  (cd "$REF" && tar --exclude=.git --exclude=.env --exclude=node_modules --exclude=__pycache__ --exclude=.venv --exclude=.pytest_cache --exclude=target --exclude=.sf -cf - .) | (cd "$TGT" && tar -xf -)
fi
for d in "${DROPS[@]}"; do
  case "$d" in /*|""|.|..|*..*) echo "refusing to drop '$d' (must be a relative path inside the target)"; exit 1;; esac
  rm -rf "${TGT:?}/${d:?}" && echo "dropped $d"
done
( cd "$TGT" && git init -q -b main && git add -A >/dev/null && git -c user.name="${GIT_AUTHOR_NAME:-$(git -C "$REF" config user.name || echo scaffold)}" -c user.email="${GIT_AUTHOR_EMAIL:-$(git -C "$REF" config user.email || echo scaffold@local)}" commit -q -m "chore: scaffold ${SLUG} from $(basename "$REF") @ $(git -C "$REF" rev-parse --short HEAD 2>/dev/null || echo untracked)" )
echo "scaffolded $TGT ($(cd "$TGT" && git ls-files | wc -l) files); first commit = untouched reference copy, so 'git diff' shows exactly what re-domaining changed"
