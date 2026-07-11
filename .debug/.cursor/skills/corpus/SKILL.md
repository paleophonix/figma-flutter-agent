---
name: corpus
description: >-
  Corpus handoff: plan reads, debug OPENs, fix/inspect auto-FIXED when proven,
  recurring lessons promoted to lessons.mdc.
disable-model-invocation: true
---

# Corpus (agent kit)

Root: `apps/agent/.agent/corpus/`. Law: `corpus-law.mdc`.

## When

| Phase | Corpus |
|-------|--------|
| **plan** | read `features/<feature>.yaml` + cases — known failure modes into `plan_notes` |
| **debug** | OPEN a compact case (on disk, same turn) |
| **fix** | playbook → **agent auto-FIXED** on proof → promotion check |
| **inspect** | clean screen → **agent auto-FIXED** all OPEN for the feature |

## Auto-close (agent — without waiting for the user)

The agent **itself** closes cards when the proof exists. Do not ask "close the case?".

### When FIXED

| Trigger | Conditions | `repair` |
|---------|-----------|----------|
| **After fix** | `analyze_exit_code: 0` · re-**inspect** · the gap/symptom from `F?` is gone · structural fix (not +1px) | `summary` + `files` from fix |
| **Screen clean** | `inspect`: `perception_gaps: []` · `inspection_complete: true` · `aligned_with_user: true` | close **all OPEN** `project: agent` + `feature` |

### Do not close

- a gap matching the case mechanism is **still in inspect**
- `fix_report.items_still_open` contains the related `F?`
- 2 fix attempts exhausted, the symptom is **still on the PNG** → stays OPEN, needs a fresh **debug**
- the user explicitly said **"кроме …"** (except) — those case ids stay OPEN

### How to close

1. `status: FIXED` · `updated_at` UTC
2. `repair:` block — `summary` (the pattern), `files`, `verification` (≤1 path, e.g. `inspect_observation.json`)
3. `fix_report.json` / **ОТЧЁТ** — `Corpus: … FIXED (auto)`
4. Do not remove the case from `features/<feature>.yaml` — history stays

### Screen close-out

A clean inspect on the feature → walk `features/<feature>.yaml` → every OPEN case → FIXED with `repair.summary` from the last fix, or `Verified clean inspect — no remaining gaps`.

## Promotion (recurring lesson → permanent rule)

When a `family_id` reaches its **2nd FIXED** case:

1. Distill the mechanism into **one line**: what to do (or never do) so the mistake cannot recur.
2. Append to `.cursor/rules/lessons.mdc` § Laws: `- <family_id>: <one-line law>. (cases: <id>, <id>)`
3. **Dedupe by `family_id`** — an existing bullet gets the new case id appended, not a second bullet.
4. Cap: 40 lessons — at the cap, merge related bullets or retire the least recurring one.
5. Report: `Lesson promoted: <family_id>`.

Promotion happens in **fix** (Step 7). plan benefits automatically — `lessons.mdc` is always-on.

## Lookup

```text
families.yaml → family_id
index/<family_id>.yaml → one case_id
cases/<case_id>.yaml
```

Never glob `cases/*.yaml`.

## Compact case (mandatory shape)

Copy `case-template.yaml`. **One file = one mechanism.**

| Field | Rule |
|-------|------|
| `summary` | 2–4 sentences: mechanism + lesson for the future. Not a diary of rounds. |
| `evidence` | **≤2 paths** — no nested `kind`/`summary` |
| `figma_ids` | optional, up to 5 ids |
| `repair` | **FIXED only** — `summary` + `files` |

**Do not write:** `occurrences[]`, `blast_radius`, `origin`, `pipeline_arrow`, `owner`, empty `repair` on OPEN, `title`/`case_kind`/`observed_at`, long evidence lists, compare PNGs in corpus (they live in the feature dir).

Skip YAML for a one-off or `unclassified` without a lesson. **Trivial** (forgot tool, typo, single config) → `fix_plan` only — see `corpus-law.mdc` § Skip corpus.

## debug → OPEN

1. `cases/YYYY-MM-DD-<slug>.yaml`, `status: OPEN`, `project: agent`
2. Append the case id to `corpus/features/<feature>.yaml` (create if missing)
3. `fix_summary_draft` goes into `fix_plan.json` — for fix; do not duplicate it as a case essay

## fix → FIXED (agent auto)

Structural fix + analyze clean + re-inspect symptom gone → **agent writes FIXED** (see Auto-close), then checks Promotion. Max 2 fix attempts without a fresh debug — otherwise it stays OPEN.

## Report

```text
Corpus: .agent/corpus/cases/….yaml (OPEN|FIXED)
Lesson promoted: <family_id>   # when promotion fired
```
