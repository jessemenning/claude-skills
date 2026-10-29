#!/usr/bin/env python3
"""Check scenario/feed environment knobs line up between the Python that reads them and the files
that declare them, and that the Event Portal domain name has one value across the repo.

Failures (exit 1):
  - a variable read WITHOUT an in-code default (environ["X"] / environ.get("X")) that compose and
    .env.example never declare
  - a knob declared in the `scenario:` or `feed:` service environment (docker-compose.yml) that no
    Python under stack/scenario or stack/feed reads — the card-testing bug: compose set
    ATTACK_ATTEMPTS/ATTACK_MERCHANTS while scenario_driver.py read ATTACK_COUNT/ATTACK_CARDS
  - more than one Event Portal domain string
Notes (exit 0): variables read with a default that are not declared anywhere (undocumented knobs).
Usage: env_consistency.py <repo>
"""
import glob, os, re, sys
repo = sys.argv[1]
def read(p): return open(p, errors="replace").read() if os.path.exists(p) else ""
compose = read(os.path.join(repo, "docker-compose.yml")); envex = read(os.path.join(repo, ".env.example"))
declared = set(re.findall(r"^\s*-?\s*([A-Z][A-Z0-9_]+)=", compose + "\n" + envex, re.M)) | set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)", compose))
# per-service environment blocks (scenario, feed)
svc_env = {}
cur = None; in_env = False
for line in compose.splitlines():
    m = re.match(r"^  ([a-z][a-z0-9_-]*):\s*$", line)
    if m: cur = m.group(1); in_env = False; continue
    if cur and re.match(r"^    environment:\s*$", line): in_env = True; continue
    if cur and in_env:
        mm = re.match(r"^      -\s*([A-Z][A-Z0-9_]+)=", line)
        if mm: svc_env.setdefault(cur, set()).add(mm.group(1)); continue
        if not line.startswith("      "): in_env = False
def reads(paths):
    out = {}
    for p in paths:
        txt = read(p)
        for m in re.finditer(r"""environ(?:\.get)?\(\s*["']([A-Z][A-Z0-9_]+)["']\s*(,)?|environ\[\s*["']([A-Z][A-Z0-9_]+)["']\]""", txt):
            name = m.group(1) or m.group(3); has_default = bool(m.group(2))
            out.setdefault(name, [set(), True]); out[name][0].add(os.path.relpath(p, repo)); out[name][1] &= has_default
    return out
all_py = glob.glob(os.path.join(repo, "stack", "**", "*.py"), recursive=True)
used = reads(all_py)
ignore = {"LOG_LEVEL", "PATH", "HOME", "PYTHONUNBUFFERED"}
bad = 0
for name, (files, has_default) in sorted(used.items()):
    if name in ignore or name in declared: continue
    if has_default: print(f"NOTE  {name} read with a default but declared nowhere ({', '.join(sorted(files))})")
    else: print(f"FAIL  {name} read without a default and declared nowhere ({', '.join(sorted(files))})"); bad += 1
for svc in ("scenario", "feed"):
    read_names = set(reads(glob.glob(os.path.join(repo, "stack", svc, "*.py"))))
    for name in sorted(svc_env.get(svc, set())):
        if name not in read_names and not name.startswith(("SOLACE_", "FL_", "LOG_")):
            print(f"FAIL  compose declares {name} for service '{svc}' but nothing under stack/{svc} reads it"); bad += 1
vals = set()
m = re.search(r"CONTINUUM_EP_DOMAIN=\$\{CONTINUUM_EP_DOMAIN:-([^}]+)\}", compose) or re.search(r"CONTINUUM_EP_DOMAIN=([^$\n]+)$", compose, re.M)
if m: vals.add(m.group(1).strip())
m = re.search(r"^CONTINUUM_EP_DOMAIN=(.+)$", envex, re.M)
if m and m.group(1).strip(): vals.add(m.group(1).strip())
m = re.search(r"""ep_domain:\s*str\s*=\s*Field\(\s*["']([^"']+)["']""", read(os.path.join(repo, "continuum-mcp/continuum_mcp/config.py")))
if m: vals.add(m.group(1).strip())
if len(vals) > 1: print("FAIL  Event Portal domain has several values:", sorted(vals)); bad += 1
print("env consistency:", "OK" if not bad else f"{bad} failure(s)")
sys.exit(1 if bad else 0)
