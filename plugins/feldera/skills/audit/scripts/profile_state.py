#!/usr/bin/env python3
"""Rank retained state in a Feldera circuit profile by the operator that owns it.

Download GET /v0/pipelines/<name>/circuit_profile (a zip), unzip it into a directory and pass
that directory. Pass an earlier profile directory as a second argument to see growth per owner.

Trace / integral nodes carry no SQL position; they are nested by indentation under the operator
that owns them, so ownership is the nearest enclosing '<name> @ <src>' header chain. Counts are
summed over all worker files.

Usage: profile_state.py <profile_dir> [<earlier_profile_dir>]
"""
import collections
import glob
import os
import re
import sys

UNITS = {"B": 1, "KiB": 2**10, "MiB": 2**20, "GiB": 2**30}


def rank(d):
    agg = collections.defaultdict(lambda: [0, 0.0])
    for f in glob.glob(os.path.join(d, "*.txt")):
        hdr, lines = [], open(f).read().splitlines()
        for i, l in enumerate(lines):
            ind = len(l) - len(l.lstrip())
            m = re.match(r"\s*(\S.*?) @ \S+$", l.rstrip())
            if m:
                while hdr and hdr[-1][0] >= ind:
                    hdr.pop()
                hdr.append((ind, m.group(1)))
                continue
            r = re.search(r"state_records_count: ([\d,]+)", l)
            if r and hdr:
                k = " > ".join(h[1][:34] for h in hdr)
                agg[k][0] += int(r.group(1).replace(",", ""))
                for j in range(i, min(i + 4, len(lines))):
                    mm = re.search(r"used_memory_bytes: ([\d.]+) (B|KiB|MiB|GiB)", lines[j])
                    if mm:
                        agg[k][1] += float(mm.group(1)) * UNITS[mm.group(2)]
                        break
    return agg


now = rank(sys.argv[1])
old = rank(sys.argv[2]) if len(sys.argv) > 2 else None
print(f"{'records':>10} {'MiB':>7} {'earlier':>10}  owner chain (summed over workers)")
for k, (recs, mem) in sorted(now.items(), key=lambda kv: -kv[1][0])[:12]:
    prev = f"{old[k][0]:,}" if old is not None and k in old else "-"
    print(f"{recs:>10,} {mem/2**20:>7.2f} {prev:>10}  {k[:90]}")
