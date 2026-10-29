# Presentation assets — what to generate and the shape of each

All four are domain-specific and must be rewritten from the contract, never sed-renamed. Keep the
file names: the Makefile, README and the UI link to them.

## `PRESENTATION_SCRIPT.md` (the live talk, ~15 min)

```
# Presentation Script — "<Title that names the data layer, not the AI>"
**Audience:** … **who already run <the vertical's existing event backbone>**
**Story:** they already run the hard part (data movement); this extends it: moving → understanding (Continuum) → acting (Agent Mesh).
**The differentiator (say it plainly, early):** scenarios are illustrative; AI is table stakes; the data layer as a capability is the point.
**What's new vs a feature tour:** building a new capability live, safely.
Setup links → README.md, demo/README.md; framing → BUSINESS.md; ground truth → CLAUDE.md.

## Cue card — what to hit            (one screen; bullets per beat; Q&A landmines; stage gotchas)
## Pre-flight (30 min before)        (make demo-ready; open demo.html?tv=1 + continuum-pipeline.html?tv=1; make ops; reset state; clear stale product)
## Opening deck (`slides.html`)      (walk the 8 slides in order; ~3–4 min)
## Beats
### 1 · The frame, then the vision (2 min)       — per slide: "▸ Slide N — title" + **Say:** quotes
### 2 · The data layer, running (90 s)           — name the three layers; open the lineage graph; boxes flash = incremental compute; click a node = running SQL
### 3 · A capability already on the layer (2 min) — fire the hero scenario; see threshold tile drop, gauges go red, storm → one incident, triage, brief; "advisory only"
### 4 · THE HEART — build a NEW data product, live (4 min) — scenario in a sentence; + Data product → prefilled SELECT → Create; compiling→running in seconds; prove it: reset → fire → new trigger flashes
### 5 · The control that makes that safe (2 min) — additive by construction; single source of truth reused; governed (versioned YAML, schema-validated SQL, the base pipeline is never touched)
### 6 · Agility and speed, named (90 s)           — runtime ms/event; build time minutes; close
## Recovery                           (table: symptom → do; include the cold-compile, stale product, slow triage = external latency, hero stuck RED → make reset, no decision → check ops + SAM, pipeline not Running)
## Likely questions                   (8–12 Q&A pairs: "already handled by existing programs?", "vs <vertical's incumbent AI>?", "rip-and-replace?", "how is the live build that fast?", "can't Flink/lakehouse?", "does the fast path have to be an LLM?", "is it taking the action itself?", "how real is the data?", "governance?" (answer: versioned YAML, SQL validated before deploy, additive products, no Event Portal in this demo), "could a domain team do this?")
```

Rules: every **Say:** line is speakable prose, no slide-ese; every **Show:** line names the exact
page/button/`make` target; timings sum to the slot; the hero numbers (threshold before/after, burst
size, SEVERE band) are quoted from the contract so the script never contradicts the gauges.

## `stack/api/static/slides-speaker-notes.md` (8 slides, matches `slides.html`)

```
# Speaker notes — `slides.html`
(intro: how to drive the deck; keys; what the bridge slide hands to)
## 1 · Move. Understand. Act.          *On screen:* … – 3 bullets – **Transition:** "…"
## 2 · From Firehose to Result
## 3 · A Proven Foundation, Extended   (the vertical's backbone they already run)
## 4 · Build It Once, Feed Everything
## 5 · Compute the Change, Not the World
## 6 · Analysis-Ready Context
## 7 · Fast Triage, Deep Investigation
## 8 · See It Live (bridge to the demo)
```
Slides 1, 2, 4, 5, 7 are platform-generic: keep their bodies, swap the examples. Slides 3, 6, 8 are
domain: rewrite. Each slide: *On screen:* one line, 2–4 bullets, a **Transition:** quote.

## `slides.html`
Reuse the deck shell, CSS tokens, fonts and nav JS verbatim; change only headline/body text and the
example labels inside the 8 `.slide` sections. Brand: Solace Platform, Continuum, Agent Mesh —
never the engine's name, never "PubSub+".

## `CEO-VIDEO-SCRIPT.md` (5:30 talking-head + screen, optional)
Beats with timecodes: why real-time AI (business case) · the three layers · the use case + what is
already running · always-current strongly-consistent state · the broker provisioned itself · how real
is the real-time + the AI judges · the negative + two-speed AI · the moat and "too early" · a
tighter cut · recovery while recording · objection handling pocket card · honesty box (real vs vision).
Generate it only if the user wants a recorded version; otherwise drop the stale FX one.

## `BUSINESS.md` (stakeholder, ~50 lines, no implementation detail)
Problem · why now · what the demo shows · the three layers in business terms · value (speed to
build, speed at runtime, governance) · what is illustrative vs real.

## `README.md` (developer quick start + data streams table + make-target table)
Keep the structure of the reference README; every topic/queue/view name from the contract.
