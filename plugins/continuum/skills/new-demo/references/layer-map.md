# Layer map — what to change, in dependency order (reference: faa-fast-slow)

Paths are relative to the repo root. **G** = generic, copy as-is (rename identifiers only where
noted). **D** = domain, rewrite from the contract. **S** = stale in the reference (inherited from its
own FX ancestor, never re-domained) — delete or regenerate, never re-domain. Commit after each layer.

## Known defects in the reference — fix them in the generated repo, do not inherit
- README.md and CUSTOMIZE.md call the SAM trigger topic `…/breach/`; the code subscribes `…/incident/` (the collapsed one-per-entity row). The contract's `incident/` wins everywhere.
- `sam/agents/SolutionBuilder.yaml`, `sam/builder/method.md`, `sam/skills/solution-design/*` say generated triggers live under `fl/<domain>/<slug>/`; `continuum-mcp` enforces `fl/cp/<slug>/`. Use `fl/cp/`.
- `sam/scripts/deploy-solution.sh` and `demo/new-solution.sh` pin `sam-2.403.3`; `Makefile`/`.env.example` say 2.409.2. Normalise every pin to the chosen SAM version (verification gate 2).
- CLAUDE.md says "3 specialists"; the workflow has 4 (`arrival_repositioning`). Decide 3 or 4 in the contract and make docs match.
- `stack/api/src/config.py` names a `watch_pipeline` (`arrival-capacity-watch`) nothing creates; `demo/create-product.py` references an `arrival-demand-watch` spec that does not exist. Point both at the contract's product slug or delete.
- `sam/builder/` is a patch for the in-runtime `/builder` that compose never mounts; keep it only if you re-domain `method.md`/`critical_prepend.md`, else drop.
- `.claude/skills/sam-*` are gitignored CLI install artifacts: ignore.
- FX-era strings survive inside generic code and must be cleaned once (the `fx`/`counterparty`/`exposure`/`venue` scan tokens find them): `continuum-mcp/continuum_mcp/service.py` volatile-column comments, `semp_client.py` header, `decision-proxy/app.py` `X-Title: solace-fx-demo`, `decision-proxy/README.md`, `sam/models/investigation.yaml` description, the `/fx/mqtt` WebSocket route in `stack/api/src/routes/mqtt_proxy.py` (rename to `/ws/mqtt` and update every page, or keep with a comment), `index.html` `*-inflight` element ids.
- card-testing was forked before the verified-reset work landed in the reference; always scaffold from the reference's current HEAD and record the hash (scaffold.sh writes it into commit 1).

## Event Portal: removed from generated demos
Delete `ep-mcp-http/`, `demo/register-ep-topology.py`, `demo/register-ep-solution.py`, `sam/skills/solace-event-portal/`, `sam/connectors/event-portal-mcp.yaml`. Remove: the `ep-mcp` service and `CONTINUUM_EP_DOMAIN`/`EP_MCP_*`/`SOLACE_API_TOKEN` from `docker-compose.yml` and `.env.example`; the `register-ep`/`register-ep-solution` targets from the Makefile; the EP step from `demo/new-solution.sh`; the EP connector + skill lines from `sam/manifests/dev.yaml`; `ep_*` tools from `sam/agents/SolutionBuilder.yaml`; `ep_domain` and the registration branch from `continuum-mcp/continuum_mcp/{config,deployer,models}.py` (delete `ep_client.py` and its test); EP links/labels from `continuum-pipeline.html` and the docs; the governance beat's EP mention in the script and deck.

## 0. Repo skeleton
| File | Kind | Change |
|---|---|---|
| `docker-compose.yml` | G | env defaults: `FELDERA_PIPELINE`, `BASE_PIPELINE`, `HERO_*`, scenario knobs; drop the `ep-mcp` service; other service names stay |
| `docker-compose.cache.yml`, `.gitignore`, `.mcp.json` | G | none |
| `Makefile` | G | `PIPELINE`/hero strings in `demo`, `reset`, `pipeline-status`, `fq`, `smoketest`, `verify-solution` help text; SAM version vars |
| `.env.example` | D | rename `HERO_AIRPORT`→`HERO_<ENTITY>` and scenario knobs; keep every platform key |
| `stack/config/init.Dockerfile`, `stack/config/caddy/` | G | none |

