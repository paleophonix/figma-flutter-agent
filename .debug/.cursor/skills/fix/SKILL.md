---
name: fix
description: >-
  Agent-kit batch repair after /debug: implement the fix_plan queue, structural lib/
  edits, dart analyze, re-inspect with available evidence, corpus auto-FIXED +
  lesson promotion. Strict step protocol. ОТЧЁТ: ПОЧИНКА + fix_report.json only.
disable-model-invocation: true
---

# fix (agent kit repair)

Use after **`/debug`** — or when the user said `/fix`, "чиним", with a fresh **`fix_plan.json`**.

**Separate from the repo compiler flow:**

```text
/debug → /fix         this skill (apps/agent lib/)
/diagnose → /repair   compiler src/ — not this skill
```

**`/fix` closes corpus when proven** — the agent writes **FIXED**; no user sign-off is required when the available evidence is sufficient.

## Scope (this phase only)

**Do:** the queue from `fix_plan.json` → `lib/` → analyze → re-inspect with appropriate evidence → corpus FIXED (+ promotion).
**Stop before:** a new debug without a fresh inspect.
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

Evidence: `.agent/features/<feature>/` artifacts, runtime output, and user-provided context — never compiler `.debug/`.

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

### Step 3 — Static verify

**Action:** After `lib/` changed:

```bash
cd apps/agent && dart analyze && dart format .
```

Also run any directly relevant command already available for the item: asset/path checks, focused tests, or a reproduction command supplied by the user.

**Check:** analyze exit 0; directly runnable checks pass.
**On fail:** fix structure in this phase; never suppress.

### Step 4 — Re-inspect with appropriate evidence

**Action:** Run the **inspect** protocol against the evidence appropriate to each item:

| Defect | Sufficient verification examples |
|--------|----------------------------------|
| runtime | reproduction no longer fails; stack trace cause removed; focused test passes |
| build/plan | Dart now matches `build_plan.json`; relevant contract check passes |
| assets/fonts | path/font report/pubspec check passes; runtime load error gone when reproducible |
| visual/layout | available screenshot or user report, or an unambiguous structural contradiction is gone |

A screenshot improves visual verification but is not universally required. Do not invent a runtime result or visual result that was not observed. When the necessary evidence is unavailable, keep the item open or blocked rather than asking for unrelated proof.

**Check:** for each candidate resolved `F?`, the matching gap is gone from the fresh `inspect_observation.json` according to the relevant evidence.
**On fail:** the item is **not** resolved — it stays open (Step 1 attempt counter applies).

### Step 5 — Corpus FIXED (agent auto-close)

**Action:** For every proven item, set the case `status: FIXED`, `updated_at`, `repair.summary` (the reusable pattern), `repair.files`, and `repair.verification` per corpus skill § Auto-close.

Proof must match the defect: analyze for analyzer failures, reproduction/tests for runtime failures, plan/code evidence for structural failures, and visual/user evidence when the claim is inherently visual. A clean inspect closes only the OPEN cases actually supported by that inspect; do not close unrelated cases merely because the screen has no listed gaps.

**Check:** every case marked FIXED has matching verification evidence; unproven items remain OPEN.
**On fail:** restore OPEN or add the missing proof.

### Step 6 — Lesson promotion

**Action:** For every family that just got its **2nd FIXED** case: append one line to `.cursor/rules/lessons.mdc` per corpus skill § Promotion (dedupe by `family_id`; respect the 40-lesson cap).

**Check:** no duplicate `family_id` bullets in `lessons.mdc`.
**On fail:** merge instead of appending.

### Step 7 — Write `fix_report.json` + gate

**Action:** Write the report after corpus and promotion are finalized:

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

Set `needs_inspect: true` only when a remaining item needs evidence not available in this run.

**Check:** `fix_report.corpus[]` matches case files on disk **and** `node .agent/tools/check.mjs --phase fix` → exit 0.
**On fail:** fix the artifact/code/corpus state per failing lines; re-run.

### Step 8 — Report

**Action:** **ОТЧЁТ: ПОЧИНКА** (RU): items resolved/open, files touched, analyze, verification evidence, corpus FIXED/OPEN, promoted lessons. End with the `Check:` line. **Do not write** separate markdown files.

---

## Done

All in-scope P0/P1 addressed or explicitly blocked; `fix_report.json` written; analyze clean; each resolved item re-inspected with appropriate evidence; OPEN cases FIXED only on proof; lessons promoted.
