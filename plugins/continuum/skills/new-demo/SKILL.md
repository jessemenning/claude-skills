---
name: new-demo
description: Turn a business use case (or just a vertical) into a complete, runnable Solace fast/slow demo with the same structure as faa-fast-slow and card-testing-fast-slow — event mesh feeds → Continuum data plane (versioned threshold, rolling metric, breach → one incident per entity) → SAM fast triage (OpenAI Decisions) + slow System-2 brief → presentation UI, live-build data product, speaker notes. Pulls the runtimes, collects credentials, scaffolds from the reference repo, re-domains every layer under a written contract, and verifies end to end with the smoke test. Use when the user says "build a demo for <use case/vertical>", "re-domain the fast/slow demo to <X>", or "new continuum demo".
argument-hint: "<business use case or vertical> [--reference <dir>] [--target <dir>] [--slug <kebab>]"
---

# /continuum:new-demo — a fast/slow demo from a use case

You produce a **new git repo** `<target>` (default `~/<slug>-fast-slow`) that is a complete,
running sibling of `faa-fast-slow`: same layers, same Makefile, same presentation flow, new domain.
The method is **re-domain under a contract**, the way card-testing was made from FAA: copy the
reference, write `REDOMAIN-CONTRACT.md` first, then rewrite each layer from the contract in
dependency order, verifying as you go. Never improvise identifiers; the contract is the only source.

Read these before starting; they are the whole method:
- `${CLAUDE_SKILL_DIR}/references/contract-template.md` — the invariants, the template, a worked FAA↔card-testing mapping, heuristics for a bare vertical
- `${CLAUDE_SKILL_DIR}/references/layer-map.md` — every file, generic vs domain vs stale, in order, with the reference's known defects to fix
- `${CLAUDE_SKILL_DIR}/references/presentation-template.md` — the shape of the script, speaker notes, deck, business doc
- `${CLAUDE_SKILL_DIR}/references/verification.md` — the 14 gates; "done" means gate 14

Budget: a full run is 2–4 hours of agent time plus one ~7 min cold compile. Say so up front.

## Phase 0 — Inputs, runtimes, credentials (do not design yet)

1. **Parse the ask.** `$ARGUMENTS` is the use case or vertical plus optional `--reference`, `--target`,
   `--slug`. Reference default: `~/faa-fast-slow` if present, else `git clone
   git@github.com:jessemenning/faa-fast-slow.git ~/faa-fast-slow` (private; the user needs access).
   Refuse a reference that lacks `stack/config/feldera/*_program.sql` and `sam/solutions/`.
