---
name: diagnose
description: >-
  Diagnosis-only for screen/compiler pipeline: layout, IR, semantic, contract,
  emitter, analyzer, golden. Inspects .debug artifacts, builds BATCH PRE-FIX
  TRIAGE REPORT. Pairs with /repair only. Use for /diagnose on a specific screen.
---

@.claude/prompts/debug-common.md

# Debug Diagnose Skill

Use for failed **generate/wizard/golden** runs on a **specific screen** —
layout, IR, emitter, analyzer, visual mismatch.

**Separate flow (do not mix with debug-fix):**

```text
/diagnose → /repair     screen/compiler
/debug → /fix             control panel / infra — not this skill
```

**Diagnosis-only by default.** Code changes belong to **`/repair`** (`/repair`,
"чиним всё") in the same flow.

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
refactor/AGENT_SYSTEM_PROMPT.md
refactor/PROJECT_MAP.md
corpus/families.yaml
```

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

Rules: read-only; do not write corpus; do not invent families; unknown mechanism → `family_id: unclassified` in output only (never commit `UNCLASSIFIED` cases); find the first arrow where the fact changed.

---

## Step 4 — Repair queue

List every distinct bug class. Do not collapse to one winner.

```text
R1: priority, law, layer, evidence, proposed fix, files allowed/forbidden, tests, depends_on
```

---

## Step 5 — Stop or hand off

**Default (`/diagnose`, triage):** emit report, **stop — no code**.

**Batch repair trigger only** (`/repair`, "чиним всё"): hand queue to repair skill, same session.

---

## Required output

```text
BATCH PRE-FIX TRIAGE REPORT

Feature / run:
Artifact freshness:

Symptoms: (by law)
Evidence:
Repair queue: R1, R2, …
Execution order:
Blocked / missing evidence:
Proceed: DIAGNOSE ONLY | BATCH REPAIR (explicit trigger only)
```

After diagnose-only: **do not code**.
