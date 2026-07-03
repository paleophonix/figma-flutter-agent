# EPIC 1 — Feedback-to-Fix Pipeline

## Goal

Build a safe feedback-to-fix loop where every hard failure becomes a durable diagnostic artifact, a deduplicated failure family, and, after human triage, a regression fixture, issue draft, or patch brief.

The system must learn from failures without allowing uncontrolled self-modifying code.

## Core Rules

```text
Auto-capture everything.
Auto-fix nothing without explicit human promote.
Auto-merge never.
```

## Core Flow

```text
failure
→ failure capsule
→ failure signature
→ failure family / dedupe
→ CI report
→ human triage
→ ignore / duplicate / backlog / promote
→ regression fixture / issue draft / patch brief
→ optional coding-agent draft PR
→ human review
→ merge
```

## MVP Scope

Included in E9 MVP:

* E9.1 Failure Capsule
* E9.2 Failure Signature & Deduplication
* E9.3 Failure Family Store
* E9.4 Human Triage Gate
* E9.5 Manual Promote CLI
* E9.6 Full-context Regression Fixture
* E9.7 Confidence-gated Root Cause Hints
* E9.8 Patch Brief Generator
* E9.9 Guardrails Against Bad Learning

Excluded from E9 MVP:

* Repro minimizer
* Automatic coding-agent invocation from CI
* Automatic issue creation from CI
* Automatic PR creation from CI
* Automatic golden baseline updates
* Automatic threshold weakening
* Silent heuristic insertion
* Auto-merge

---

## E9.1 — Failure Capsule

### Goal

Persist a full diagnostic artifact for every hard pipeline failure.

### Scope

Any hard failure in the generation, validation, emit, golden, runtime geometry, fidelity, classification, accessibility, asset, or conservation pipeline must write a failure capsule.

Capsules are stored under:

```text
.debug/failures/<failure_id>/
```

Required files:

```text
failure.json
command.txt
settings_snapshot.yaml
environment.json
clean_tree.json
screen_ir_raw.json
screen_ir_post_layout.json
screen_ir_post_classify.json
screen_ir_pre_emit_stamped.json
generated_files/
logs/
renders/
```

Optional files:

```text
figma_reference.png
flutter_render.png
diff_heatmap.png
runtime_geometry.json
classification_report.json
fidelity_report.json
provenance.jsonl
pass_decisions.jsonl
flutter_analyze.log
flutter_test.log
```

### `failure.json` shape

```json
{
  "failureId": "ff-20260612-0001",
  "familyId": "fam-runtime-geometry-001",
  "createdAt": "2026-06-12T12:00:00+02:00",
  "stage": "runtime_geometry_gate",
  "failureClass": "node_geometry_mismatch",
  "featureName": "task_management",
  "screenId": "task_management",
  "command": "figma-flutter generate ...",
  "commitSha": "abc123",
  "pipelineProfile": "production",
  "firstBadCheckpoint": "CP2_ir_passes",
  "artifacts": {
    "cleanTree": "clean_tree.json",
    "screenIrPreEmit": "screen_ir_pre_emit_stamped.json",
    "generatedFiles": "generated_files/",
    "logs": "logs/",
    "renders": "renders/"
  },
  "signals": {
    "nodeId": "123:456",
    "expectedRect": [16, 144, 343, 88],
    "actualRect": [16, 172, 343, 88],
    "delta": [0, 28, 0, 0],
    "iou": 0.52
  },
  "policy": {
    "autoIssueAllowed": false,
    "autoPrAllowed": false,
    "autoMergeAllowed": false,
    "manualPromoteRequired": true
  }
}
```

### Acceptance Criteria

* Any hard failure writes a capsule.
* Capsule creation must not hide or downgrade the original failure.
* Capsule creation must not update golden baselines.
* Capsule creation must not weaken thresholds.
* Capsule creation must not call an LLM.
* Missing optional artifacts must not crash capsule creation.
* Capsule must contain enough state to reproduce without Figma API and without LLM whenever possible.

---

## E9.2 — Failure Signature & Deduplication

### Goal

Group repeated failures into stable failure families and prevent tracker/CI noise.

### Scope

Each failure capsule must produce a stable signature.

Signature inputs:

```text
failureClass
stage
firstBadCheckpoint
exception type
normalized stacktrace hash
node id / figma id when available
delta bucket when geometry-related
emit kind when emitter-related
fidelity tier when fidelity-related
suspected subsystem hint when deterministic
```

Example:

```text
runtime_geometry_mismatch|CP2_ir_passes|node=123:456|delta_y_bucket=28
```

### Failure Family

A failure family aggregates occurrences:

