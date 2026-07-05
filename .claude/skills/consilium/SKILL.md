---
name: consilium
description: Optional fast review for ambiguous or high-risk batch repairs. NOT a mandatory gate per queue item. Use only when evidence conflicts, anti-patching risk is unclear, or user asks for consilium. Default /repair flow skips consilium and runs diagnose → batch fix.
disable-model-invocation: true
---

# Debug Synthesis Skill

Use **only when needed** — not between every repair queue item.

**Skip consilium when:**

```text
user said /repair, "чиним всё", "fix all", or batch repair is default
BATCH PRE-FIX TRIAGE REPORT already lists prioritized R1..Rn
each item has law + layer + evidence + test plan
no contradictory pipeline readings
```

**Use consilium when:**

```text
two reviewers disagree on layer or law
a proposed fix smells like screen-specific patching
report-only and production repair are mixed without split plan
artifacts are stale or diagnosis is incomplete
user explicitly asked for consilium
```

Goal: one clear call for the **whole batch** (or one blocked item), not N micro-approvals.

Do not write code in this skill.

## Corpus (consilium cannot skip)

**corpus handoff: none strong** = defer blocking/oracle only. `/diagnose` and `/repair` still require OPEN case + `defects validate` (`.claude/skills/corpus/SKILL.md`). Fixture pytest alone is not corpus signoff.

---

# Inputs to inspect

Use only real evidence:

```text
.debug artifacts
changed files / diff
tests added or removed
agent summary
task spec
```

Do not trust summaries without checking code or artifacts.

---

# Three lenses

Review the issue through three lenses only.

## 1. Pipeline lens

Question:

```text
Where did the bug first appear?
```

Check:

```text
raw -> processed -> IR -> semantic verdicts -> element contracts -> policy -> emitter -> Dart -> render
```

Output:

```text
first suspected bad layer
evidence
missing evidence
```

## 2. Contract/law lens

Question:

```text
Which contract or law is violated?
```

Check:

```text
contract_kind
subtype
owned nodes
expected law
current violation
```

Output:

```text
target law
whether this is recognition, contract recovery, policy, or emitter
```

## 3. Scope/regression lens

Question:

```text
Is this a durable fix or a local patch?
```

Check for:

```text
screen-specific code
node-id branches
magic padding/coordinates
text/name production heuristics
baseline updates
unrelated files
mixed layers
missing tests
```

Output:

```text
approve / request changes / split / revert
required tests
```

---

# Required output

```text
DEBUG SYNTHESIS

Subject:
Decision:
  APPROVE / REQUEST CHANGES / SPLIT REQUIRED / REVERT REQUIRED / DIAGNOSIS INCOMPLETE

Summary:

Evidence checked:
  - ...

Pipeline finding:
  first bad layer:
  evidence:
  missing evidence:

Contract/law finding:
  contract_kind:
  law:
  violation:
  owner layer:

Scope/regression finding:
  risks:
  shortcuts found:
  tests/proof:

Recommended next action:
  task type:
  allowed files:
  forbidden files:
  tests required:
  acceptance criteria:

Final instruction:
```

---

# Decision rules

```text
APPROVE BATCH
  → implement full repair queue (or listed subset) in one session

REQUEST CHANGES
  → fix diagnosis/queue ordering/tests before coding

SPLIT REQUIRED
  → separate report-only PR from production repair batch

REVERT REQUIRED
  → shortcuts or unapproved production behavior

DIAGNOSIS INCOMPLETE
  → refresh .debug / rerun stage before any repair
```

For batch approval, output:

```text
Approved queue: R1, R2, R3, …
Forbidden: …
Proceed without per-item consilium: yes
```

Use:

```text
APPROVE
```

only if scope matches task, tests prove it, and no shortcuts are present.

Use:

```text
REQUEST CHANGES
```

if direction is good but cleanup is needed.

Use:

```text
SPLIT REQUIRED
```

if report-only work is mixed with production repair.

Use:

```text
REVERT REQUIRED
```

if production behavior changed without approval, baselines hide failure, or shortcuts became production authority.

Use:

```text
DIAGNOSIS INCOMPLETE
```

if artifacts/evidence are missing or the bug is not mapped to a law.

---

# Final rule

Do not average opinions.

Make one clear call:

```text
what is wrong
where it belongs
what to do next
what not to touch
```

---

## Additional resources

- Diagnosis phase: `.cursor/skills/diagnose/SKILL.md`
- Repair phase: `.cursor/skills/repair/SKILL.md`
- Artifact map and forbidden shortcuts: `.cursor/rules/debug-context.mdc`
- Layout laws reference: `docs/projects/26-06-13-codex-hardening/element-layout-laws.md`
