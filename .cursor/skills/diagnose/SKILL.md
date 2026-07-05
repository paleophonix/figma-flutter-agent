---
name: diagnose
description: >-
  Diagnosis for screen/compiler pipeline. Builds BATCH PRE-FIX TRIAGE REPORT,
  writes OPEN corpus cases on disk when mechanism is known, runs defects validate
  before handoff. Pairs with /repair. CRITICAL: chat-only corpus handoff is forbidden.
---

@.claude/prompts/debug-common.md

**Mandatory corpus:** Read and follow `.cursor/skills/corpus/SKILL.md` before finalizing the report (Step 6). Consilium or pytest alone does not replace it.

## CRITICAL — Corpus on disk before handoff (non-negotiable)

A `/diagnose` turn is **not done** until corpus Steps 3–4 complete whenever any root cause has `corpus_status: ready_for_record` (confidence `high` or `medium`).

**FORBIDDEN — treating these as corpus-done:**

```text
Corpus handoff (Cursor): YAML blocks in chat only
"Cursor will write cases" / "handoff for repair" without file I/O
Consilium APPROVE without corpus/cases/*.yaml on disk
BATCH PRE-FIX TRIAGE REPORT delivered before defects validate (when cases apply)
Deferring OPEN case YAML to /repair — repair writes FIXED only; diagnose owns OPEN
```

**REQUIRED before the final diagnose reply** (per `.cursor/skills/corpus/SKILL.md`):

```text
1. Write or update corpus/cases/YYYY-MM-DD-<mechanism-slug>.yaml (status: OPEN)
2. poetry run figma-flutter defects index --write   # when cases added or changed
3. poetry run figma-flutter defects validate          # exit 0
4. Report Corpus recorded: with actual paths written — not proposed case_ids
```

**Allowed on `/diagnose`:** `corpus/` YAML + `corpus/families.yaml` (new family row when mechanism is clear). **Not allowed:** `src/` compiler code, generated Dart, golden baseline updates.

When `corpus_status` is `unclassified` or `needs_evidence`, report `Corpus recorded: none — <reason>` — do not invent cases.

**Same law as `corpus-law.mdc`:** diagnose without on-disk OPEN case when mechanism is known = incomplete handoff, same class of error as shipping a compiler fix without corpus proof.

---

# Debug Diagnose Skill

Use for failed **generate/wizard/golden** runs on a **specific screen** —
layout, IR, emitter, analyzer, visual mismatch.

**Separate flow (do not mix with debug-fix):**

```text
/diagnose → /repair     screen/compiler
/debug → /fix             control panel / infra — not this skill
```

**Diagnosis-only for compiler code** — no Dart/IR fixes in `/diagnose`. **Exception:** write
`corpus/cases/*.yaml` with `status: OPEN` when classification is ready (see Step 6).

Code changes belong to **`/repair`** (`/repair`, "чиним всё") in the same flow or a follow-up.

Do not edit generated Dart.
Do not update golden baselines to hide failures.
Do not patch one screen, node id, customer path, or fixture coordinate as a
production shortcut.

## Anti-patching (mandatory)

Forbidden: screen/feature/`figmaId`/text-value/asset-filename/customer-path/fixture-specific production code; magic coordinates/padding/colors; baseline updates to hide failure; production text/name regex heuristics.

Required: named law + owning compiler layer; reusable fix for any Figma tree; regression proof per queue item.

If only a local workaround exists: stop — report forbidden shortcut, do not implement or queue it.

---

## Goal

```text
.debug artifacts / traces
  -> symptom
  -> contract_kind / law
  -> responsible pipeline layer
  -> repair queue (P0–P3)
  -> BATCH PRE-FIX TRIAGE REPORT
```

Do not diagnose from memory or screenshot alone.

---

## Step 1 — Active run

```text
<agent_repo>/.debug/<feature>/
<project_dir>/wizard-state.yml
```

Confirm feature, freshness, last command. Stale/missing artifacts → state blocker, do not guess.

---

## Step 2 — Read evidence (flat layout)

```text
last.log → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

Plus when present: llm_*, semantic_*, contract_emit_diff.*, provenance.json, dart-errors.json, capture/*.

---

## Step 3 — Map symptoms to laws

Read before classifying:

```text
.cursor/rules/project-bible.mdc
.cursor/rules/pipeline-contracts.mdc
corpus/families.yaml
corpus/index/<family_id>.yaml   # after family_id is known
AGENTS.md
```

After `family_id` is known, read `corpus/index/<family_id>.yaml` to pick the relevant
`case_id` (prefer same `project`+`feature`, then `OPEN`, then `FIXED` with repair).
Open only the chosen `corpus/cases/<case_id>.yaml` — do not load every case file.

**Reading FIXED cases (same family)** — do not read whole `repair.changed_files`:

```text
1. contract.expected / actual     what broke (law)
2. repair.summary                 if present — mechanism fix recap (2–3 sentences)
3. repair.regression_tests        read test function only — executable spec
4. owner.module + owner.symbol    detector/checkpoint anchor (may ≠ fix site)
5. repair.changed_files           grep symbol from test/summary; narrow read only
```

`owner` often names the law checkpoint; the fix may live in another path under
`repair.changed_files`.

Compiler arrow/law contract: `.cursor/rules/pipeline-contracts.mdc` (self-contained; do not chase `refactor/contracts/` links).

Group by contract/law, not by screen region. For each symptom: evidence path, node id, layer, P0–P3.

For each root cause return:

```yaml
root_cause:
  symptom: ...
  family_id: ...            # from families.yaml mechanism id, never a visual symptom
  pipeline_arrow: ...       # A1 | A1b | A2 | A3 | CP2 | A4 | NONE
  law_id: ...
  stage: ...
  origin: COMPILER | SOURCE | AMBIGUOUS | UNSUPPORTED
  blast_radius: ...
  confidence: high | medium | low
  owner:
    module: ...
    symbol: ...
  contract:
    field: ...
    field_class: fact | intent | proposal | compiler_owned | report_only
    category: preserved | inferred | lossy | illegal
    expected: ...
    actual: ...
  evidence:
    - kind: source_code | test | debug_artifact | log
      path: ...
      summary: ...
  corpus_status: ready_for_record | needs_evidence | unclassified
