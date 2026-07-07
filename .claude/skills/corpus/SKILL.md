---
name: corpus
description: >-
  Mandatory defect corpus handoff for /diagnose, /repair, and compiler fixes.
  Classify family_id, lookup corpus/index (never glob cases), write OPEN/FIXED
  case YAML, run defects validate. Consilium and pytest alone do not replace this.
---

@.claude/prompts/corpus-law.md

# Corpus handoff skill

**Law:** `corpus-law.md` / `.cursor/rules/corpus-law.mdc` (always-on). **This skill:** step-by-step procedure — not optional.

## When mandatory (read this skill first)

```text
/diagnose          → before triage report is final
/repair            → before any src/ compiler code change
failed generate    → when mechanism is known or classifiable
compiler fix PR    → before handoff or "done"
```

**Pairs with:** `/diagnose` → [`/consilium`?] → `/repair`.

## Workflow

| Step | Write |
|------|-------|
| diagnose | OPEN (default) |
| consilium? | audit / amend OPEN only — does not replace diagnose |
| repair | FIXED |

Consilium optional. If skipped, diagnose OPEN stands. `corpus handoff: none strong` = no blocking promote only.

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
2. Pick `family_id` by **mechanism** — never visual symptom.
3. If no row exists but mechanism is clear → add minimal family row, then case.
4. If mechanism unknown → report `unclassified` only — no case YAML.

---

## Step 2 — Lookup (never glob)

```text
corpus/families.yaml              → family_id
corpus/index/<family_id>.yaml     → scan rows
corpus/cases/<case_id>.yaml       → open ONE file for chosen row
```

Pick row: same `project`+`feature` → `OPEN` → `FIXED` with `repair` → `updated_at` desc.

**Screen binding:** `case.project` + `case.feature` = `.debug/screen/<project>/<feature>/`. Enumerate screen `OPEN` via index rows (never glob cases).

**Screen close-out:** user says screen ready / «закрой кейсы» → `FIXED` all `OPEN` for that pair **except** user «кроме …» exceptions; then index + validate. Full rules: `.cursor/skills/corpus/SKILL.md`.

## Step 3 — Write or update case YAML

Template: `corpus/case-template.yaml`. **Diagnose** → `OPEN`. **Consilium** → audit/amend `OPEN` only (see `.cursor/skills/corpus/SKILL.md`). **Repair** → `FIXED` with proof.

One mechanism → one case file. Max 2 repair attempts without fresh `/diagnose`.

---

## Step 4 — Index + validate (every edit)

```bash
poetry run figma-flutter defects index --write
poetry run figma-flutter defects validate
```

No handoff without validate passing.

---

## Forbidden

- Fix from `.debug/` alone; glob all cases; `FIXED` without proof; consilium **replacing** diagnose OPEN on clear mechanisms; hand-edit `corpus/index/`.
