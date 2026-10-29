#!/usr/bin/env python3
"""Find leftover old-domain identifiers in a re-domained tree.

Usage: domain_scan.py <dir> --tokens faa,airport,KEWR,... [--allow path-substring,...] [--top 40]
Case-insensitive; tokens of 4 chars or fewer match on word boundaries, longer tokens as substrings.
Skips .git, caches, lock files, images/SVG, binaries and files > 2 MB.
Exit 1 when any hit remains, so it can be used as a gate.
"""
import argparse, os, re, sys
ap = argparse.ArgumentParser()
ap.add_argument("dir"); ap.add_argument("--tokens", required=True)
ap.add_argument("--allow", default="", help="comma-separated path substrings to ignore (e.g. REDOMAIN-CONTRACT.md)")
ap.add_argument("--top", type=int, default=40)
a = ap.parse_args()
tokens = [t.strip() for t in a.tokens.split(",") if t.strip()]
allow = [s for s in a.allow.split(",") if s]
skip_dirs = {".git", "node_modules", "__pycache__", ".venv", ".pytest_cache", "target", ".sf", "dist", "build"}
skip_files = re.compile(r"(\.lock|lock\.json|\.min\.js|\.svg|\.png|\.jpg|\.pdf)$", re.I)
# short tokens (<= 4 chars) match on word boundaries so "AAR" does not hit inside hashes; longer ones match as substrings
parts = [(r"\b" + re.escape(t) + r"\b") if len(t) <= 4 else re.escape(t) for t in tokens]
rx = re.compile("|".join(parts), re.I)
hits = {}; total = 0
for root, dirs, files in os.walk(a.dir):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for f in files:
        p = os.path.join(root, f); rel = os.path.relpath(p, a.dir)
        if any(s in rel for s in allow) or skip_files.search(f): continue
        try:
            if os.path.getsize(p) > 2_000_000: continue
            data = open(p, "rb").read()
            if b"\0" in data[:4096]: continue
            text = data.decode("utf-8", "replace")
        except OSError: continue
        n = len(rx.findall(text))
        if n: hits[rel] = n; total += n
for rel, n in sorted(hits.items(), key=lambda kv: -kv[1])[: a.top]:
    print(f"{n:6d}  {rel}")
print(f"\n{total} hits in {len(hits)} files for tokens: {', '.join(tokens)}")
sys.exit(1 if total else 0)