```

Incorporate **user chat notes** (product observations) into `case.summary` and/or an
evidence item `summary` — never as the sole classifier; still require `family_id` from
`families.yaml`.

Rules: do not invent families; unknown mechanism → `family_id: unclassified` in report
only (**never** write YAML); find the first arrow where the fact changed.

---

## Step 6 — Record OPEN corpus cases (mandatory gate)

Follow **`.cursor/skills/corpus/SKILL.md`** Steps 1–4. **This step is not optional** when `corpus_status: ready_for_record`.

See **CRITICAL — Corpus on disk before handoff** above. Chat `corpus_handoff:` blocks are planning notes only; they **do not** satisfy this step.

### `case.summary` (OPEN only)

```text
- family + law_id in plain language (what invariant failed)
- contract.expected vs actual — one sentence each
- first pipeline arrow where the fact changed
- User observation: …  when product noted something in chat
```

Do **not** put fix recipe, `changed_files`, or test names in `case.summary` — repair-only.

### YAML steps

For each such root cause:

1. Read `corpus/case-template.yaml` and matching row in `corpus/families.yaml`.
2. Create or update `corpus/cases/YYYY-MM-DD-<mechanism-slug>.yaml`.
3. Set each occurrence `status: OPEN` — **never `FIXED`** on diagnose.
4. Fill `case.summary` per rules above.
5. Point `evidence` at repo-relative `.debug/screen/<project>/<feature>/…` paths.
6. Leave `repair` absent or empty; `FIXED` is repair-only.
7. Run `poetry run figma-flutter defects validate` — fix YAML until exit 0 (includes index check).

### Handoff to `/repair` — `repair_summary_draft`

Per queue item with a matching `family_id`, emit **2–3 sentences** (mechanism-level, not
screen patch):

```yaml
repair_summary_draft: >
  What invariant the fix must restore; which compiler layer owns it; how the
  regression test will prove the law holds.
```

`/repair` refines this into `repair.summary` when promoting to `FIXED`. File paths and
test ids still go in `repair.changed_files` / `regression_tests` — summary is the
human/agent-readable “what changed”, not a substitute for proof.

After writing or updating cases, regenerate indexes if validate reports index drift:

```bash
poetry run figma-flutter defects index --write
```

**Do not write YAML when:**

```text
corpus_status: unclassified | needs_evidence
family_id would be invented or UNCLASSIFIED
only a visual symptom with no mechanism
infra/control-panel issue (/debug flow)
```

**One mechanism → one occurrence.** Reuse an existing case file for the same
`family_id` + screen when updating evidence; do not duplicate case ids.

If a case for that mechanism is already `OPEN` with prior repair attempts in
`summary`, reference it — do not duplicate; note whether re-diagnose is needed
before another `/repair` spin.

Report which files were written under `Corpus recorded:` in the triage report.

---

## Step 4 — Repair queue

List every distinct bug class. Do not collapse to one winner.

```text
R1: priority, law, layer, evidence, proposed fix, repair_summary_draft, files allowed/forbidden, tests, depends_on
```

---

## Step 5 — Stop or hand off

**Default (`/diagnose`, triage):** complete Step 6 corpus gate when applicable, emit report, **no compiler code**.

**Incomplete diagnose** = report sent but Step 6 skipped while `ready_for_record` root causes exist.

**Batch repair trigger** (`/repair`, "чиним всё"): hand queue to repair skill. Cases stay `OPEN` until proof; repair promotes to `FIXED`.

---

## Required output

```text
BATCH PRE-FIX TRIAGE REPORT

Feature / run:
Artifact freshness:

Symptoms: (by law)
Evidence:
Repair queue: R1, R2, …
  (each R?: repair_summary_draft when family known)
Execution order:
Blocked / missing evidence:
Corpus recorded:
  repo paths written + defects validate result, or "none — <reason>"
Proceed: DIAGNOSE ONLY | BATCH REPAIR (explicit trigger only)
```

**Diagnose-only:** no compiler code. **Corpus YAML on disk is required** when mechanism is classified — not deferred to chat handoff or `/repair`.
