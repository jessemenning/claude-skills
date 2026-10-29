# Re-domain contract — template

Fill this in completely BEFORE touching any file. Save it as `REDOMAIN-CONTRACT.md` at the root of
the new repo; every identifier in every layer must match it exactly. Delete it before the repo is
shared externally, or keep it as `docs/DOMAIN.md` once the demo is stable. Two filled examples follow
the template (aviation arrival capacity, payments card testing) — study the mapping between them, it
shows what is invariant and what is domain.

## The fast/slow invariants (do not bend these)

1. **One keyed entity** is judged (airport, device, counterparty, store, patient, turbine...). Every
   topic ends in `{entity_key}`; every view that matters is keyed by it.
2. **A rolling metric vs a versioned threshold.** A HOP window over the firehose produces a metric
   per entity (demand, velocity, exposure); a slow side-input stream carries the threshold in effect
   (published rate, risk policy, credit limit) with `valid_from`/`valid_to` derived by `LEAD()`, so
   dropping a new threshold event re-scores every affected window. That is the "versioned side input".
3. **Breach with hysteresis and severity tiers** (material margin AND sustained-or-clearly-over),
   so one noisy window never fires the AI.
4. **The alert storm collapses to one incident per entity** carrying only fields that stay
   INVARIANT for the life of the incident (identity, descriptors, the threshold in effect, severity).
   Never a per-row id or a climbing count — each distinct value re-fires the trigger. The SAM trigger
   subscribes the `incident/` topic, never the per-window `breach/` topic.
5. **An observable recovery edge**: an `*_incident_state` view keyed on the static reference set,
   `status` SEVERE↔CLEAR, sunk WITHOUT skip_deletes, so reset can be confirmed, not guessed.
6. **A hero scenario that reliably crosses the thresholds within ~90 s, and a reset that reliably
   clears**: baseline synthetic data stays under the threshold for every entity; the scenario (a)
   degrades the threshold and/or (b) bursts the firehose for ONE hero entity; reset restores the
   threshold, evicts the burst entities two independent ways, and publishes a reset marker that the
   data plane uses to re-score windows frozen against the degraded threshold (reset-epoch re-scoring).
   **Prove the eviction in SQL before trusting it:** a re-published row only evicts the original if a
   dedup per row id (`ROW_NUMBER` per `gufi`/`auth_id`) lets the newest version supersede it, or a
   status filter drops it. Card-testing's reset re-published auth rows into a view with no per-row
   dedup, so the originals stayed in the window and recovery waited on the 3-minute freshness filter.
   The contract must name the eviction path and the view that implements it.
7. **Fast then slow**: a typed decision node (OpenAI Decisions via the in-stack proxy) answers the
   same six questions — `will_materialize`, `self_resolves`, `impact`, one domain boolean
   (`is_<something>`), `action` ∈ {ESCALATE, GROUP, SUPPRESS}, `case_priority` — then 3 parallel
   specialist agents (each exactly one `continuum_preview_query` over an `mcp_*` view) and one lead
   briefer (stronger model) run only when `action == "ESCALATE"`. The brief is ADVISORY: options,
   tradeoffs, provenance; it never issues the operational action itself.
8. **Three ways to consume** every data product: events (sinks), MCP (`mcp_*` views the specialists
   query), SQL (ad-hoc). The UI reads only the `mcp_*` and sink views the API exposes.
9. **Name invariant payload fields so the volatility guard keeps them.** `continuum-mcp`'s
   `is_volatile_column()` strips any trigger payload column whose name contains tokens like `rate`,
   `count`, `demand`, `overage`, `window`, `bin_` (read the function; the list evolves). A stable
   descriptor named `policy_min_decline_rate` or `published_rate` gets stripped silently. Use names
   like `threshold_limit`, `policy_floor`, `capacity_published`.
10. **Every view's name and comment must be true.** A `*_context` view that joins nothing is not
   "enriched"; a severity tier referenced in a decision question's choice text must exist in the SQL.
11. **The generation-engine beat**: one additive data product (a SELECT composing two existing
   ingestable streams) with a trigger under `fl/cp/<slug>/<trigger>/{entity_key}`, that can be built
   live on stage as a cache hit. It never touches the base pipeline.

## Template

