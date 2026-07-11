---
name: fix
description: >-
  Agent-kit batch repair after /debug: implement the fix_plan queue, structural lib/
  edits, dart analyze, re-inspect, corpus auto-FIXED + lesson promotion. Strict
  step protocol. ОТЧЁТ: ПОЧИНКА + fix_report.json only.
disable-model-invocation: true
---

# fix (agent kit repair)

Use after **`/debug`** — or when the user said `/fix`, "чиним", with a fresh **`fix_plan.json`**.

**Separate from the repo compiler flow:**

```text
/debug → /fix         this skill (apps/agent lib/)
/diagnose → /repair   compiler src/ — not this skill
```

**`/fix` closes corpus when proven** — the agent writes **FIXED**; no user sign-off.

## Scope (this phase only)

**Do:** the queue from `fix_plan.json` → `lib/` → analyze → re-inspect → corpus FIXED (+ promotion).
**Stop before:** a new debug without a fresh inspect (except the re-inspect at the end of fix).
**Forbidden in the same turn:** new triage / new `fix_plan` / layout / plan from scratch.

## Hard limits

```text
+1px opaque padding / Positioned nudges to hide overflow
magic colors outside theme
screen-name / figmaId-only branches
hand-edits to pass analyze without fixing structure
ignoring remaining P0/P1 queue items
dart analyze before lib/ changed (only after edits)
```

Evidence: `.agent/features/<feature>/` artifacts — never `.debug/`.

---

## Protocol — execute steps strictly in order

Each step ends with a **Check**. If the Check fails — apply **On fail** and do **not** continue.

### Step 0 — Queue gate

**Action:** Read `.agent/features/<feature>/fix_plan.json`. Sort by `execution_order` (or P0 → P1 → P2).

**Check:** file exists, `ready_for_fix: true`, `node .agent/tools/check.mjs --phase debug` → exit 0.
**On fail:** run **debug** first — no fixing without a fresh queue.

### Step 1 — Playbook + anti-loop

**Action:** Per item `F?` with `family_id`:

1. `.agent/corpus/index/<family_id>.yaml` → matching case (`project: agent`, same feature preferred).
2. FIXED case exists → apply `repair.summary` pattern first.
3. Count prior attempts on this symptom.

**Check:** <2 failed fix attempts on this symptom without a fresh **debug**.
**On fail:** STOP the item, mark `blocked`, note in the case `summary`: `"Fix attempt N (YYYY-MM-DD): <tried> → <why failed>"`. Re-**debug** owns it.

### Step 2 — Implement (structural only, full queue)

**Action:** Work items in order, **P0 → P1 → P2, all in-scope items in one session**. Per item layer:

| layer | action |
|-------|--------|
| `plan` | revise `build_plan.json`, then `lib/` to match |
| `build` | align `lib/` to the plan |
| `visual` | flex, scroll, Stack, extracts, theme tokens |
| `assets` | full **fetch** if needed, pubspec, asset paths |
| `fonts` | rename + `fonts.ps1`, pubspec |
| `layout` | stop — return to **layout**: the perception contract is wrong |

Follow `fix_actions` + `fix_summary_draft`. Update `build_plan.json` when intent was wrong; update catalogs when a widget API or token changes (`widget-reuse.mdc`, `token-reuse.mdc`).

**Check:** every touched change traces to a queue item — no drive-by refactors.
**On fail:** revert the stray edit.

### Step 3 — Verify

**Action:** After `lib/` changed:

```bash
cd apps/agent && dart analyze && dart format .
```

**Check:** analyze exit 0.
**On fail:** fix structure in this phase; never suppress.

### Step 4 — Re-inspect

**Action:** When any visual item was touched: run the **inspect** protocol (region walk + contract checks) against design + built Dart. A fresh user screenshot (`compare_*.png`) sharpens the check but is not required.

**Check:** for each resolved `F?` the matching gap is gone from the fresh `inspect_observation.json`.
**On fail:** the item is **not** resolved — it stays open (Step 1 attempt counter applies).

### Step 5 — Write `fix_report.json` + gate

**Action:**

```json
{
  "version": 2,
  "feature": "<slug>",
  "fix_plan_ref": { "version": 2 },
  "items_resolved": ["F1"],
  "items_still_open": ["F2"],
  "files_touched": ["lib/widgets/…", "build_plan.json"],
  "analyze_exit_code": 0,
  "needs_inspect": false,
  "corpus": [
    { "case_id": "…", "status": "OPEN|FIXED", "path": ".agent/corpus/cases/….yaml" }
  ]
}
```

**Check:** `node .agent/tools/check.mjs --phase fix` → exit 0.
**On fail:** fix the artifact/code per failing lines; re-run.

### Step 6 — Corpus FIXED (agent auto-close)

**Action:** For every proven item (analyze clean + re-inspect gap gone + structural fix): set the case `status: FIXED`, `updated_at`, `repair.summary` (the pattern), `repair.files`, `repair.verification` — per corpus skill § Auto-close. Clean full re-inspect (`perception_gaps: []`, `inspection_complete`, `aligned_with_user`) → close **all remaining OPEN** for the feature (§ Screen close-out). Do not ask "close the case?".

**Check:** `fix_report.corpus[]` matches case files on disk.
**On fail:** sync them.

### Step 7 — Lesson promotion

**Action:** For every family that just got its **2nd FIXED** case: append one line to `.cursor/rules/lessons.mdc` per corpus skill § Promotion (dedupe by `family_id`; respect the 40-lesson cap).

**Check:** no duplicate `family_id` bullets in `lessons.mdc`.
**On fail:** merge instead of appending.

### Step 8 — Report

**Action:** **ОТЧЁТ: ПОЧИНКА** (RU): items resolved/open, files touched, analyze, corpus FIXED (auto), promoted lessons. End with the `Check:` line. **Do not write** separate markdown files.

---

## Done

All in-scope P0/P1 addressed or explicitly blocked; `fix_report.json` written; analyze clean; re-inspect on visual items; OPEN cases FIXED on proof; lessons promoted.
