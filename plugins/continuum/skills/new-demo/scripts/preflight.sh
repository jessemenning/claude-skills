#!/usr/bin/env bash
# Preflight + runtime pull for a Continuum fast/slow demo. Non-interactive; exit 1 on a hard failure.
# Usage: preflight.sh [--pull] [--repo-dir <dir>]
#   --pull       download/load missing runtimes (SAM image + CLI from the GitHub release, docker pull the rest)
#   --repo-dir   a demo checkout whose .env / Makefile supply SAM_IMAGE, SAM_RELEASE_TAG, SAM_REPO (optional)
set -u
PULL=0; REPO_DIR=""
while [ $# -gt 0 ]; do case "$1" in --pull) PULL=1;; --repo-dir) REPO_DIR="$2"; shift;; esac; shift; done
SAM_VERSION="${SAM_VERSION:-2.409.2}"
SAM_RELEASE_TAG="${SAM_RELEASE_TAG:-2.409.2-5ae9afd958}"
SAM_REPO="${SAM_REPO:-SolaceDev/solace-agent-mesh-go}"
SAM_IMAGE="${SAM_IMAGE:-solace-agent-mesh:${SAM_VERSION}}"
FELDERA_IMAGE="${FELDERA_IMAGE:-ghcr.io/jessemenning/feldera:feat-solace-connector}"
SOLACE_IMAGE="${SOLACE_IMAGE:-solace/solace-pubsub-standard:latest}"
if [ -n "$REPO_DIR" ] && [ -f "$REPO_DIR/Makefile" ]; then
  v=$(grep -E '^SAM_RELEASE_TAG \?=' "$REPO_DIR/Makefile" | sed 's/.*= *//'); [ -n "$v" ] && SAM_RELEASE_TAG="$v"
  v=$(grep -E '^SAM_REPO \?=' "$REPO_DIR/Makefile" | sed 's/.*= *//'); [ -n "$v" ] && SAM_REPO="$v"
  [ -f "$REPO_DIR/.env" ] && { v=$(grep -E '^SAM_IMAGE=' "$REPO_DIR/.env" | cut -d= -f2-); [ -n "$v" ] && SAM_IMAGE="$v"; }
fi
fail=0; ok(){ echo "  PASS $*"; }; bad(){ echo "  FAIL $*"; fail=1; }; note(){ echo "  NOTE $*"; }
arch(){ case "$(uname -m)" in x86_64|amd64) echo amd64;; aarch64|arm64) echo arm64;; *) echo unknown;; esac; }

echo "1. Tooling"
docker info >/dev/null 2>&1 && ok "docker daemon" || bad "docker daemon not reachable"
command -v gh >/dev/null && ok "gh CLI" || bad "gh CLI missing (needed to download the SAM release)"
gh auth status >/dev/null 2>&1 && ok "gh authenticated" || bad "gh not authenticated: run 'gh auth login'"
gh release view "$SAM_RELEASE_TAG" --repo "$SAM_REPO" --json tagName >/dev/null 2>&1 && ok "read access to $SAM_REPO release $SAM_RELEASE_TAG" || bad "no access to $SAM_REPO release $SAM_RELEASE_TAG (ask for read access to the SAM release repo)"
command -v python3 >/dev/null && ok "python3" || bad "python3 missing"
python3 -c 'import paho.mqtt' 2>/dev/null && ok "paho-mqtt" || note "paho-mqtt missing: pip install 'paho-mqtt>=2' (smoke test / ops console)"
command -v rsync >/dev/null && ok "rsync" || note "rsync missing (scaffold falls back to tar)"

echo "2. SAM CLI"
if command -v "sam-${SAM_VERSION}" >/dev/null; then ok "sam-${SAM_VERSION} on PATH ($(sam-${SAM_VERSION} --version 2>/dev/null | head -1))"
elif [ "$PULL" = 1 ]; then
  a=$(arch); tmp=$(mktemp -d)
  if gh release download "$SAM_RELEASE_TAG" --repo "$SAM_REPO" --pattern "*cli-linux-${a}.tar.gz" --dir "$tmp" --clobber >/dev/null 2>&1; then
    mkdir -p "$HOME/.local/bin"; tar -xzf "$tmp"/*cli-linux-${a}.tar.gz -C "$tmp"
    bin=$(find "$tmp" -type f -name 'sam*' ! -name '*.tar.gz' | head -1)
    if [ -n "$bin" ]; then install -m 755 "$bin" "$HOME/.local/bin/sam-${SAM_VERSION}" && ln -sf "$HOME/.local/bin/sam-${SAM_VERSION}" "$HOME/.local/bin/sam" && ok "installed sam-${SAM_VERSION} to ~/.local/bin (ensure it is on PATH)"; else bad "CLI tarball had no sam binary"; fi
  else bad "could not download the SAM CLI from the release"; fi
  rm -rf "${tmp:?}"
else bad "sam-${SAM_VERSION} not on PATH (re-run with --pull to install from the release)"; fi

echo "3. Runtime images"
for img in "$SOLACE_IMAGE" "$FELDERA_IMAGE"; do
  if docker image inspect "$img" >/dev/null 2>&1; then ok "$img present"
  elif [ "$PULL" = 1 ]; then docker pull -q "$img" >/dev/null 2>&1 && ok "pulled $img" || bad "docker pull $img failed"
  else note "$img not present (pulled on first compose up, or run with --pull)"; fi
done
if docker image inspect "$SAM_IMAGE" >/dev/null 2>&1; then ok "SAM image $SAM_IMAGE present"
elif [ "$PULL" = 1 ]; then
  a=$(arch); tmp=$(mktemp -d); echo "  ...downloading SAM runtime image (~800 MB) from release $SAM_RELEASE_TAG"
  if gh release download "$SAM_RELEASE_TAG" --repo "$SAM_REPO" --pattern "*app-${a}.tar.gz" --dir "$tmp" --clobber >/dev/null 2>&1 && docker load -i "$tmp"/*app-${a}.tar.gz >/dev/null 2>&1 && docker image inspect "$SAM_IMAGE" >/dev/null 2>&1; then ok "loaded $SAM_IMAGE"
  else bad "SAM image download/load failed (check 'docker images solace-agent-mesh' and SAM_IMAGE)"; fi
  rm -rf "${tmp:?}"
else bad "SAM image $SAM_IMAGE not present (re-run with --pull)"; fi

echo "4. Ports (host side)"
for p in 8080 8081 8800 8089 1883 8008 55555 9000 8091 8092 8093; do
  if (ss -ltn 2>/dev/null || netstat -ltn 2>/dev/null) | grep -qE "[:.]${p}\b"; then note "port $p in use (another demo stack up? stop it or change the mapping)"; fi
done
[ "$fail" = 0 ] && echo "PREFLIGHT OK" || { echo "PREFLIGHT FAILED"; exit 1; }