```json
{
  "familyId": "fam-runtime-geometry-001",
  "signature": "runtime_geometry_mismatch|CP2_ir_passes|node=123:456|delta_y_bucket=28",
  "status": "new",
  "occurrences": 17,
  "firstSeenCommit": "abc123",
  "lastSeenCommit": "def456",
  "firstSeenAt": "2026-06-12T12:00:00+02:00",
  "lastSeenAt": "2026-06-12T14:30:00+02:00",
  "capsules": [
    "ff-20260612-0001",
    "ff-20260612-0002"
  ]
}
```

### Statuses

```text
new
triaged
promoted_to_issue
ignored
duplicate
known_flaky
needs_more_evidence
fixed
```

### Acceptance Criteria

* Repeated failures do not create new failure families.
* Each new capsule is linked to a family.
* Family occurrence count is updated.
* Family status is human-controlled.
* Deduplication must be deterministic.
* Deduplication must not require LLM.

---

## E9.3 — Failure Family Store

### Goal

Maintain a durable local/CI-readable registry of failure families.

### Scope

Store failure families under one of:

```text
.debug/failures/families.json
```

or:

```text
.debug/failures/families/<family_id>.json
```

The store must support:

```text
list families
inspect family
append occurrence
change status
mark duplicate
link promoted issue
link regression fixture
```

### Acceptance Criteria

* Failure family store survives multiple pipeline runs.
* CI can publish the store as an artifact.
* Local CLI can read the store.
* Store updates are atomic enough to avoid corrupted JSON on interrupted runs.
* Store must not require network access.

---

## E9.4 — Human Triage Gate

### Goal

Ensure that issues, patch briefs, coding-agent calls, and PRs are created only after explicit human decision.

### Rule

```text
Failure Capsule is not an Issue.
Failure Family is not an Issue.
Only a human may promote a Failure Family into tracked work.
```

### Allowed Automatic Actions

CI/system may automatically:

```text
write failure capsule
compute signature
deduplicate into failure family
update occurrence count
publish failure report
suggest severity
suggest subsystem
suggest confidence
```

### Forbidden Automatic Actions

CI/system must not automatically:

```text
create GitHub/GitLab issue
assign owner
set milestone
call LLM
invoke coding agent
create PR
update golden baseline
weaken threshold
bypass conservation checkpoint
downgrade fidelity tier to hide failure
insert heuristic patch
```

### Human Decisions

Human triage decides:

```text
is this a real bug?
is this noise?
is this duplicate?
is this flaky?
is this blocker?
should this become an issue?
should this become a regression fixture?
should a patch brief be generated?
may a coding agent be invoked?
```

### Acceptance Criteria

* No CI path can create issue/PR/LLM call without explicit command.
* Failure family can be marked `ignored`, `duplicate`, `known_flaky`, `needs_more_evidence`, or `promoted_to_issue`.
* Human decision is recorded in the family metadata.
* All promoted actions are auditable.

---

## E9.5 — Manual Promote CLI

### Goal

Provide explicit human-controlled commands for inspecting and promoting failures.

### Commands

```bash
figma-flutter failure list
figma-flutter failure inspect <failure_id_or_family_id>
figma-flutter failure promote <failure_id_or_family_id>
figma-flutter failure brief <failure_id_or_family_id>
figma-flutter failure ignore <failure_id_or_family_id> --reason "<reason>"
figma-flutter failure mark-duplicate <failure_id_or_family_id> <canonical_family_id>
figma-flutter failure mark-flaky <failure_id_or_family_id> --reason "<reason>"
```

### Promote Targets

```bash
figma-flutter failure promote <id> --to fixture
figma-flutter failure promote <id> --to issue-draft
figma-flutter failure promote <id> --to brief
```

### Explicitly Out of MVP

```bash
figma-flutter failure promote <id> --to pr
```

PR creation is backlog, not MVP.

### Acceptance Criteria

* `failure list` shows family id, count, stage, severity, confidence, status.
* `failure inspect` shows capsule/family details and artifact paths.
* `failure promote --to fixture` creates a full-context regression fixture.
* `failure promote --to issue-draft` prints issue body or writes markdown draft, but does not create remote issue automatically.
* `failure brief` creates patch brief only after explicit command.
* Commands never update golden baselines.
* Commands never call coding agent in MVP.

---

## E9.6 — Full-context Regression Fixture

### Goal

Convert a promoted failure into a regression fixture that reproduces the bug without Figma API and without LLM.

### Scope

Create:

```text
tests/fixtures/regressions/<failure_id>/
tests/test_regression_<failure_id>.py
```

Fixture directory includes:

```text
failure.json
clean_tree.json
screen_ir_raw.json
screen_ir_post_layout.json
screen_ir_post_classify.json
screen_ir_pre_emit_stamped.json
settings_snapshot.yaml
generated_files/
expected_failure.json
```

### Full-context Rule

MVP fixtures must preserve the full screen context.

No subtree minimization in MVP.

Reason:

```text
Flutter layout failures often depend on ancestor constraints, sibling interactions,
viewport size, and root shell policy. Naive minimization may remove the actual cause.
```

### Regression Test Types

Supported fixture test modes:

```text
emit_parse
layout_pass
classification
fidelity_stamp
runtime_geometry
golden_capture
conservation_checkpoint
```

### Acceptance Criteria

* Regression fixture runs without Figma API.
* Regression fixture runs without LLM.
* Fixture preserves full ancestor/context graph.
* Fixture reproduces the original failure or asserts the expected invariant.
* Fixture is committed only by human-approved PR.
* Fixture generation must not update golden baselines.
* Fixture generation must not weaken thresholds.

---

## E9.7 — Confidence-gated Root Cause Hints

### Goal

Provide subsystem hints without giving the router authority to direct code changes.

### Rule

Root cause router output is a hint, not a directive.

### Confidence Policy

```text
confidence >= 0.95 → targeted patch brief allowed
confidence < 0.95  → evidence-only brief; human triage required
```

### Output Shape

```json
{
  "suspectedSubsystem": "layout_passes",
  "suspectedFiles": [
    "generator/ir/passes/unstack.py",
    "generator/ir/passes/layout_criteria.py"
  ],
  "confidence": 0.82,
  "action": "human_triage_required",
  "evidence": [
    "first bad checkpoint is CP2_ir_passes",
    "clean tree before pass matches Figma",
    "runtime geometry mismatch appears after unstack"
  ]
}
```

### Router Inputs

Allowed deterministic signals:

```text
failure class
stage
checkpoint
exception type
stacktrace frame paths
provenance records
pass decision records
invariant failure type
runtime geometry delta
fidelity tier source
classification report
```

### Router Restrictions

The router must not:

```text
modify code
modify config
modify thresholds
assign owner
create issue
call coding agent
create PR
```

### Acceptance Criteria

* Router emits confidence and evidence.
* Confidence below `0.95` prevents targeted brief.
* Evidence-only brief is generated when confidence is low.
* Router output never overrides human triage.
* Router does not require LLM for deterministic classifications.
* LLM-based explanation, if later added, must be manual-only.

---

## E9.8 — Patch Brief Generator

### Goal

Generate a strict patch brief for a coding agent after human promote.

### Scope

Patch brief is created by:

```bash
figma-flutter failure brief <failure_id_or_family_id>
```

or:

```bash
figma-flutter failure promote <failure_id_or_family_id> --to brief
```

### Brief Contents

````markdown
# Patch Brief

## Failure

- Failure ID:
- Family ID:
- Stage:
- Failure class:
- Feature:
- First bad checkpoint:

## Repro

```bash
pytest tests/test_regression_<failure_id>.py
```

## Evidence

- Artifact paths
- Relevant invariant failures
- Runtime geometry deltas
- Stacktrace excerpts
- Pass decisions
- Provenance mutations

## Root Cause Hints

- Suspected subsystem:
- Suspected files:
- Confidence:
- Evidence:

## Required Fix

- Preserve pixel fidelity.
- Preserve conservation invariants.
- Add/keep regression test.
- Do not update golden baseline.

## Forbidden Changes

- Do not update golden baseline.
- Do not weaken thresholds.
- Do not bypass conservation checkpoints.
- Do not add name-based heuristic outside semantic registry.
- Do not downgrade fidelity tier to hide the failure.
- Do not delete failing fixture.
- Do not silence the error.
- Do not mutate clean tree without provenance.
- Do not add broad try/except fallback.

## Acceptance