```markdown
# Re-domain contract — <Demo name> Fast/Slow

## Story (3–5 sentences)
Who the operator is, what firehose arrives, what threshold it is judged against, what the hero
scenario is, what the AI decides, what the human does with the brief. Name the vertical's real
systems (the analog of SWIM/NEMS or the card network) so the deck can say "you already run this".

## Identifiers
| | Value |
|---|---|
| Slug (repo, pipeline, SAM solution, product namespace) | `<slug>` (kebab) |
| Python/SQL identifier prefix | `<pfx>` (snake, e.g. `ct`) |
| Entity key column + topic token | `<entity_key>` / `{<entity_key>}` |
| Hero entity id | `<HERO>` |
| Static reference set (8–12 entities with display names + 1–2 descriptors) | ... |
| Event Portal application domain | "<Vertical> <Capability>" |
| API prefix | `/api/<domain>` |

## Solace topics
| Purpose | Topic |
|---|---|
| Firehose (feed + scenario publish) | `<sys>/<object>/<verb>/{...}/{<entity_key>}` |
| Secondary feeds (0–3: identity/plan, ETA-like, context) | ... |
| Versioned threshold side input | `<sys>/<policy>/{scope}` |
| Context side inputs (weather-like, restriction-like; 0–2) | ... |
| Per-window breach (UI storm) | `fl/<domain>/<slug>/breach/{<entity_key>}` |
| One-per-incident (SAM trigger) | `fl/<domain>/<slug>/incident/{<entity_key>}` |
| Incident state edge (UI + verified reset) | `fl/<domain>/<slug>/incident-state/{<entity_key>}` |
| Per-window metric (UI gauges) | `fl/<domain>/<slug>/<metric>/{<entity_key>}` |
| Scenario fire / reset | `<domain>/scenario/<fire>` / `<domain>/scenario/reset` |
| SAM decision / interim triage | `solutions/<slug>/decision/{<entity_key>}` / `solutions/<slug>/triage` |
| Generated products | `fl/cp/<product-slug>/<trigger>/{<entity_key>}` (fixed by continuum-mcp) |

## Broker queues (setup.sh)
`dlq-fl-<domain>` (DMQ) · one `fl-<feed>` queue per feed with its subscription · `fl-<domain>-reset` ← reset topic.

## Payloads (JSON, raw bytes; timestamps UTC 'YYYY-MM-DD HH:MM:SS')
Firehose: `{ ...fields..., ts }` — list every field and which ones come from topic levels instead.
Threshold: `{ <policy_id>, scope, <limits...>, effective_time }` — default values published once at feed start.
Context feeds: ...

## Feldera pipeline `<slug>`, program `<slug_snake>_program.sql`
Keep the section numbering: §1 ingest tables · §2 LOCAL dedups (explicit columns, 1-day NOW() bound) ·
§3 static reference VALUES · §4 versioned threshold (LEAD) + `reset_epoch` · §5 keyed entity ·
§6 HOP metric (size/slide) · §7 assessment vs threshold-in-effect + reset-epoch re-scoring ·
§8 breach hysteresis + severity · §9 context joins, `<pfx>_incident`, `<pfx>_incident_state` ·
§10 sinks (breach/incident skip_deletes; incident-state/metric full changelog) · §11 `mcp_*` views.
View names: ...
**Incident payload (INVARIANT fields only):** `{ <entity_key>, severity:"SEVERE", <threshold id + limits>, <stable descriptors> }`
**Severity bands:** SEVERE when ... ; <MID> when ... ; material floor ...
**HOP:** size <N> min, slide <M> min. **Freshness filter on the keyed entity:** <X> min.

## Synthetic data (baseline green, hero SEVERE)
- Baseline: <count> entities, per-entity rates kept at <fraction> of the threshold.
- Hero scenario: <what degrades>, <what bursts>, numbers that land in SEVERE with margin.
- Reset: restore threshold, evict burst rows two ways (far-future time AND a non-active status),
  publish the reset marker, abort an in-progress hold.

## SAM solution `sam/solutions/<slug>/`
| reference (arrival-capacity) | new |
|---|---|
| entrypoints/arrival_capacity_gateway.yaml | entrypoints/<pfx>_gateway.yaml (subscribe `fl/<domain>/<slug>/incident/>`, forwardContext `<entity_key>`) |
| workflows/ArrivalCapacityWorkflow.yaml | workflows/<Pascal>Workflow.yaml |
| models/arrival_decider.yaml | models/<pfx>_decider.yaml |
| agents/arrival_weather_context.yaml | agents/<pfx>_<specialist_1>.yaml (queries mcp_...) |
| agents/arrival_downstream_impact.yaml | agents/<pfx>_<specialist_2>.yaml |
| agents/arrival_capacity_trend.yaml | agents/<pfx>_<specialist_3>.yaml |
| agents/arrival_repositioning.yaml | optional 4th specialist, or drop |
| agents/arrival_lead_briefer.yaml | agents/<pfx>_lead_<briefer>.yaml (investigation model) |
| agents/arrival_triage_decider.yaml + alternatives/ | <pfx> equivalents (A/B only) |
**Decision questions:** will_materialize · self_resolves · impact · is_<domain_boolean> · action · case_priority, with
the `detection:` policy text that defines the field semantics.
**Brief sections:** headline / what's happening / why it is <X> and not <benign alternative> / recommended
action (advisory) / <entities> at risk / provenance.

## API `stack/api/src/routes/<domain>.py`, prefix `/api/<domain>`
<metric> · <threshold> · breaches · reference/{...} · latest/{stream} · agent-state · scenario/start ·
scenario/reset (blocks on incident-state CLEAR) · inject/* · stream/{...} (SSE) · data-product/*.
`_MV_VIEWS` = the views the UI flashes on change. `solace_receiver.py` subscribes the 5 live topics.

## UI `stack/api/static/`
`demo.html` 4 columns: firehose → per-entity gauges vs threshold → storm→one-incident collapse (hero
metric = <metric> vs <threshold>) → FAST TRIAGE verdict + System-2 brief sections. `continuum-pipeline.html`:
node map = the §-views; 7 stage captions in plain language. `slides.html`: reuse the deck shell; re-skin
the 8 bodies to this story. Scenario button label: "<Fire label>".

## Generation-engine product (the live build beat)
`demo/products/<product-slug>.json`: name, plain-language description, ONE SELECT composing
<stream A> + <stream B>, source_streams, key_columns, event_time_column, trigger condition,
`output_topic_template: fl/cp/<product-slug>/<trigger>/{<entity_key>}`.

## Scenario control
`scenario_driver.py` subscribes `<domain>/scenario/<fire>` + `<domain>/scenario/reset`;
env knobs: HERO_<ENTITY>, NORMAL_<THRESHOLD>, DEGRADED_<THRESHOLD>, SCENARIO_BURST, SCENARIO_HOLD, SCENARIO_AUTOSTART.
```

