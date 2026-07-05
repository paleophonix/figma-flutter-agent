---
name: diagnose
description: >-
  Diagnosis-only for screen/compiler pipeline: layout, IR, semantic, contract,
  emitter, analyzer, golden. Inspects .debug artifacts, builds BATCH PRE-FIX
  TRIAGE REPORT. Pairs with /repair only. Use for /diagnose on a specific screen.
  MUST follow corpus skill for all case YAML.
disable-model-invocation: false
---

@.claude/prompts/debug-common.md

**Mandatory corpus:** Read and follow `.claude/skills/corpus/SKILL.md` before finalizing the report.

# Debug Diagnosis Skill

Use for failed **generate/wizard/golden** runs on a **specific screen**.

**Separate flow (do not mix with debug-fix):**

```text
/diagnose → /repair     this skill
/debug → /fix             control plane / infra — not this skill
```

Use this skill when investigating any:

```text
pipeline bug
layout bug
IR bug
semantic bug
contract bug
emitter bug
analyzer failure
golden/fidelity failure
visual mismatch
```

This skill is **diagnosis-only** when invoked as `/diagnose` without fix intent.

Do not change code in diagnose-only mode.
Do not edit generated Dart.
Do not update baselines.
Do not apply fixes — unless the user triggered **batch repair** (`/repair`, "чиним всё"); then hand off the queue to the repair skill in the same session.

## Anti-patching (mandatory)

Forbidden: screen/feature/`figmaId`/text-value/asset-filename/customer-path/fixture-specific production code; magic coordinates/padding/colors; baseline updates to hide failure; production text/name regex heuristics.

Required: named law + owning compiler layer; reusable fix for any Figma tree; regression proof per queue item.

If only a local workaround exists: stop — report forbidden shortcut, do not implement or queue it.

The required output is a **BATCH PRE-FIX TRIAGE REPORT**.

---

# Diagnosis goal

Convert symptoms into a law-level diagnosis:

```text
.debug artifacts
  -> symptom
  -> contract_kind
  -> expected law
  -> current violation
  -> responsible pipeline layer
  -> regression proof proposal
  -> approved fix scope
```

Do not diagnose by memory.
Do not diagnose by looking only at the screenshot.
Do not diagnose by guessing which file "probably" caused the issue.

---

# Step 1 — Identify active run

Open:

```text
<project_dir>/.debug/
```

Usually:

```text
sandbox/limbo/.debug/
```

Identify:

```text
active feature
project dir
last run timestamp
freshness of artifacts
command if visible
whether generate/analyze/capture completed
```

Use:

```text
wizard-state.yml
logs/last.log
file timestamps
CLI args if available
```

If artifacts are stale or missing, state this and request/re-run the correct stage. Do not continue as if stale artifacts are current.

---

# Step 2 — Read artifacts in order

Default order:

```text
1. logs/last.log
2. processed/<feature>_layout.json vs raw/<feature>_layout.json
3. ir/<feature>_llm_parsed.json
4. ir/<feature>_llm_validated.json
5. ir/<feature>_pre_emit.json
6. ir/<feature>_semantic_context.json, if present
7. ir/<feature>_semantic_verdicts.json, if present
8. ir/<feature>_element_contracts.json, if present
9. ir/<feature>_contract_emit_diff.json/md, if present
10. provenance/<feature>.json
11. semantics/<feature>.json
12. dart/<feature>_plan.dart
13. dart/<feature>_screen.dart
14. dart.bug/<feature>_screen.dart, if present
15. reference/figma/<feature>_figma.png/json
16. renders/ or capture/, if present
17. reports/*
18. sync/snapshot.json
```

You may reorder only if evidence requires it. If you reorder, say why.

---

# Step 3 — Collect evidence

Every diagnosis must cite concrete evidence:

```text
artifact path
node id
contract id if available
IR field
Dart snippet
reference image/capture evidence
analyzer diagnostic
timestamp/freshness
```