## 1. Data plane — `stack/config/feldera/`
| File | Kind | Change |
|---|---|---|
| `init.sh` | G | SQL filename, pipeline name/description in the PUT payload |
| `faa_program.sql` → `<slug_snake>_program.sql` | D | rewrite by section, same numbering. Keep: `solace_input` tables with `topic_pattern` captures + `CONNECTOR_METADATA()` defaults; LOCAL dedups with explicit columns and a 1-day `NOW()` filter inside the ROW_NUMBER subquery; inline VALUES reference set; versioned threshold via `LEAD(valid_from)`; `reset_epoch`; keyed entity with a freshness filter; HOP metric; assessment with temporal join + reset-epoch re-scoring; hysteresis breach; context joins; `<pfx>_incident` (invariant fields, `MAX()` collapse, SEVERE only); `<pfx>_incident_state` over the static set; four sinks (breach + incident `skip_deletes`, incident-state + metric full changelog); `mcp_*` views for each specialist and the UI |
Gotchas: publishers must send raw bytes (a `str` payload makes `PARSE_JSON` return NULL); timestamps UTC `YYYY-MM-DD HH:MM:SS`; MATERIALIZED only on views the API/agents query ad hoc; sinks are plain non-LOCAL views. Validate with `/v0/validate_program` (ir=true) before anything else is built; audit with `/feldera:audit` at the end.

## 2. Broker — `stack/config/solace/setup.sh`
| Kind | Change |
|---|---|
| D (list) / G (helpers) | DMQ name, one `create_queue "<queue>" "<subscription>" <ttl>` per feed + the reset queue, the closing log lines. MQTT/REST enablement stays |

## 3. Feed — `stack/feed/`, `stack/data/`
| File | Kind | Change |
|---|---|---|
| `feed/replay.py` | G | `REFERENCE_PREFIXES` (feeds published once on pass 1: thresholds, reference sets) |
| `feed/Dockerfile`, `requirements.txt` | G | none |
| `data/gen_sample_corpus.py` | D | entity table (ids, display names, descriptors, thresholds, baseline rate kept under threshold), secondary feeds, seeded timeline with `@now`/`@+N` tokens; regenerate `sample-corpus.jsonl` and commit it |
| `data/capture.py` | D | `TOPICS` list, timestamp field names (keep only if the vertical has a real broker to capture from) |
| `data/README.md` | D | record format is generic; feed descriptions are domain |

## 4. Scenario — `stack/scenario/scenario_driver.py`
D. Keep the skeleton (connect-with-backoff, lock with 8 s timeout, `_abort` event, `SCENARIO_AUTOSTART`/`WARMUP`/`HOLD`). Rewrite: control topics, hero entity, `run()` (degrade threshold, publish context, burst with deterministic ids `…1000000+i`, hold), `reset()` (restore threshold/context, evict burst ids two independent ways, set abort). Env knob names per contract, and the SAME names in `docker-compose.yml` and `.env.example` (gate 14a). The eviction in `reset()` must match the SQL's eviction path (contract invariant 6): a far-future timestamp only works through a per-row dedup view; a non-active status only works through a status filter.

## 5. API — `stack/api/src/`
| File | Kind | Change |
|---|---|---|
| `main.py`, `services/feldera_client.py`, `routes/mqtt_proxy.py`, `Dockerfile`, `requirements.txt` | G | router import/prefix only |
| `config.py` | G | `feldera_pipeline`, `watch_pipeline`/product slug defaults |
| `services/solace_receiver.py` | G mech / D topics | `_PREFIX_MAP`, `_SUBSCRIPTIONS`, the `latest` key column |
| `routes/faa.py` → `routes/<domain>.py` | D | prefix `/api/<domain>`; query routes over the contract's views; `_REFERENCE_QUERIES`; `scenario/start|reset` (keep the blocking CLEAR handshake); inject allowlist prefixes; `_MV_VIEWS`; keep SSE + data-product proxy code verbatim |

## 6. UI — `stack/api/static/`
| File | Kind | Change |
|---|---|---|
| `demo.html` | D | keep layout/CSS/MQTT/SSE plumbing; rewrite copy, `PRIMARY`, `FALLBACK_<ENTITIES>`, topic list, gauge semantics (metric vs threshold), storm/incident/triage/brief sections, button labels |
| `continuum-pipeline.html` | D | `NODES` graph = the §-views and sinks; 7 `STAGES` captions in plain language; "+ Data product" presets come from `demo/products/*.json` |
| `slides.html`, `slides-speaker-notes.md` | D | see presentation-template.md |
| `index.html`, `console.html`, `monitor.html`, `thin-client.html`, `continuum.html` | D/secondary | re-domain only if they appear in the script; otherwise delete and drop their links |
| `live-view.html` (demo/) | S | delete |