2. **Preflight and pull runtimes** (SAM runtime image + CLI from the GitHub release, Solace and the
   Continuum engine image via docker):
   `bash "${CLAUDE_SKILL_DIR}/scripts/preflight.sh" --pull --repo-dir <reference>`.
   Stop on `PREFLIGHT FAILED` and relay the FAIL lines verbatim; port NOTEs mean another stack is up —
   ask before stopping it (that is someone's running demo).
3. **Credentials.** `python3 "${CLAUDE_SKILL_DIR}/scripts/collect_env.py" <reference> --out /tmp/env-probe
   --reuse <reference>/.env` tells you which required keys exist already (values are never printed).
   For each key reported MISSING, ask the user in one message what it is for and where to get it:
   - `LLM_SERVICE_ENDPOINT` + `LLM_SERVICE_API_KEY` — the OpenAI-compatible endpoint SAM's agents use (LiteLLM proxy or OpenAI); plus the three model-name slots (general = fast, investigation = Sonnet-class)
   - `OPENAI_DECISION_API_KEY` — an OpenRouter key WITH credit; the fast triage is an OpenAI Decisions node routed through the in-stack proxy
   - optional: `SOLACE_API_TOKEN` (Event Portal registration), `SOLACE_*` broker overrides
   Then write the new repo's `.env` in Phase 2 with `--set KEY=VALUE … --save-secrets` so the next
   demo asks nothing. `.env` is gitignored and mode 600; never echo a value, never commit one.
4. **Name it.** Slug = kebab noun phrase of the capability (`arrival-capacity`, `card-testing`,
   `claims-surge`). Target = `~/<slug>-fast-slow`. Refuse to overwrite an existing target.

## Phase 1 — Design the contract (the step that decides everything)

Write `REDOMAIN-CONTRACT.md` from `contract-template.md`. Every section filled, every identifier
final. If the input is only a vertical, apply the template's heuristics and record each choice as an
assumption at the top of the contract. Ask the user at most three questions, and only when the
firehose, the threshold or the hero scenario is genuinely open; otherwise choose and move on.
Do the arithmetic in the contract: baseline per-entity rate vs threshold (must stay green for
every entity), the hero burst vs the SEVERE band (must land SEVERE with margin), HOP size/slide,
freshness window, reset eviction. Show the contract to the user in the chat as a compact summary
(story, entity, metric vs threshold, hero scenario, the six questions, the three specialists) and
continue without waiting; they can redirect you mid-build.

## Phase 2 — Scaffold

```sh
bash "${CLAUDE_SKILL_DIR}/scripts/scaffold.sh" <reference> <target> <slug> \
  --drop sam/solutions/wind-arrival-risk --drop demo/live-view.html --drop sam/scripts/run-docker.sh \
  --drop sam/scripts/run-embedded.sh --drop sam/scripts/undeploy-reference.sh --drop sam/README.md \
  --drop sam/.env.template --drop PACKAGING.md --drop DESIGN-fast-slow-investigation.md \
  --drop EVAL-openai-decision-model.md --drop SHIFT_TO_PREDICTIVE.md --drop CEO-VIDEO-SCRIPT.md
cp REDOMAIN-CONTRACT.md <target>/ && python3 "${CLAUDE_SKILL_DIR}/scripts/collect_env.py" <target> --reuse <reference>/.env [--set …] --save-secrets
```
The scaffold's first commit is the untouched copy, so `git diff <scaffold-commit>` is the complete
re-domain record. Commit after every layer below with conventional messages.

## Phase 3 — Re-domain layer by layer (follow `layer-map.md`; order matters)

1. **Data plane first.** Write `stack/config/feldera/<slug_snake>_program.sql` by section (keep the
   §1–§11 structure and every state-safety rule: LOCAL dedups with explicit columns and the 1-day
   NOW() filter, invariant-only incident fields, incident-state edge, reset-epoch re-scoring). Bring up
   only the broker and the engine (`docker compose -f docker-compose.yml -f docker-compose.cache.yml
   up -d solace feldera`), then compile-check with `POST /v0/validate_program` (`"ir": true`, after the
   `${FL_*}` substitution) and read the IR with the feldera plugin's `dataflow_census.py`. Do not
   proceed with a failing program.
2. **Broker, feed, scenario.** `setup.sh` queues; `gen_sample_corpus.py` + regenerate the corpus;
   `replay.py` reference prefixes; `scenario_driver.py`. Sanity-check the corpus with a 10-line
   python count: no entity's baseline rate crosses the threshold in any window.
3. **API and UI.** Route module, receiver topics, `_MV_VIEWS`; `demo.html`, `continuum-pipeline.html`,
   `slides.html`. Rewrite copy from the contract; keep plumbing verbatim. Delete secondary pages the
   script never opens, and their links.
4. **SAM and the generation engine.** The solution directory per the contract table; platform
   connector topic; builder/skills worked examples; continuum-mcp catalog + golden tests
   (`uv run pytest -q` inside `continuum-mcp/`); the product JSON for the live-build beat.
5. **Demo tooling.** Rewrite `smoketest.py`, `verify-solution.py`, `ops-console.py`, `burst.sh`,
   `register-ep-*.py`; regenerate `demo/README.md`; replace `doctor.sh` with a thin wrapper around
   this skill's `preflight.sh` logic. Normalise every SAM version pin.
6. **Docs and presentation.** `CLAUDE.md` (ground truth, keep the rollout procedure and audit notes),
   `README.md`, `BUSINESS.md`, `CUSTOMIZE.md`, `PRESENTATION_SCRIPT.md`, `slides-speaker-notes.md`;
   SVG diagrams and the graphics/look-book pages via a subagent briefed with the contract.
7. After each layer: `python3 "${CLAUDE_SKILL_DIR}/scripts/domain_scan.py" <target> --tokens <old
   tokens> --allow REDOMAIN-CONTRACT.md` and fix hits in the files you just touched.

Rules that are easy to break: rewrite prose, never sed it; sed only whole-word identifiers in
YAML/py/sql and review the diff of generic code afterwards (a replace-all once rewrote "in-flight" to
"in-progress" inside the engine's comments); the reset's eviction must be proven against the SQL
(contract invariant 6); scenario env names must match compose and `.env.example`;
the SAM trigger subscribes `incident/`, not `breach/`; generated products live under `fl/cp/`;
`when:` gate values quoted; `successOutput` is `custom` + `input.payload:data[0]`; publishers send raw
bytes; UTC timestamps; "Solace Platform", "Continuum", "Agent Mesh" — never the engine's name or
"PubSub+" in anything user-facing; the brief is advisory and never performs the operational action.

## Phase 4 — Bring it up and verify

Run the gates in `verification.md` in order: leftovers, version pins, brand, SQL, secrets, preflight,
`make demo-ready`, baseline green, `make smoketest`, repeatability (`make reset` → `make demo`), the
live-build beat (`make create-product` / `make new-solution`), `/feldera:audit <target>`, the two
`?tv=1` pages, docs cross-check. Fix and re-run until every gate passes or is explicitly SKIPPED with
the reason (no credit on the decisions key, no Event Portal token). Never report a skipped gate as
passed.

## Phase 5 — Hand over

End with: the repo path and the scaffold→final commit range; the three commands (`make demo-ready`,
`make demo`, `make reset`); the two presentation URLs; where the script and speaker notes are; the
contract summary; the gate table with PASS/SKIPPED; what you assumed; and the offer to push to a new
GitHub repo (creating a public repo needs the user's explicit instruction).

## Scripts in this skill
| Script | Purpose |
|---|---|
| `scripts/preflight.sh [--pull] [--repo-dir d]` | tooling, gh access to the SAM release, SAM CLI + image, engine/broker images, port conflicts |
| `scripts/collect_env.py <repo> [--reuse other/.env] [--set K=V] [--save-secrets]` | build `.env` from example + reuse + user-level secrets; lists MISSING required keys; never prints values |
| `scripts/scaffold.sh <ref> <target> <slug> [--drop path…]` | copy, drop stale files, fresh git repo with the untouched copy as commit 1 |
| `scripts/domain_scan.py <dir> --tokens a,b [--allow …]` | leftover-identifier gate |
| `scripts/env_consistency.py <repo>` | env vars read by the stack are declared in compose/.env.example; one Event Portal domain string |
