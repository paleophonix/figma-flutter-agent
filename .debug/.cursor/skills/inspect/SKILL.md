---
name: inspect
description: >-
  /inspect — hunts visual gaps figma vs render/plan, verifies the screen
  contract. Strict step protocol. No diagnosis, no fixes. Runs before /debug.
disable-model-invocation: true
---

# inspect

**Active inspection** after build: the agent **itself** compares design against the built screen, records differences, and verifies the screen contract. No root-cause, no fixing.

```text
build → inspect → [clarification] → debug → fix → inspect …
```

**inspect ≠ debug.** No P0/P1, no `family_id`, no `fix_plan`, no corpus OPEN.

Write to `.agent/features/<feature>/`.

## Visual evidence (no capture tool)

The kit does **not** screenshot the running app. Visual truth comes from:

| Evidence | Source | When |
|----------|--------|------|
| `figma.png` | fetch | always (design side) |
| user screenshot | user drops `compare_*.png` into the feature dir | when the user ran the app |
| Dart + plan | `lib/`, `build_plan.json`, `cleaned.json` | always (structural side) |

**No user screenshot ⇒ inspect is structural:** verify the built Dart against `build_plan` + `cleaned.json` + `figma.png` intent. Anything that genuinely needs pixels on a device → contract check `blocked`, ask the user to run and screenshot.

## Scope (this phase only)

**Do:** design vs build comparison → `inspect_observation.json`.
**Stop before:** `fix_plan`, `family_id`, `lib/` edits.
**Forbidden in the same turn:** debug, fix, corpus OPEN.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Gate + evidence

**Action:** Confirm inputs.

| Gate | Otherwise |
|------|-----------|
| `build_report.json` → `analyze_exit_code: 0` | **build** |
| `figma.png` on disk | full **fetch** |

Note the visual evidence mode in `sources`: `user_screenshot` (newest `compare_*.png` present) or `structural` (none). No `dart analyze` in this phase.

**Check:** analyze green + `figma.png` present; `sources.evidence_mode` set.
**On fail:** route per the table.

### Step 1 — Region walk

**Action:** Walk `layout_observation.regions` top-down. For each region compare **three sides**:

- **design** — `figma.png` + `cleaned.json` (`itemSpacing`, `padding`, `crossAxisAlign`, `cornerRadius`, fills on key `figma_id`s)
- **plan** — what `build_plan.json` said to build
- **built** — the actual Dart in `lib/` (and the user screenshot, if `evidence_mode: user_screenshot`)

Record per region: `figma_observed`, `built_observed`, `perception_match`: `aligned` | `differs` | `unclear`.

Look at: padding, gap, alignment, thumb sizes, dividers, corner radii, footer/header background, opacity, text clipping, scroll/pinned behavior. Compare **by meaning** (whitespace, centering, a missing divider), not "roughly similar".

**Check:** every region has a `perception_match` verdict.
**On fail:** finish the walk — partial inspection is not an inspection.

### Step 2 — Record gaps

**Action:** Every noticeable difference → `perception_gaps[]` (`G1`, `G2`, …): `region_id`, `figma_ids`, `figma_shows`, `built_shows` — **without** `fix_action`, `layer`, or severity. Minor observations → `notable_spots[]`.

A gap found structurally (Dart contradicts plan/design) is as valid as one seen on a screenshot — say which in `evidence`.

**Check:** every `differs` region has at least one gap or a note explaining why not.
**On fail:** record it — unwritten gaps do not exist for debug.

### Step 3 — Contract checks

**Action:** For every `screen_contract` acceptance item with `verify_by: inspect` → `contract_checks[]`:

```json
{ "id": "A1", "status": "pass | fail | blocked", "evidence": "structural: … | screenshot: …" }
```

`fail` → also record a matching `G*` gap. `blocked` → the item needs pixels/device the agent cannot see: say so, request a user screenshot.

**Check:** all `verify_by: inspect` items have a verdict (check.mjs enforces when `inspection_complete`).
**On fail:** verify or mark `blocked` with a reason.

### Step 4 — Questions (only genuine ones)

**Action:** Question the user **only** when genuinely unclear (bug vs intent, stub behavior, or a `blocked` check needing a screenshot). An obvious defect is a gap, not a question. Questions → `questions_for_user[]` + **УТОЧНЕНИЕ (inspect)** block; stop the protocol here if alignment is impossible without answers.

**Check:** no gap disguised as a question, no question disguised as a gap.
**On fail:** reclassify.

### Step 5 — Write artifact + gate

**Action:** Write `inspect_observation.json`:

```json
{
  "version": 1,
  "feature": "<slug>",
  "sources": { "figma_png": true, "evidence_mode": "user_screenshot | structural", "screenshot": "compare_*.png | null" },
  "regions": [],
  "perception_gaps": [],
  "notable_spots": [],
  "contract_checks": [],
  "questions_for_user": [],
  "inspection_complete": false,
  "aligned_with_user": false
}
```

Prose values — Russian. Set `inspection_complete: true` after Steps 1–3; `aligned_with_user: true` when the user confirmed the gap list (or had no objection).

**Check:** `node .agent/tools/check.mjs --phase inspect` → exit 0.
**On fail:** fix the artifact; re-run.

### Step 6 — Report + handoff

**Action:** **ОТЧЁТ: ОСМОТР** (RU): evidence mode, gap list G*, contract check verdicts, questions. End with the `Check:` line.

| State | Next |
|-------|------|
| gaps exist + `aligned_with_user: true` | **debug** |
| no gaps, inspection complete, contract checks pass | done · **agent: FIXED** all OPEN cases for the feature (corpus § Auto-close) |
| questions / disagreement / `blocked` checks | **УТОЧНЕНИЕ (inspect)** |

---

## Forbidden

Diagnosis and fixes · `fix_plan` · `lib/` edits · passive "awaiting instructions" when evidence exists · inventing a device screenshot the agent never saw · `.debug/`
