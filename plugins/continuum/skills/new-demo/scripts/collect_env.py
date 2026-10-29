#!/usr/bin/env python3
"""Build a demo's .env without ever printing secret values.

Sources, lowest to highest precedence:
  1. the repo's .env.example (defaults and the full key list)
  2. --reuse <path>: another demo's filled .env (same key names), e.g. a sibling fast/slow demo
  3. --secrets <path>: a user-level file (default ~/.config/continuum-demo/secrets.env), KEY=VALUE lines
  4. --set KEY=VALUE (repeatable)
Writes --out (default <repo>/.env, mode 600) and reports which REQUIRED keys are still empty, exit 2
if any — the caller then asks the user for exactly those and re-runs with --set.
Usage: collect_env.py <repo-dir> [--reuse other/.env] [--secrets file] [--set K=V ...] [--out path] [--save-secrets]
  --save-secrets  also store the secret keys into the user-level secrets file for next time
"""
import argparse, os, re, sys
REQUIRED = ["LLM_SERVICE_ENDPOINT", "LLM_SERVICE_API_KEY", "OPENAI_DECISION_API_KEY"]
SECRET_RX = re.compile(r"(KEY|TOKEN|PASSWORD|SECRET)", re.I)
ap = argparse.ArgumentParser()
ap.add_argument("repo"); ap.add_argument("--reuse"); ap.add_argument("--secrets", default=os.path.expanduser("~/.config/continuum-demo/secrets.env"))
ap.add_argument("--set", action="append", default=[]); ap.add_argument("--out"); ap.add_argument("--save-secrets", action="store_true")
a = ap.parse_args()
def load(path):
    vals = {}
    if path and os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1); vals[k.strip()] = v.split(" #")[0].strip()
    return vals
example_path = os.path.join(a.repo, ".env.example")
if not os.path.exists(example_path): print("no .env.example in", a.repo); sys.exit(1)
example_lines = open(example_path).read().splitlines()
example = load(example_path)
placeholder = lambda v: v == "" or v.startswith("replace-me") or v.startswith("https://your-")
merged = dict(example)
for src in (load(a.reuse), load(a.secrets)):
    for k, v in src.items():
        if k in merged and v and not placeholder(v): merged[k] = v
for kv in a.set:
    k, v = kv.split("=", 1); merged[k] = v
out = a.out or os.path.join(a.repo, ".env")
with open(out, "w") as f:
    for line in example_lines:
        m = re.match(r"^([A-Z_][A-Z0-9_]*)=(.*)$", line)
        f.write(f"{m.group(1)}={merged.get(m.group(1), m.group(2))}\n" if m else line + "\n")
os.chmod(out, 0o600)
if a.save_secrets:
    os.makedirs(os.path.dirname(a.secrets), exist_ok=True)
    keep = load(a.secrets)
    for k, v in merged.items():
        if SECRET_RX.search(k) and v and not placeholder(v): keep[k] = v
    with open(a.secrets, "w") as f:
        for k, v in sorted(keep.items()): f.write(f"{k}={v}\n")
    os.chmod(a.secrets, 0o600)
missing = [k for k in REQUIRED if placeholder(merged.get(k, ""))]
print(f"wrote {out}")
for k in sorted(merged):
    v = merged[k]; shown = ("<set>" if v and not placeholder(v) else "<EMPTY>") if SECRET_RX.search(k) else (v or "<EMPTY>")
    print(f"  {k}={shown}")
if missing:
    print("\nMISSING required keys:", ", ".join(missing)); sys.exit(2)
print("\nall required keys present")
