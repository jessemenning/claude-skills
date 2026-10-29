---
name: audit
description: Audit a Feldera SQL pipeline/program for efficiency against Feldera's official best practices AND verify state-growth claims by compiling the program with the bundled SQL compiler (--dataflow) instead of reading SQL alone. Covers LOCAL views, bounded dedup state (temporal filters, not LATENESS, bound ROW_NUMBER), payload columns leaking into window state via SELECT *, unused tables, clock_resolution, flat VARIANT, parse-once UDF/JSON patterns, transactions, storage/fault-tolerance. Use when the user asks to audit, review, or optimize a Feldera pipeline, workflow, program, or `*_program.sql` / `config/feldera/*.sql`, asks "is this Feldera pipeline efficient?", or asks what a payload/format change (e.g. XML) will cost.
---

Audit a Feldera SQL program against Feldera's documented best practices, **verify the state-related findings by compiling the program**, and report ranked, actionable findings. Applies to any Continuum/Feldera demo in the family (`config/feldera/` or `stack/config/feldera/`).

## When to use

- "Audit `~/<repo>`" / "review this Feldera pipeline" / "is this efficient?"
- Before shipping changes to a `*_program.sql`.
- Scaffolding a new Continuum/Feldera demo and want it efficient from the start.
- Estimating the cost of larger payloads (XML/FIXM/AIXM, big JSON) or a new UDF.

## Step 1 — locate the inputs

