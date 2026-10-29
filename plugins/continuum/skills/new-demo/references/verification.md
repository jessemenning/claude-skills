# Verification gates — run in this order; do not report "done" past a failing gate

| # | Gate | Command / check | Pass criterion |
|---|---|---|---|
| 0 | Contract complete | read `REDOMAIN-CONTRACT.md` | every template field filled; incident payload lists only invariant fields; hero numbers land in SEVERE with margin |
| 1 | No old-domain leftovers | `python3 "${CLAUDE_SKILL_DIR}/scripts/domain_scan.py" <repo> --tokens <old tokens> --allow REDOMAIN-CONTRACT.md` | exit 0. Old tokens = every identifier in the reference contract's Identifiers/topics/views/hero rows plus `faa, airport, KEWR, gufi, arrival, AAR, SWIM, flight, wind, NEMS, SCDS, TMI, windshift` (also the FX leftovers: `fx, counterparty, exposure`) |
| 2 | No stale version pins | `grep -rn "sam-2\.[0-9]*\.[0-9]*" <repo> --include=*.sh --include=Makefile --include=*.md` | only the chosen SAM version appears |
| 3 | Brand | `grep -rn "PubSub+" <repo>`; `grep -rni "feldera" <repo>/stack/api/static <repo>/PRESENTATION_SCRIPT.md <repo>/BUSINESS.md` | no "PubSub+"; the engine name appears in no user-facing string (UI, script, business doc) |
| 4 | SQL compiles | with the stack up: `POST /v0/validate_program {"program_code": <substituted sql>, "ir": true}` | `Success`; no `Unused` warnings you did not intend; `dataflow_census.py` from the feldera plugin shows every `topK` behind a `window` and every windowed view projecting before `LogicalWindow` |
| 5 | Secrets | `.env` is gitignored and mode 600; `git diff --cached` has no key/token/password values | the only secrets live in `.env` and the user-level secrets file |
| 6 | Preflight | `bash "${CLAUDE_SKILL_DIR}/scripts/preflight.sh" --pull --repo-dir <repo>` | `PREFLIGHT OK` |
| 7 | Cold start | `cp`-free: `.env` written by `collect_env.py`; `make demo-ready` (or `make up` then `make prewarm`) | SAM healthy, pipeline `Running`, `check-gateway` bound |
| 8 | Baseline is green | `make fq SQL="SELECT <entity_key>, status FROM <pfx>_incident_state"` after ~2 min of replay | every entity CLEAR; no breach messages on `fl/<domain>/<slug>/breach/#` (`make ops`) |
| 9 | Hero path | `make smoketest` | exit 0: incident → triage → decision → brief, reset confirmed CLEAR first |
| 10 | Repeatable | `make reset` then `make demo` again | a second incident fires within ~5 s of the burst |
| 11 | Live-build beat | `make create-product` (or `make new-solution SLUG=… TRIGGER=…`, with its Event Portal step removed) | product pipeline Running as a cache hit after prewarm; its trigger fires on the next hero run |
| 12 | Data-plane audit | `/feldera:audit <repo>` | no HIGH findings |
| 13 | UI | open `demo.html?tv=1` and `continuum-pipeline.html?tv=1`; click a node; fire + reset from the buttons | copy is the vertical's; hero tile, gauges, storm→incident, triage, brief all render; reset button confirms green |
| 14a | Env names agree | `python3 "${CLAUDE_SKILL_DIR}/scripts/env_consistency.py" <repo>` | every env var the stack's Python reads is declared in compose or `.env.example`; every scenario/feed knob compose declares is read |
| 14e | No Event Portal | `grep -rniE "event portal|ep-mcp|ep_mcp|SOLACE_API_TOKEN|register-ep" <repo>` | no hits outside `REDOMAIN-CONTRACT.md` |
| 14b | Schemas agree | compare `continuum-mcp/catalog/streams/*.yaml` columns with the sink views' columns and severity tiers; compare decision-question choice text with the SQL tiers | identical names and tiers |
| 14c | No replace-all collateral | `git diff <scaffold-commit> -- continuum-mcp decision-proxy ep-mcp-http stack/api/src/routes/mqtt_proxy.py` | only intended identifier changes in generic code (card-testing turned "in-flight" into "in-progress" inside engine comments and left `X-Title: solace-fx-demo`) |
| 14d | Clean index | `git status --short` empty; `git log --oneline` shows scaffold + one commit per layer | nothing untracked, nothing staged from the reference by accident |
| 14 | Docs cross-check | README topic table, CUSTOMIZE contract line, CLAUDE.md §-list, PRESENTATION_SCRIPT numbers | all agree with the contract and the SQL (the reference repo itself disagreed on `breach/` vs `incident/`; do not inherit that) |

When a gate cannot be run (no credits on the decisions key, no GPU for a model), say so explicitly in the handover and mark the gate SKIPPED, never PASSED.