## Worked mapping: arrival capacity (reference) ↔ card testing

| Slot | faa-fast-slow | card-testing-fast-slow |
|---|---|---|
| Entity key | `airport` (ICAO) | `device_id` (fingerprint) |
| Hero | `KEWR` | `dev-BOTNET-01` |
| Firehose | FDPS positions + flight plans, TTP ETAs (`FDPS/…`, `TTP/flightData/…`) | card auth attempts `fraud/auth/attempt/{auth_id}/{device_id}/{result}` |
| Versioned threshold | published AAR `TTP/airportInfo/{airport}` (`aar, adr, runway_config, effective_time`) | risk policy `fraud/policy/risk/{scope}` (`max_attempts, min_distinct_cards, min_decline_rate, effective_time`) |
| Context side inputs | METAR weather, TMR restrictions | (none; merchants static) |
| Rolling metric | arrivals due in next 60 min (HOP 60/15) vs AAR | attempts / distinct cards / decline rate in 90 s window vs policy |
| Breach | `overage = demand - aar`, SEVERE ≥ 25% over | `attempt_over`, SEVERE ≥ 40 attempts |
| Incident invariant fields | airport, airport_name, tracon, bin_capacity, runway_config, severity, restriction | device_id, severity, policy_id, policy limits |
| Hero scenario | wind shift: AAR 44→26 + GDP + burst of 24 arrivals | botnet burst: 60 auths / 40 cards / 15 merchants / 85% declined in 90 s |
| Reset | restore AAR + wind, evict burst GUFIs (ETA +6 h AND plan COMPLETED), reset marker | restore policy, re-publish burst auth_ids with far-future ts, reset marker |
| Domain boolean question | `is_upstream_symptom` | `is_known_merchant_issue` |
| Specialists | weather context · downstream impact · capacity trend (· repositioning) | ring mapper · merchant impact · velocity trend |
| Lead briefer | `arrival_lead_briefer` (never issues a TMI) | `card_testing_lead_investigator` (never applies the block) |
| mcp_* views | mcp_weather, mcp_downstream_risk, mcp_arrival_demand, mcp_inbound_flights, mcp_airport_rate, mcp_active_restrictions | mcp_card_spread, mcp_recent_auths, mcp_merchant_impact, mcp_device_velocity, mcp_risk_policy |
| Product for the live-build beat | `wind-arrival-risk` = capacity_assessment ⋈ weather | `repeat-decline-watch` |
| "You already run this" | SWIM / NEMS / SCDS on Solace | the card network's event backbone |

## Design heuristics when the use case is only a vertical

- Pick the **firehose** the vertical already has (telemetry, orders, auths, claims, trades, sensor
  readings). Pick the **threshold** a human already publishes or a policy already defines (capacity,
  limit, SLA, policy). The breach is "metric vs threshold in effect"; that is the whole demo.
- The hero scenario must be explainable in one sentence to a non-technical audience and must look
  like something that genuinely happens.
- The domain boolean should separate "real problem" from "benign look-alike" (symptom of something
  upstream, a known merchant outage, a planned maintenance window).
- Specialists map to the three questions an operator asks: what else is going on (context), who else
  is affected (impact), is it getting worse (trend). The briefer synthesises; it never acts.
- Keep numbers small and round: 8–12 reference entities, a 60–120 s hero burst, thresholds a viewer
  can read off a gauge.
