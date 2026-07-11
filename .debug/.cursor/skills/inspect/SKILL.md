---
name: inspect
description: >-
  /inspect — hunts gaps from available evidence, verifies the screen contract.
  Strict step protocol. No diagnosis, no fixes. Runs before /debug.
disable-model-invocation: true
---

# inspect

**Active inspection** after build: the agent **itself** compares the available evidence against the design, plan, built code, and screen contract. No root-cause analysis, no fixing.

```text
build → inspect → [clarification] → debug → fix → inspect …
```

**inspect ≠ debug.** No `family_id`, no `fix_plan`, no corpus OPEN.

Write to `.agent/features/<feature>/`.

## Evidence

Use whatever evidence actually exists. A user screenshot is useful, but not required.

| Evidence | Source | When |
|----------|--------|------|
| `figma.png` | fetch | design-side visual reference |
| user screenshot | newest `compare_*.png` in the feature dir | when the user provides one |
| runtime error / stack trace / logs | user message or files in the feature dir | when the built screen fails at runtime |
| user description | current request, comments, `user_context.md` | when the user reports behavior or a mismatch |
| Dart + plan | `lib/`, `build_plan.json`, `cleaned.json` | always — structural evidence |

No user screenshot means inspect may be structural, runtime-focused, or mixed. Do not invent pixels the agent never saw; do not ignore clear runtime or structural evidence merely because no screenshot exists.

## Scope (this phase only)

**Do:** evidence vs design/plan/build comparison → `inspect_observation.json`.
**Stop before:** `fix_plan`, `family_id`, `lib/` edits.
**Forbidden in the same turn:** debug, fix, corpus OPEN.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Gate + evidence

**Action:** Confirm inputs and record the evidence actually available.

| Gate | Otherwise |
|------|-----------|
| `build_report.json` → `analyze_exit_code: 0` | **build** |
| `figma.png` on disk | full **fetch** |

Set `sources.evidence_mode` to `user_screenshot`, `runtime`, `structural`, or `mixed`. Record the newest `compare_*.png` when present and list runtime/log evidence paths when present. No `dart analyze` in this phase.

**Check:** analyze green + `figma.png` present; `sources.evidence_mode` matches the evidence on disk/in context.
**On fail:** route per the table.

### Step 1 — Region walk

**Action:** Walk `layout_observation.regions` top-down. For each region compare the applicable sides:

- **design** — `figma.png` + `cleaned.json` (`itemSpacing`, `padding`, `crossAxisAlign`, `cornerRadius`, fills on key `figma_id`s)
- **plan** — what `build_plan.json` said to build
- **built** — actual Dart in `lib/`
- **observed runtime** — screenshot, runtime error, logs, or user description when available

Record per region: `figma_observed`, `built_observed`, `perception_match`: `aligned` | `differs` | `unclear`.

Look at: padding, gap, alignment, thumb sizes, dividers, corner radii, footer/header background, opacity, text clipping, scroll/pinned behavior, exceptions, overflows, failed asset loads, and behavior contradicting the contract. Compare by meaning, not “roughly similar”.

**Check:** every region has a `perception_match` verdict or an explicit note that the evidence does not concern that region.
**On fail:** finish the walk — partial inspection is not an inspection.

### Step 2 — Record gaps

**Action:** Every observable difference or failure → `perception_gaps[]` (`G1`, `G2`, …): `region_id`, `figma_ids`, `figma_shows`, `built_shows`, `evidence` — **without** `fix_action`, `layer`, `family_id`, or severity. Despite the historical field name, a gap may be visual, runtime, behavioral, or structural.

Examples of valid evidence:

- screenshot contradicts `figma.png`
- runtime exception points to the built screen
- Dart contradicts `build_plan.json`
- user reports behavior contradicting `screen_contract.json`

Minor observations → `notable_spots[]`.

**Check:** every `differs` region and every reported runtime/contract failure has at least one gap or a note explaining why not.
**On fail:** record it — unwritten gaps do not exist for debug.

### Step 3 — Contract checks

**Action:** For every `screen_contract` acceptance item with `verify_by: inspect` → `contract_checks[]`:

```json
{ "id": "A1", "status": "pass | fail | blocked", "evidence": "structural: … | runtime: … | screenshot: … | user: …" }
```

`fail` → also record a matching `G*` gap. `blocked` is only for an item that genuinely cannot be judged from the available evidence; say what evidence is missing.

**Check:** all `verify_by: inspect` items have a verdict (check.mjs enforces when `inspection_complete`).
**On fail:** verify or mark `blocked` with a reason.

### Step 4 — Questions (only genuine ones)

**Action:** Question the user only when the evidence is genuinely ambiguous: bug vs intent, missing reproduction details, an unclear stack trace, stub behavior, or a blocked contract check. An obvious defect is a gap, not a question. Questions → `questions_for_user[]` + **УТОЧНЕНИЕ (inspect)** block; stop only when the ambiguity prevents a reliable gap list.

Clear runtime evidence or an unambiguous plan/code contradiction does **not** require user confirmation before debug.

**Check:** no gap disguised as a question, no question disguised as a gap.
**On fail:** reclassify.

### Step 5 — Write artifact + gate

**Action:** Write `inspect_observation.json`:

```json
{
  "version": 1,
  "feature": "<slug>",
  "sources": {
    "figma_png": true,
    "evidence_mode": "user_screenshot | runtime | structural | mixed",
    "screenshot": "compare_*.png | null",
    "runtime_evidence": []
  },
  "regions": [],
  "perception_gaps": [],
  "notable_spots": [],
  "contract_checks": [],
  "questions_for_user": [],
  "inspection_complete": false,
  "aligned_with_user": false
}
```

Prose values — Russian. Set `inspection_complete: true` after Steps 1–3. Set `aligned_with_user: true` when the gap list is supported by the available evidence and does not contradict the user's report. Explicit user confirmation is useful when intent is disputed, but is not required for an unambiguous runtime, structural, or visual defect.

**Check:** `node .agent/tools/check.mjs --phase inspect` → exit 0.
**On fail:** fix the artifact; re-run.

### Step 6 — Report + handoff

**Action:** **ОТЧЁТ: ОСМОТР** (RU): evidence mode, gap list G*, contract check verdicts, questions. End with the `Check:` line.

| State | Next |
|-------|------|
| gaps exist + `aligned_with_user: true` | **debug** |
| no gaps, inspection complete, contract checks pass | done · **agent: FIXED** applicable OPEN cases for the feature (corpus § Auto-close) |
| questions / disagreement / `blocked` checks | **УТОЧНЕНИЕ (inspect)** |

---

## Forbidden

Diagnosis and fixes · `fix_plan` · `lib/` edits · passive “awaiting instructions” when evidence exists · inventing a device screenshot or runtime result the agent never saw · `.debug/`