## 7. SAM — `sam/`
| File | Kind | Change |
|---|---|---|
| `models/general.yaml`, `models/investigation.yaml` | G | none |
| `connectors/continuum-mcp.yaml` | G | none (`event-portal-mcp.yaml` is deleted) |
| `connectors/event-mesh-publish.yaml` | G | the static `solutions/<slug>/triage` topic |
| `manifests/dev.yaml` (platform) | G | remove the Event Portal connector and skill entries |
| `agents/SolutionBuilder.yaml` | D (examples) | worked examples, `fl/cp/` namespace, entity key |
| `skills/solution-design/*` (+ `references/worked-example-*.md`), `skills/continuum-data-product/references/*`, `skills/schema-refs/*` | D (examples) / G (rules) | replace the worked example with the new solution; keep rules; delete `skills/solace-event-portal/` and any EP step in `solution-design` |
| `solutions/arrival-capacity/` → `solutions/<slug>/` | D | per the contract table: gateway (subscription, `forwardContext.<entity_key>`, decision/error topics, `successOutput: custom input.payload:data[0]`), workflow (`detection:` policy, 6 questions, `publish_triage`, 3–4 `when`-gated specialists, `brief`, `output_mapping`), decider model (unchanged shape), specialist agents (one `continuum_preview_query` each over an `mcp_*` view), lead briefer (investigation model, JSON brief sections, advisory rule), A/B alternative, `manifests/dev.yaml` |
| `solutions/wind-arrival-risk/` | D-generated | drop; regenerate the live-build product's solution with `make new-solution` after the stack is up |
| `scripts/apply.sh`, `deploy-solution.sh` | G | SAM version pin |
| `scripts/run-docker.sh`, `run-embedded.sh`, `undeploy-reference.sh`, `README.md`, `.env.template` | S | delete |
Load-bearing details: the `when:` gate value must be quoted (`'"{{triage.output.answers.action.choice}}" == "ESCALATE"'`); `successOutput` must be `custom` + `input.payload:data[0]`; `SAM_FEATURE_WORKFLOW_DECISION_NODE=true` on host and runtime.

## 8. Generation engine — `continuum-mcp/`
| File | Kind | Change |
|---|---|---|
| `continuum_mcp/*.py`, `templates/*.j2`, `Dockerfile`, `pyproject` | G | defaults in `config.py` (`base_pipeline`), docstring examples in `server.py`; remove the EP registration path and `ep_client.py` |
| `catalog/base/<slug>.yaml` | D | the base views exposed as read-only products |
| `catalog/streams/*.yaml` | D | raw streams (topic subscriptions, DDL, decode SQL), derived ingestable streams (snapshot / inserts_only), non-ingestable previews; `key_columns`, `event_time_column`, `volatile_columns` |
| `catalog/products/` | runtime state | leave empty |
| `tests/*`, `tests/golden/*.sql` | D | re-author against the new catalog; `uv run pytest -q` must pass |
| `README.md`, `.env.example` | D | stream names |

## 9. Demo tooling — `demo/`
| File | Kind | Change |
|---|---|---|
| `prewarm.sh`, `continuum-create-product.py`, `continuum-add-trigger.py`, `new-solution.sh`, `check-gateway.py`, `prune-orphan-queues.sh` | G | version pin, key column default; remove the EP step from `new-solution.sh` |
| `burst.sh`, `smoketest.py`, `verify-solution.py`, `ops-console.py`, `create-product.py`, `products/<product>.json` | D | topics, hero, env knob names (`register-ep-*.py` are deleted) |
| `README.md`, `doctor.sh`, `live-view.html` | S | regenerate README from the Makefile help; rewrite doctor.sh from `preflight.sh`; delete live-view |

## 10. Docs and presentation — root
| File | Kind | Change |
|---|---|---|
| `CLAUDE.md`, `README.md`, `BUSINESS.md`, `CUSTOMIZE.md`, `PRESENTATION_SCRIPT.md`, `stack/api/static/slides-speaker-notes.md` | D | rewrite (presentation-template.md); keep the rollout procedure and the audit notes sections |
| `architecture.svg`, `architecture-business.svg`, `diagrams/`, `presentation-graphics.html`, `presentation-lookbook.html` | D | delegate SVG/HTML graphics to a subagent with the contract; brand colours per the Solace brand rule |
| `CEO-VIDEO-SCRIPT.md` | S | regenerate only on request |
| `PACKAGING.md`, `DESIGN-fast-slow-investigation.md`, `EVAL-openai-decision-model.md`, `SHIFT_TO_PREDICTIVE.md` | S | delete |
| `.claude/skills/solace-solution-builder/` | G | none |
| `.claude/skills/faa-generate-solution/` → `<slug>-generate-solution/` | D | envelope table (ingestable streams + key columns), hero, topics |
| `REDOMAIN-CONTRACT.md` | new | the filled contract |

## Order of work and commits
1 contract → 2 scaffold (commit) → 3 data plane + broker + feed + scenario (bring up `solace`+`feldera` only, validate SQL, regenerate corpus; commit) → 4 API + UI (commit) → 5 SAM + continuum-mcp catalog + tests (commit) → 6 demo tooling + products (commit) → 7 docs + presentation + deletions (commit) → 8 full stack up, gates 6–14, fixes (commit per fix).
