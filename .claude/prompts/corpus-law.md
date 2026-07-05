# CRITICAL — Defect corpus law

**No compiler fix is done without corpus proof.** `.debug/` is triage only — not a substitute for cases, fixtures, or named laws.

## Applies to

`/diagnose`, `/repair`, failed `generate`, any layout/IR/emitter bug, any `src/` compiler change, before PR or handoff.

## Mandatory chain

```text
symptom → family_id (mechanism) → corpus lookup → law_id + layer → generic fix → case proof → defects validate
```

Classify **mechanism**, not symptom. `family_id` from `corpus/families.yaml` — never `overflow`, `wrong_checkbox`, or screen name.

## Lookup (never glob `corpus/cases/`)

```text
corpus/families.yaml              → family_id
corpus/index/<family_id>.yaml     → scan rows: case_id, project, feature, status, summary
corpus/cases/<case_id>.yaml       → open ONE file for the chosen row
```

Pick row: same `project`+`feature` first → `OPEN` → `FIXED` with `repair` → `observed_at` desc.

## Status (binary)

| When | status |
|------|--------|
| `/diagnose` classifies mechanism | `OPEN` (write or update case) |
| `/repair` without proof | stay `OPEN` |
| `/repair` with proof + `repair` block | `FIXED` |

`/repair` alone closes nothing. Max **2** repair attempts per item without fresh `/diagnose`.

## After every case edit

```bash
poetry run figma-flutter defects index --write
poetry run figma-flutter defects validate
```

`corpus/index/` is **generated** — never hand-edit.

## Forbidden

- Ship a fix from `.debug/` or golden diff alone — no `family_id`, no case YAML
- `FIXED` without `repair` block and regression proof
- Glob `corpus/cases/*.yaml` to browse
- Skip `defects validate` before handoff
- Use visual symptom as `family_id`

## Done checklist

1. `family_id` + `law_id` + owning layer named
2. `corpus/cases/<case_id>.yaml` with evidence (template: `corpus/case-template.yaml`)
3. Generic regression test or fixture — not one screen patch
4. `poetry run figma-flutter defects validate` passes

Promotion funnel: `inbox → corpus → fixtures → blocking`. Details: `corpus/README.md`, arrow routing: `pipeline-contracts.mdc`.

**Procedure:** `.cursor/skills/corpus/SKILL.md` (or `.claude/skills/corpus/SKILL.md`) — mandatory on `/diagnose` and `/repair`.