Do not say "probably" without evidence.

If a required artifact is missing, say:

```text
which artifact is missing
which pipeline stage should have produced it
what command/stage should be rerun
what diagnosis is blocked by its absence
```

---

# Step 4 — Classify symptoms by contract/law

## Compiler pipeline (Program 00 / 01)

Read before classifying compiler/IR failures:

```text
.claude/prompts/project-bible-lite.md
.claude/prompts/pipeline-contracts.md
corpus/families.yaml
corpus/index/<family_id>.yaml   # after family_id is known
AGENTS.md
```

After `family_id` is known, read `corpus/index/<family_id>.yaml` to pick the relevant
`case_id` (prefer same `project`+`feature`, then `OPEN`, then `FIXED` with repair).
Open only the chosen `corpus/cases/<case_id>.yaml` — do not load every case file.

@.claude/prompts/pipeline-contracts.md

For each **compiler** root cause (not legacy element-contract rows below), also emit:

```yaml
root_cause:
  symptom: ...
  family_id: ...            # mechanism id from families.yaml — never a visual symptom
  pipeline_arrow: A1 | A1b | A2 | A3 | CP2 | A4 | NONE
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

Rules: do not invent families; unknown mechanism → `unclassified` in report only; find the
**first arrow** where the fact changed.

Incorporate **user chat notes** into the triage report and into the **corpus handoff**
block below (for Cursor to apply) — do not write `corpus/` files from this skill.

---

# Step 8 — Corpus handoff (Cursor-owned writes)

**Do not** create, update, or index `corpus/` YAML from `.claude/` diagnose.

When `corpus_status: ready_for_record` and confidence is `high` or `medium`, emit a
**handoff block** in the triage report so a **Cursor** agent can write the case:

```yaml
corpus_handoff:
  action: create | update          # if matching OPEN case exists in index
  case_id: YYYY-MM-DD-<mechanism-slug>   # proposed; Cursor confirms uniqueness
  family_id: ...
  project: ...
  feature: ...
  status: OPEN                     # diagnose never proposes FIXED
  summary: ...                     # include user chat notes
  evidence:
    - kind: debug_artifact
      path: .debug/screen/<project>/<feature>/...
      summary: ...
```

Skip handoff when `unclassified`, `needs_evidence`, infra-only, or symptom-only.

List proposed handoffs under `Corpus handoff (Cursor):` in the report — paths **not**
written yet. **Diagnose-only still means no compiler code and no corpus file I/O.**

---

## Element contracts (legacy semantic corpus)

Do not group by screen.

Bad:

```text
Fix all 10 Feedback screen issues.
```

Good:

```text
This screen has:
  3 violations of text_input laws
  2 violations of chip state laws
  1 navigation/system_chrome issue
  4 visual polish issues without contract coverage
```

For every symptom, map:

```text
contract_kind
subtype
expected law
current violation
responsible pipeline layer
systemic vs fixture-local
```

Common mappings:

```text
textbox hint/value not vertically centered
  -> contract_kind: text_input
  -> law: single_line_input_vertical_center

textarea hint vertically centered incorrectly
  -> contract_kind: textarea / multiline_text_input
  -> law: multiline_input_top_align

label becomes field value
  -> contract_kind: text_input
  -> law: label_outside_control / value_as_field_content

placeholder emitted as sibling Text
  -> contract_kind: text_input
  -> law: placeholder_as_hint

chip selected state lost
  -> contract_kind: choice_chip_group / choice_chip
  -> law: chip_selected_state_preserved

rating value lost
  -> contract_kind: rating_input
  -> law: rating_value_from_component_variant_or_filled_options

button looks right but has no action role
  -> contract_kind: button
  -> law: a11y_role_button / button_label_centered

nav/system chrome pollutes layout
  -> contract_kind: system_chrome / nav_bar
  -> law: system_chrome_safe_area_respected / navigation_docked_position_preserved
