#!/usr/bin/env python3
"""Summarise a Feldera dataflow graph.

Input: the JSON from GET /v0/pipelines/<name>/dataflow_graph, from POST /v0/validate_program
with "ir": true (take program_info.dataflow), or from the compiler's --dataflow flag.

Prints (1) an operator census, (2) every topK / window / lag / retain operator with its SQL
source line and upstream chain, and (3) for each view that uses a window function, whether a
LogicalProject precedes LogicalWindow and which columns it keeps.

Reading it: a `topK` whose chain has no `window` upstream is a ROW_NUMBER dedup with unbounded
per-key state. A `window` fed by `now` is a temporal filter. `waterline` / `controlled_key_filter_typed`
are LATENESS late-row filters only. A `*retain*` operator is one the compiler made garbage-collectable.
A view whose rels go TableScan -> Filter -> LogicalWindow with no projection retains every column.

Usage: dataflow_census.py <dataflow.json>
"""
import collections
import json
import sys

d = json.load(open(sys.argv[1]))
if "mir" not in d and "dataflow" in d:  # raw validate_program / program_info payload
    d = d["dataflow"]
mir = d.get("mir", {})
skip = {"inspect", "map", "map_index", "flat_map", "flat_map_index", "constant", "source_multiset"}
ops = collections.Counter(str(n.get("operation")) for n in mir.values())
print("operator census:", {k: v for k, v in sorted(ops.items()) if k not in skip})


def chain(k, depth=4):
    out, cur = [], k
    for _ in range(depth):
        n = mir[cur]
        out.append(f"{cur}:{n['operation']}")
        ins = [i["node"] for i in n.get("inputs", []) if mir[i["node"]]["operation"] != "apply"]
        if not ins:
            break
        cur = ins[0]
    return " <- ".join(out)


print("\nstateful dedup / window operators (topK with no 'window' upstream = unbounded per-key state):")
for k, n in mir.items():
    op = n.get("operation", "")
    if op in ("topK", "window", "lag_custom_order") or "retain" in op:
        lines = sorted({p.get("start_line_number") for p in n.get("positions", []) if p.get("start_line_number")})
        print(f"  src {lines or '-'}: {chain(k)}")

print("\nviews with a window function (is there a projection before LogicalWindow, and what does it keep?):")
for v, plan in d.get("calcite_plan", {}).items():
    rels = plan.get("rels", [])
    wi = [i for i, r in enumerate(rels) if r.get("relOp") == "LogicalWindow"]
    if not wi:
        continue
    before = rels[: wi[0]]
    proj = [r.get("fields") for r in before if r.get("relOp") == "LogicalProject"]
    print(f"  {v}: {[r['relOp'] for r in before]} -> projected={proj[-1] if proj else 'NONE (full row retained)'}")
