---
name: corpus
description: >-
  Mandatory defect corpus handoff for /diagnose, /repair, and compiler fixes.
  Classify family_id, lookup corpus/index (never glob cases), write OPEN/FIXED
  case YAML, run defects validate. Consilium and pytest alone do not replace this.
---

@.cursor/rules/corpus-law.mdc

# Corpus handoff skill

**Law:** `corpus-law.mdc` (always-on). **This skill:** step-by-step procedure agents must run — not optional.

## When mandatory (read this skill first)

```text
/diagnose          → before triage report is final
/repair            → before any src/ compiler code change
failed generate    → when mechanism is known or classifiable
compiler fix PR    → before handoff or "done"
```

**Pairs with:** `/diagnose` → [`/consilium`?] → `/repair`. Do not mix with `/debug` → `/fix` (infra).

## Workflow by step

```text
/diagnose     read index + write OPEN (default when mechanism clear)
/consilium?   audit / amend OPEN — optional; does NOT replace diagnose write
/repair       read index + write OPEN→FIXED
```

| Step | Corpus read | Corpus write |
|------|-------------|--------------|
| **diagnose** | always (Step 2) | **OPEN** when `ready_for_record` + confidence `high`/`medium` |
| **consilium** | audit diagnose cases + index | **amend** family/summary/evidence; **first OPEN** if diagnose left `needs_evidence` |
| **repair** | before each R? (anti-loop) | **OPEN** attempts; **FIXED** + `repair` when proven |

**Consilium is optional.** If skipped, diagnose must have written OPEN (or reported `unclassified` / deferred with reason). Repair must not start without on-disk case for each in-scope mechanism.

## What is NOT corpus-done

| Partial proof | Corpus status |
|---------------|---------------|
| `.debug/` triage only | not done |
| Screen fixture / emit-law pytest only | supporting proof only |
| Consilium: "corpus handoff: none strong" | **blocking deferred** — inbox OPEN case still required |
| `FIXED` without `repair` block | invalid |
| Skipped `defects validate` | not done |

Promotion funnel: `inbox → corpus → fixtures → blocking`. **This skill covers inbox through validate.** Blocking/oracle waits for stable baseline + product OK.

---

## Step 1 — Classify mechanism

1. Read `corpus/families.yaml`.
2. Pick `family_id` by **mechanism** (law + pipeline arrow + owning stage) — never visual symptom (`overflow`, `wrong_radio`, screen name).
3. If no row exists but mechanism is clear (named `law_id`, owning module, arrow):
   - Add a minimal family row to `families.yaml` (`status: active`).
   - Re-run validate after case work.
4. If mechanism is unknown → report `unclassified` only — **do not write case YAML**.

---

## Step 2 — Lookup (never glob)

```text
corpus/families.yaml              → family_id
corpus/index/<family_id>.yaml     → scan rows: case_id, project, feature, status, summary
corpus/cases/<case_id>.yaml       → open ONE file for the chosen row
```

Pick row: same `project`+`feature` first → `OPEN` → `FIXED` with `repair` → `observed_at` desc.

`corpus/index/` is **generated** — never hand-edit.

---

## Step 3 — Write or update case YAML

Template: `corpus/case-template.yaml`.

### On `/diagnose` (OPEN)

When `corpus_status: ready_for_record` and confidence `high` or `medium`:

1. Create or update `corpus/cases/YYYY-MM-DD-<mechanism-slug>.yaml`.
2. **New case:** set `case.created_at` (UTC minute, e.g. `2026-07-05T16:34:00Z`). **Every edit:** bump `case.updated_at` (≥ `created_at`).
3. Each occurrence: `status: OPEN` — **never `FIXED` on diagnose**.
4. `case.summary`: mechanism + contract expected/actual + first arrow where fact changed. No fix recipe or test names in summary.
5. `evidence`: repo-relative `.debug/screen/<project>/<feature>/…` paths.
6. Leave `repair` absent or empty.
7. Emit `repair_summary_draft` (2–3 sentences) per queue item for `/repair`.

**One mechanism → one case file.** Update in place; do not fork per retry.

### On `/repair` (OPEN → FIXED)

Before coding on queue item `R?`:

1. Resolve `family_id` → read index → open matching `OPEN` row (or write `OPEN` first if diagnose was skipped).
2. If case documents ≥2 failed repair attempts without fresh `/diagnose` → **STOP** item; ask re-diagnose.

While repairing: status stays `OPEN`. Failed attempt → append one line to `case.summary`:
`Repair attempt N (YYYY-MM-DD): <tried> → <why failed>`. **Always bump `case.updated_at`.**

When proof is conclusive (all must hold):

```text
targeted regression test passes (generic law, not screen patch)
fix at owning compiler layer
symptom class would not recur on same law
```

Then: `status: FIXED`, fill `repair.summary`, `changed_files`, `regression_tests`, `verification`.

`/repair` alone closes nothing. Max **2** repair attempts per item without fresh `/diagnose`.

---

## Step 4 — Index + validate (every edit)

```bash
poetry run figma-flutter defects index --write
poetry run figma-flutter defects validate
```

Fix YAML until exit 0. **No handoff without validate passing.**

---

## Done checklist

```text
[ ] family_id + law_id + owning layer named
[ ] corpus/cases/<case_id>.yaml with evidence + `created_at` / `updated_at` (UTC minute)
[ ] generic regression test linked in repair.regression_tests (when FIXED)
[ ] defects validate passes
[ ] blocking/oracle promote — only if product + stable baseline (optional, later)
```

---

## Forbidden

- Ship fix from `.debug/` or golden diff alone
- Glob `corpus/cases/*.yaml` to browse
- Mark `FIXED` because unrelated pytest passed
- Let consilium triage skip Steps 3–4 when `/diagnose` or `/repair` ran
- Hand-edit `corpus/index/`

---

## Report lines (paste in triage / repair output)

```text
Corpus recorded:
  - family_id: …
  - case: corpus/cases/….yaml (OPEN | FIXED)
  - validate: pass | fail (command + error)

Corpus deferred:
  - reason: unclassified | needs_evidence | infra (/debug flow)
```
