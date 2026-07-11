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
| **debug** | OPEN a compact case on disk before finalizing `fix_plan.json` |
| **fix** | playbook → **agent auto-FIXED** on matching proof → promotion check |
| **inspect** | close only the OPEN cases supported by the current evidence |

## Auto-close (agent — without waiting for the user)

The agent **itself** closes cards when sufficient proof exists. Do not ask “close the case?”. Do not demand a screenshot for a runtime or structural defect when stronger relevant proof already exists.

### When FIXED

| Defect/proof | Conditions | `repair` |
|--------------|------------|----------|
| analyzer/static | relevant check passes; `analyze_exit_code: 0` when applicable | `summary` + `files` + check path/result |
| runtime | reproduction/test no longer fails, or the reported exception cause is removed and verifiable | `summary` + `files` + runtime/test evidence |
| structural | implementation matches `build_plan.json` / contract and fresh inspect no longer reports the gap | `summary` + `files` + inspect evidence |
| visual | fresh screenshot/user report when needed, or another unambiguous visual proof | `summary` + `files` + visual evidence |

A screenshot is evidence, not a universal gate. Match the proof to the defect.

### Do not close

- the case symptom is still present in fresh inspect/runtime evidence
- `fix_report.items_still_open` contains the related `F?`
- 2 fix attempts are exhausted and the symptom still reproduces → stays OPEN, needs fresh **debug**
- the user explicitly said **“кроме …”** — those case ids stay OPEN
- the current evidence does not actually verify this case, even if another gap on the same screen was fixed

### How to close

1. `status: FIXED` · `updated_at` UTC
2. `repair:` block — `summary` (the reusable pattern), `files`, `verification` (≤1 primary path/result)
3. `fix_report.json` / **ОТЧЁТ** — `Corpus: … FIXED (auto)`
4. Do not remove the case from `features/<feature>.yaml` — history stays

### Screen close-out

A clean inspect may close multiple OPEN cases for the feature only when its evidence covers their mechanisms. Walk `features/<feature>.yaml`, match each OPEN case to the verified gaps/checks, and leave unrelated or unproven cases OPEN.

## Promotion (recurring lesson → permanent rule)

When a `family_id` reaches its **2nd FIXED** case:

1. Distill the mechanism into **one line**: what to do (or never do) so the mistake cannot recur.
2. Append to `.cursor/rules/lessons.mdc` § Laws: `- <family_id>: <one-line law>. (cases: <id>, <id>)`
3. **Dedupe by `family_id`** — an existing bullet gets the new case id appended, not a second bullet.
4. Cap: 40 lessons — at the cap, merge related bullets or retire the least recurring one.
5. Report: `Lesson promoted: <family_id>`.

Promotion happens in **fix** after proof and before the final `fix_report.json`. Plan benefits automatically — `lessons.mdc` is always-on.

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
| `repair` | **FIXED only** — `summary` + `files` + `verification` |

**Do not write:** `occurrences[]`, `blast_radius`, `origin`, `pipeline_arrow`, `owner`, empty `repair` on OPEN, `title`/`case_kind`/`observed_at`, long evidence lists, compare PNGs in corpus (they live in the feature dir).

Skip YAML for a one-off or `unclassified` without a lesson. **Trivial** (forgot tool, typo, single config) → `fix_plan` only — see `corpus-law.mdc` § Skip corpus.

## debug → OPEN

1. `cases/YYYY-MM-DD-<slug>.yaml`, `status: OPEN`, `project: agent`
2. Append the case id to `corpus/features/<feature>.yaml` (create if missing)
3. Finalize the matching `fix_plan.json` item with `corpus_status: record_open` + the real case id
4. `fix_summary_draft` stays in `fix_plan.json` — do not duplicate it as a case essay

## fix → FIXED (agent auto)

Structural fix + relevant checks + fresh inspect/reproduction proving the symptom gone → **agent writes FIXED**, then checks Promotion. Max 2 fix attempts without a fresh debug — otherwise it stays OPEN.

## Report

```text
Corpus: .agent/corpus/cases/….yaml (OPEN|FIXED)
Lesson promoted: <family_id>   # when promotion fired
```