- Regression test passes.
- Existing E0–E5 tests pass.
- No new Dart-in-Python fingerprints.
- No new silent clamps.
- No new semantic classifier false positives.
```
````

### Targeting Policy

If confidence is below `0.95`, brief must say:

```text
Human triage required. Do not edit suspected files solely based on router output.
```

### Acceptance Criteria

* Brief generation is manual only.
* Brief includes forbidden changes.
* Brief includes repro command.
* Brief links to full capsule artifacts.
* Brief never calls coding agent in MVP.
* Brief never creates PR in MVP.

---

## E9.9 — Guardrails Against Bad Learning

### Goal

Prevent the feedback system from becoming a source of overfitting, hidden regressions, and technical debt.

### Hard Prohibitions

The system must never automatically:

```text
merge code
update golden baselines
weaken visual thresholds
weaken geometry thresholds
disable tests
delete failing fixtures
mark failures as fixed without passing tests
insert name-based heuristics
bypass conservation checkpoints
bypass fidelity gates
downgrade native_verified to hide failure without explicit reviewed manifest PR
```

### High-risk Changes

Any PR generated later by an agent must be labelled high-risk if it touches:

```text
golden baselines
thresholds
heuristic registries
classification rules
fidelity manifest
layout pass activation criteria
conservation checkpoints
test skip markers
```

### Acceptance Criteria

* Guardrails are represented in docs and CLI policy.
* Patch brief includes forbidden changes.
* Promote commands refuse unsafe automatic actions.
* Tests cover that CI cannot auto-issue, auto-PR, or auto-merge.
* Any future agent PR path must create draft PR only.

---

## E9 Backlog

### E9.B1 — Constraint-preserving Repro Minimizer

Out of MVP.

Future minimizer may be considered only if it preserves:

```text
ancestor chain
viewport constraints
root shell
relevant siblings
layout parent constraints
theme/config context
failure reproduction after every reduction step
```

Acceptance for future:

```text
minimized fixture must reproduce same failure signature
minimizer must prove failure survives each reduction
original full-context fixture must remain available
```

### E9.B2 — Draft PR Candidate

Out of MVP.

Future flow:

```text
manual promote
→ patch brief
→ explicit coding-agent invocation
→ draft PR
→ CI
→ human review
```

Forbidden future flow:

```text
CI failure
→ automatic coding-agent
→ automatic PR
```

### E9.B3 — Learning Dashboard

Out of MVP.

Possible metrics:

```text
new failure families
deduped occurrences
promoted fixtures
open failure families
fixed failure families
flaky families
top failing subsystem
mean time to triage
mean time to fix
```

### E9.B4 — Remote Issue Creation

Out of MVP.

Future command may be added:

```bash
figma-flutter failure promote <family_id> --to github-issue
```

Requirements:

```text
manual command only
issue body preview before creation
human-selected labels
human-selected milestone
human-selected owner
no auto-create from CI
```

---

## E9 MVP Definition of Done

* Every hard failure writes a full failure capsule.
* Capsule includes command, settings, environment, logs, IR/tree snapshots, generated files, and render artifacts when available.
* Failure signature is deterministic.
* Repeated failures are deduplicated into failure families.
* Failure family store tracks status and occurrence count.
* CI may publish failure reports but cannot create issues.
* Human triage is required before issue, brief, fixture promotion, or agent invocation.
* `failure list` and `failure inspect` work.
* `failure promote --to fixture` creates a full-context regression fixture.
* Regression fixture runs without Figma API and without LLM.
* Root cause router emits confidence and evidence only.
* Confidence below `0.95` blocks targeted patch brief.
* Patch brief generation is manual only.
* Patch brief contains forbidden changes and acceptance tests.
* No repro minimizer in MVP.
* No automatic coding-agent invocation in MVP.
* No automatic issue creation in MVP.
* No automatic PR creation in MVP.
* No auto-merge ever.
* No golden update, threshold weakening, or silent heuristic insertion.

---

## Suggested Issue Structure

```text
EPIC 9 — Feedback-to-Fix Pipeline

Child issues:
  E9.1 Failure Capsule
  E9.2 Failure Signature & Deduplication
  E9.3 Failure Family Store
  E9.4 Human Triage Gate
  E9.5 Manual Promote CLI
  E9.6 Full-context Regression Fixture
  E9.7 Confidence-gated Root Cause Hints
  E9.8 Patch Brief Generator
  E9.9 Guardrails Against Bad Learning

Backlog:
  E9.B1 Constraint-preserving Repro Minimizer
  E9.B2 Draft PR Candidate
  E9.B3 Learning Dashboard
  E9.B4 Remote Issue Creation
```

## Suggested Labels

```text
epic:E9
area:feedback-to-fix
area:failure-capsule
area:regression-fixtures
area:agent-automation
guardrail:no-auto-merge
guardrail:no-auto-llm-ci
guardrail:no-auto-issue
guardrail:no-golden-update
risk:high
status:needs-triage
status:promoted
status:accepted
```

## Merge Strategy

```text
PR 1: E9.1 Failure Capsule only
PR 2: E9.2 + E9.3 Signature/Dedup + Family Store
PR 3: E9.4 + E9.5 Human Triage Gate + CLI list/inspect
PR 4: E9.6 Full-context Regression Fixture
PR 5: E9.7 Root Cause Hints
PR 6: E9.8 Patch Brief Generator
PR 7: E9.9 Guardrails tests/docs
```

Each PR must close exactly one mergeable slice and must not introduce automatic LLM, issue, PR, or merge behavior.