```

---

# Step 5 — Identify responsible layer

Use one primary layer:

```text
raw fetch
parser
clean tree
semantic context
semantic verdict
element contract recovery
contract recipe registry
contract-vs-emit diff
policy gate
IR validation
materializer
emitter
style
write
capture/golden
test fixture
```

Do not blame "the compiler" generically.

Examples:

```text
semantic_verdicts identify textarea but element_contracts missing boundary
  -> layer: element contract recovery

element_contract exists but current Dart ignores law
  -> layer: policy/materializer/emitter wiring

Dart has TextField but no textAlignVertical.center
  -> layer: emitter law

raw has correct geometry but processed loses node
  -> layer: parser / clean tree

processed has correct node but IR omits it
  -> layer: IR construction / validation

analyzer fails on generated syntax
  -> layer: template/emitter
```

---

# Step 6 — Build the full repair queue (do not defer by default)

List **every** distinct bug class found in Step 4–5. Do not pick one winner and hide the rest.

Rank each item:

```text
P0 — runtime crash / analyze hard-fail / generation abort
P1 — major missing or broken UI (wrong widget, empty subtree, nav missing)
P2 — fidelity / alignment / polish with layout still stable
P3 — warnings-only / cosmetic / advisory pixel diff
```

For **each** queue item record:

```text
id:           R1, R2, …
priority:
contract_kind:
subtype:
law:
layer:
evidence:     path + node id + snippet
proposed fix: smallest law-level change
files:        allowed / forbidden
tests:        name + fixture + assertion
depends_on:   earlier queue ids, or none
```

**Default:** the repair queue is **approved as a batch** when the user invoked `/repair`, said "чиним всё", "fix all", "fix everything", or is continuing from a failed wizard/generate run. Do **not** stop after R1 and ask for another consilium.

**Single-item mode** only when the user explicitly scopes one law (e.g. "only S1", "just the Row stretch fix"). Then repair only that id; still list the rest in `Deferred (out of user scope)`.

**Consilium** is optional — use only when evidence is contradictory or a queue item would violate anti-patching. It is **not** a mandatory gate between queue items.

---

# Step 7 — Propose regression proof (per queue item)

Every proposed fix must have proof:

```text
unit test for law
fixture/corpus test
contract-vs-emit diff assertion
golden/visual test if appropriate
```

Limbo `.debug` is observation only. It is not regression proof.

For each **queue item**, propose:

```text
test name
fixture
assertion
why it generalizes to future screens
```

---

# Required output: BATCH PRE-FIX TRIAGE REPORT

Produce this report. Then:

- **Batch repair default** (`/repair`, "чиним всё", failed run): proceed to implement the full queue (P0 → P1 → P2) in the same session without per-item approval.
- **Diagnose-only** (`/diagnose` with no fix intent): stop after the report.

```text
BATCH PRE-FIX TRIAGE REPORT

Active feature:
Active project dir:
Artifact freshness:
Last command/run evidence:

Symptoms:
  grouped by contract_kind/law, not only by visual location

Evidence:
  paths + node ids + snippets

Repair queue (all items — do not collapse to one):
  R1:
    priority: P0|P1|P2|P3
    contract_kind:
    subtype:
    law:
    layer:
    evidence:
    proposed fix:
    files allowed:
    files forbidden:
    tests:
    depends_on:
  R2:
    …

Recommended execution order:
  R?, R?, …

Out of scope (only if user narrowed or blocked by missing artifacts):
  …

Diagnosis summary:
  systemic vs fixture-local per item

Corpus handoff (Cursor):
  proposed case_id(s) or none — reason

Regression risk:
Rollback plan:

Proceed:
  BATCH REPAIR (default) | DIAGNOSE ONLY | SINGLE ITEM (user-scoped)
```

After a **diagnose-only** report, do not change compiler code until repair. Corpus YAML
writes are **Cursor-owned** — hand off Step 8 blocks when `ready_for_record`. After a
**batch repair** trigger, do not wait for a separate consilium per queue item.