1. **The SQL program** — `find <repo> -path '*feldera*' -name '*.sql'`. Usually `config/feldera/<name>_program.sql` or `stack/config/feldera/`. This is the audit subject; read it in full (it IS the thing being audited — don't delegate-skim it).
2. **Runtime config + SET statements** — `init.sh` (the `runtime_config` JSON in the PUT payload, often `{"workers":N}`) and any `SET feldera_* = ...` lines at the top of the `.sql`. These carry `clock_resolution`, `storage`, `fault_tolerance`, `transaction_mode`, `feldera_flat_variant`.
3. **Volume model** — does `docker-compose.yml` give Feldera a persistent volume? Most Continuum demos deliberately run Feldera with **no volume** (a `docker compose down` resets the engine; reference data lives elsewhere). If so, storage-sizing and fault-tolerance checks are **N/A** — say so, don't flag them.
4. **Is the stack running?** `docker ps | grep feldera`. If yes, Step 3 gives real rates and memory; if not, say the numbers are estimates.

## Step 2 — run the checklist

Grep-assisted detection + a read of every `CREATE ... VIEW`. For each view note: modifier (`LOCAL` / plain / `MATERIALIZED`), who consumes it, and whether it's an actual output (has a `'connectors'` sink, or is queried ad-hoc e.g. by an MCP layer).

| # | Check | How to detect | Severity if violated | Fix |
|---|-------|---------------|----------------------|-----|
| 1a | **Dedup / latest-per-key state is bounded** (`ROW_NUMBER() OVER (PARTITION BY k ORDER BY ts DESC) ... rn = 1`) | The subquery has **no temporal filter** (`WHERE ts >= NOW() - INTERVAL ...`) on the ordering column. `LATENESS` does **not** count — see Step 3; verified 2026-10-29 on `ghcr.io/jessemenning/feldera:feat-solace-connector` (upstream main as of 2026-10-26, commit 2057281bc) — re-verify with Step 3.3 on a newer compiler: with LATENESS (nullable, NOT NULL, or `append_only`) the compiler still emits a plain `topK` operator that keeps every row ever seen per key. | **HIGH** — unbounded per-key history; grows with rows/hour × row bytes forever | Add `AND ts >= NOW() - INTERVAL <W>` **inside the ROW_NUMBER subquery** (the docs' soft-delete pattern: temporal filter → ROW_NUMBER). It compiles to a `window` op in front of the TopK and old rows are discarded. Choose `W` ≥ the longest a row can legitimately stay current *relative to downstream logic* — e.g. if a later view keeps a flight while `GREATEST(plan_ts, eta_ts)` is fresh, the plan-side window must cover a stale plan with fresh ETAs (use days, not minutes). |
| 1b | **LATENESS on event-time columns feeding windows/aggregates/joins** | `grep -i LATENESS` → none, while program has `HOP`/`TUMBLE`, time-keyed `GROUP BY`, or joins on event time | **HIGH** for those operators — state kept forever | Add `LATENESS` so waterlines let those operators GC. Note it also **drops late rows** (semantic change; a queue backlog replayed after restart is discarded) — don't add it "for GC" on views where check 1a is the real mechanism. |
| 1c | **Payload columns leak into window state** | A subquery feeding `ROW_NUMBER`/`LEAD`/`LAG`/`OVER` uses `SELECT *` or carries the raw payload column (`data`, `payload`, a VARCHAR/VARBINARY blob). Confirm in the Calcite plan (Step 3): no `LogicalProject` between the scan and `LogicalWindow`, or one that still lists the blob. | **HIGH** with large payloads (XML, batched JSON); **MED** otherwise — the whole row sits in TopK state; growth = rows/hour × full row bytes | List columns explicitly (Calcite then projects before the window; explicit lists in sibling views already do this). Parse/`CAST` what you need in that projection; never carry the blob past the first projection unless a sink needs it. Mandatory before any large-payload/XML change. |
| 1d | **Unused tables / columns** | Compiler warnings `Unused: Table 'x' is not used` / `Unused column` (Step 3), or `grep "FROM <table>"` finds no consumer | **LOW** today (connector CPU only; unused tables hold no state); **MED** once payloads are heavy (parse work for nothing) | Wire it into a view or drop the connector. |
| 2 | **Intermediate views `LOCAL`** | Every `CREATE VIEW` / `CREATE MATERIALIZED VIEW` that is *not* a sink and *not* queried ad-hoc. Trace consumers. | **HIGH** — each non-LOCAL view buffers a change stream + indexes; each MATERIALIZED keeps a full extra copy | Declare `LOCAL` unless the view is a pipeline output. Keep `MATERIALIZED` only for sinks and ad-hoc/MCP-queried views. Watch for a base view AND a near-identical passthrough both MATERIALIZED = double storage. |
| 3 | **`clock_resolution` set when `NOW()` used** | `grep -i 'NOW()'` present AND no `clock_resolution` in runtime_config (default = 1s) | **MED–HIGH** — every tick re-evaluates NOW()-dependent logic | Set `clock_resolution` to the coarsest interval the logic tolerates (e.g. `"1m"` for minute-scale bins). Helps even when NOW() is only in temporal filters. |
| 4 | **`NOW()` inside temporal filters only** | Read each `NOW()` site | **HIGH** if outside a filter (projection/aggregate/join/CASE) — recomputes all dependents every tick; compiler warns | Keep `NOW()` in `WHERE ts > NOW() - INTERVAL ...` form (cheap + enables GC). Move it out of SELECT/CASE. |
| 5 | **Flat VARIANT for JSON** | Flat `VARIANT` is the **default** on builds from 2026-10 onward (grammar.md: `FELDERA_FLAT_VARIANT` only documents `OFF` to revert; the old representation is slated for removal). Flag only a program that sets `SET FELDERA_FLAT_VARIANT = OFF;` without a checkpoint-compat reason. On older builds (pre-default) check for the absence of `SET feldera_flat_variant = 'on';`. | **MED** only when explicitly OFF | Remove the `OFF` setting (expensive: triggers a full backfill, so do it at a restart). |
| 6 | **Parse once per row (JSON, XML, any UDF)** | Same `PARSE_JSON(<col>)` or parsing UDF repeated N× in one view to pull N fields; or a VARIANT-producing view declared MATERIALIZED | **MED** — re-parses the whole blob per field, per row; a materialized VARIANT tree is several × the blob size | Parse once into a VARIANT column in an inner query/CTE (`PARSE_JSON(data) AS v` / `xml_to_variant(data) AS v`), extract `v['field']` and `CAST` **in that same LOCAL view**, and never materialize the VARIANT view. For fan-out (one message → N rows) use `UNNEST(CAST(v[...] AS VARIANT ARRAY))` once. |
| 7 | **Transactions for backfill** | Delta/Iceberg connector present (`grep -i 'delta\|iceberg'`) AND `transaction_mode` unset/`none` | **MED** for batch backfill; **N/A** for pure streaming | Set `transaction_mode='catchup'` (good for backfill + steady state). Pure Solace/event streaming → `none` is correct; note it's correct, not a gap. |
| 8 | **Storage sized 2–4×** | `storage`/`storage_max` in runtime_config | **MED** on a persistent-volume deployment; **N/A** with no volume | Start `storage_max` at 2–4× input size, fast `storage_class` for backfills. |
| 9 | **Fault tolerance** | `fault_tolerance` model in runtime_config | **LOW–MED** on persistent deployment; **N/A** with no volume | Enable storage + `at_least_once`/`exactly_once` if restarts must not reprocess from zero. |
| 10 | **Cross-view optimization / layering** | Is SQL organized into intermediate views (ingest → derive → aggregate → output)? | **LOW** — positive check | Confirm good layering; flag only redundant duplicate views. |

## Step 3 — verify with the compiler, not by reading

Reading SQL predicts; the compiler decides. Every state finding (1a–1d, 2) must be backed by the compiled plan. Everything below works offline against the running Feldera container's bundled compiler and takes ~10 s per compile.

### 3.1 Compile the program and dump the dataflow

**Fastest path — ask the manager, no container exec.** For any pipeline that has compiled (running or not), `GET /v0/pipelines/<name>/dataflow_graph` returns the same JSON as the compiler's `--dataflow` output (`calcite_plan` + `mir`). For SQL that is not deployed yet, `POST /v0/validate_program` with `{"program_code": "...", "ir": true}` (or `fda validate-program file.sql --ir`) compiles it and returns the IR without creating a pipeline; it needs the same `${VAR}` substitution as below because connector JSON is validated. Use the in-container jar only for offline A/B variants (3.3) or for `--plan` / `--png`.

```sh
curl -s http://localhost:<port>/v0/pipelines/<name>/dataflow_graph > "$HOME/feldera-df.json"
```

**Offline path (jar).** The jar lives in the Feldera container at `/home/ubuntu/feldera/build/sql2dbsp-jar-with-dependencies.jar`. Programs in this family contain `${VAR}` tokens that `init.sh` substitutes; the compiler rejects them, so substitute first (ports must become numbers). Stream the SQL in over stdin and copy results out with `docker exec cat` — host `/tmp` is not reliably visible to `docker cp` from the agent sandbox; keep host copies under `$HOME`. When writing a shell heredoc that itself contains a `<<'EOF'` block, use a different outer delimiter.

```sh
C=<feldera-container>; J=/home/ubuntu/feldera/build/sql2dbsp-jar-with-dependencies.jar
python3 "${CLAUDE_SKILL_DIR}/scripts/substitute_vars.py" <repo>/config/feldera/<name>_program.sql \
  | docker exec -i $C sh -c 'cat > /tmp/p.sql'
docker exec $C sh -c "cd /tmp && java -jar $J -i /tmp/p.sql -o /tmp/out.rs --dataflow /tmp/df.json 2>&1 \
  | grep -v 'Unknown format' | grep -i -A4 'warning\|error' | head -60"
docker exec $C cat /tmp/df.json > "$HOME/feldera-df.json"
```

Warnings worth keeping: `Unused: Table ...`, `Unused column ...` (check 1d), `unknown field ...` (a connector/format option the compiler can't validate — usually fork-only options, harmless). `Unknown format: "transport.name" "solace_input"` is expected on the Solace fork.

### 3.2 Read the dataflow JSON

The bundled `scripts/dataflow_census.py` prints the operator census, each dedup/window operator with its source line and upstream chain, and the projection check per windowed view. `df.json` has `calcite_plan` (per view: `rels[]` with `relOp`, `fields`, `window#0`), `mir` (operator id → `{operation, inputs, positions}`), `sources`.

```sh
python3 "${CLAUDE_SKILL_DIR}/scripts/dataflow_census.py" "$HOME/feldera-df.json"
```

How to read it:
- `topK` with its source line = a `ROW_NUMBER` dedup whose state is unbounded **unless** a `window` op (temporal filter) sits upstream of it in the same view. `waterline` + `controlled_key_filter_typed` + `transaction_delay_with_initial_value` per table = LATENESS late-row filters only; they do not shrink `topK`. `accumulate_integrate_trace_retain_*` = an operator the compiler made garbage-collectable.
- In `calcite_plan`, the sequence `LogicalTableScan → LogicalFilter → LogicalWindow` with no `LogicalProject` in between means the full row (every table column, including the payload blob) is the window's state. `... → LogicalProject [cols] → LogicalWindow` with the blob absent is the good shape.
- **Do not rely on "Unbounded state" warnings.** The `FindUnboundedState` pass printed nothing on that same build even for a deliberate unbounded self-join; absence of a warning proves nothing.

### 3.3 A/B-compile the fix before recommending it

Apply the candidate change to the substituted copy (python `str.replace` on the exact subquery text, assert it matched), recompile to a second `df.json`, and diff: the `topK` for that view should now have a `window` input, and the view's `LogicalProject` should precede `LogicalWindow` without the blob. Cite both plans in the report. The same loop answers "does annotation X bound construct Y?" — write a 2-line program (table + the construct, with and without X) and compare the operator census; it is faster and more honest than guessing from docs.

### 3.4 Runtime evidence when the stack is up

- `GET /v0/pipelines/<name>/stats` → `global_metrics.rss_bytes`, `cpu_msecs / uptime_msecs` (= average cores), `total_input_records/bytes`; `inputs[].metrics.total_records/total_bytes` per connector → real msg/s and bytes/record (subtract the `now` pseudo-input). Sample RSS twice ≥ 10 min apart to see slope. `docker stats --no-stream` for container CPU.
- Expected growth for an unbounded dedup: **rows/hour × bytes per retained row** (all columns kept + ~100 B trace overhead). State it per hour / day / week, and again with the proposed payload size — that is what makes a check-1c finding concrete.
- Per-record CPU model for parsers/UDFs: **msg/s × µs per message = fraction of one core**. Measured 2026-10-29 with roxmltree 0.21 (release): ~27 µs parse / ~90 µs parse+tree per 8.5 KB FIXM flight, ~100 MB/s; a 200 KB batch ≈ 2 ms. At demo rates (≤ 50 msg/s) parsing is < 1% of a core — payload **retention** and per-column re-parsing (check 6) are what hurt, not parsing itself. Microbenchmark in a scratch `cargo` project when a new format/UDF is proposed; don't estimate from memory.

### 3.5 Runtime profile — the EXPLAIN ANALYZE equivalent

Feldera SQL has no `EXPLAIN` (the keyword is reserved, not implemented; ad-hoc `EXPLAIN` is DataFusion's plan over materialized views, not the incremental program). The runtime answer is `GET /v0/pipelines/<name>/circuit_profile` on a running or paused pipeline: a zip with one `<worker>.txt` and `<worker>.dot` per worker plus a `Makefile` (`make FORMATS=svg`, needs graphviz). Per node it reports `runtime_seconds` / `runtime_percent` / `invocations_count`, `state_records_count`, `used_memory_bytes` / `allocated_memory_bytes`, `spine_storage_size_bytes`, and a `persistent_id` that matches the `mir` node in the dataflow graph. The Web Console renders the same bundle (pipeline page → **View profile**): click a node to jump to its SQL, rank **Top nodes** by a metric, and read **Issues & Suggestions** triage results. `/heap_profile` exists too.

Reading the text dump: trace/integral nodes carry no SQL position; they are nested (by indentation) under the operator that owns them, so rank state by walking up to the nearest `<name> @ <src>` header. Take two profiles ≥ 10 min apart and diff `state_records_count` per owner to see growth, which is far more precise than RSS.

```sh
curl -s http://localhost:<port>/v0/pipelines/<name>/circuit_profile -o "$HOME/prof.zip" && unzip -qo "$HOME/prof.zip" -d "$HOME/prof"
python3 "${CLAUDE_SKILL_DIR}/scripts/profile_state.py" "$HOME/prof"                      # rank retained state by owner
python3 "${CLAUDE_SKILL_DIR}/scripts/profile_state.py" "$HOME/prof" "$HOME/prof-earlier"   # growth since an earlier snapshot
```

Example (faa-fast-slow, 2026-10-29): `topk_row_number_1 > shard_accumulate_integrate_trace` held 33,602 records / 8.3 MiB across 4 workers; the next owner held 819. That is the four `ROW_NUMBER` dedup views, exactly as the plan predicted.

## Step 4 — report

Lead with a one-line verdict, then a **findings table ranked by severity** (HIGH first), each with: the finding, the specific view/line, why it costs, the plan evidence (operator name / plan shape from Step 3, and profile `state_records_count` when the stack is up), and the concrete fix. Put correctly-configured items in a short "Checked, no change needed" list (don't pad the findings with non-issues). End by offering to apply the fixes.

For a no-volume demo, state up front that checks 8–9 (and often 7) are N/A by design, so the real levers are 1–6 (SQL-side). If the stack was not running, label every number an estimate.

## Sources (cite these)

- [Feldera Best Practices](https://docs.feldera.com/operations/best_practices/) — LOCAL, storage 2–4×, transactions, flat VARIANT, clock_resolution, fault tolerance
- [Streaming SQL extensions](https://docs.feldera.com/sql/streaming) — "Soft deletes with temporal filters" (temporal filter → ROW_NUMBER, the bounded dedup pattern), `append_only`, unbounded-state warnings
- [Time series guide](https://docs.feldera.com/tutorials/time-series) — "How Feldera garbage collects old state", "NOW() and temporal filters → Garbage collection" (discards rows older than the bound, no waterline needed), lateness guidelines
- [Feldera Overview / IVM](https://www.feldera.com/overview) — work ∝ change size
- [Medallion architecture](https://docs.feldera.com/use_cases/medallion_architecture/part1/) — cross-view optimization, layering
- Compiler internals (in any Feldera checkout): `sql-to-dbsp-compiler/SQL-compiler/src/main/java/org/dbsp/sqlCompiler/compiler/visitors/outer/FindUnboundedState.java` (what counts as "streaming" and bounded; `DBSPIndexedTopKOperator` is only bounded when its key domain is), compiler flags `--dataflow`, `--plan`, `--png`.
