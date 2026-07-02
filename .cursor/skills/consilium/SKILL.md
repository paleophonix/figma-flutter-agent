---
name: consilium
description: >-
  Optional synthesis for ambiguous or high-risk batch repairs. NOT a mandatory
  gate per queue item. Produces an exhaustive plan aimed at ALL current symptoms
  and evidence-backed foreseen failures — systemic laws only, no local patching.
  Use when evidence conflicts, anti-patching risk is unclear, or user asks for
  consilium. Default /repair skips consilium.
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
no anti-patching smell
```

**Use consilium when:**

```text
two reviewers disagree on layer or law
a proposed fix smells like screen-specific patching
report-only and production repair are mixed without split plan
artifacts are stale or diagnosis is incomplete
user explicitly asked for consilium
queue item cannot name a law that generalizes beyond current feature
```

Goal: one clear call for the **whole batch** (or one blocked item), not N micro-approvals.

**Scope of synthesis:** the report and approved queue must aim to resolve **all**
current failures **and** foreseen problems — same root cause, adjacent laws,
downstream propagation, and corpus siblings likely to break next. Do not approve
a plan that fixes only the loudest symptom while leaving mapped or predictable
failures undocumented. Foreseen items still need evidence (artifact, law, layer,
test) — never approve speculative screen patches.

Do not write code in this skill.

## Anti-patching (mandatory)

Every consilium verdict must explicitly audit anti-patching. **REVERT REQUIRED** or **REQUEST CHANGES** if any item fails.

**Forbidden in approved repair plans:**

```text
screen-, feature-, figmaId-, text-value-, asset-filename-, customer-path-, fixture-specific production code
magic coordinates, padding, colors, or anonymous hardcoded tokens for one golden/screenshot
baseline/golden updates to hide failure
production text/name regex heuristics
node-id or dump-path conditional branches in src/
hand-edits to sandbox/demo generated Dart as the fix
mixing unrelated contract kinds in one diff without SPLIT
```

**Required for each queue item R?:**

```text
named law (not "make bank_home look right")
owning compiler layer (parser → emit → capture — pick one primary)
reusable algorithm: must apply to arbitrary Figma trees, not only active .debug/<feature>
regression proof: test/fixture/corpus name + assertion + why it generalizes
files allowed / files forbidden (explicit)
```

**If only a local workaround exists:** mark item **BLOCKED (forbidden shortcut)** — do not APPROVE batch containing it.

---

# Inputs to inspect

Use only real evidence:

```text
<agent_repo>/.debug/screen/<project>/<feature>/  (flat: last.log, raw.json, processed.json, pre_emit.json, screen.dart, …)
<project_dir>/wizard-state.yml
changed files / diff (if repair already started)
tests added, removed, or proposed
agent summary / BATCH PRE-FIX TRIAGE REPORT
prior agent diagnosis in the same thread (your own /diagnose or triage output)
task spec / user scope
```

Do not trust summaries without checking code or artifacts.

## Prior agent analysis (mandatory when present)

When consilium runs in a thread that already contains an agent-produced diagnosis
(`/diagnose`, BATCH ROOT-CAUSE REPORT, BATCH PRE-FIX TRIAGE REPORT, or inline
triage), **you must reconcile it with any user-pasted or third-party analysis**
— do not ignore your own earlier work.

For each prior agent report in scope:

```text
cite it in Source reports (e.g. "agent /diagnose — same thread")
list claims that still hold after re-checking artifacts/code
list claims superseded or wrong (with evidence)
state explicitly whether the prior agent analysis adds NEW evidence vs only confirms
```

**Verdict options for overlap:**

```text
CONFIRMS — same layer, law, queue; no new R? needed
EXTENDS — prior analysis correct but incomplete (add R?, law, or foreseen F?)
CONTRADICTS — prior analysis wrong on layer/law; consilium picks one reading
REDUNDANT — prior analysis adds nothing beyond user/other report; say so in Executive summary
```

If your own prior analysis and the user's report agree on layer, law, and single-item
queue with no new foreseen failures, state **"Prior agent analysis: REDUNDANT / CONFIRMS —
no additional queue items"** instead of restating the same findings at length.

Do not treat consilium as a second independent review that omits what you already
diagnosed in the same conversation unless you explicitly overturn it with evidence.

---

# Three lenses

Review through three lenses. **Every lens must cite artifact paths, node ids, and snippets.**

## 1. Pipeline lens

Question: **Where did the bug first appear?**

Trace (cite evidence at each hop):

```text
raw.json
  -> processed.json
  -> llm_parsed / llm_validated / pre_emit.json
  -> semantic_context / semantic_verdicts / element_contracts
  -> contract_emit_diff.*
  -> provenance.json
  -> plan.dart / screen.dart / screen.bug.dart
  -> figma.png vs flutter_render / capture
  -> last.log (pipeline + flutter render errors)
  -> dart-errors.json
```

Output (per symptom and per queue item):

```text
first bad layer (single primary)
upstream layers ruled out (with evidence)
downstream symptoms explained as propagation vs independent bugs
missing artifacts / blocked stages
recommended rerun command if stale
```

## 2. Contract/law lens

Question: **Which contract or law is violated?**

For each symptom:

```text
contract_kind
subtype
owned node ids / figma ids (evidence only — not fix targets)
expected law (named)
current violation (IR field, Dart snippet, render delta)
responsible layer: recognition | contract recovery | policy | materializer | emitter | style | write | capture
systemic vs fixture-local (justify)
```

Output:

```text
law mapping table: symptom -> law -> layer
items that share one law (may batch in one diff)
items that must stay separate (different laws/layers)
unmapped symptoms (diagnosis gap)
```

## 3. Scope / regression / anti-patching lens

Question: **Is this a durable fix or a local patch?**

Audit each proposed fix in the queue:

```text
[ ] no screen/feature name in production conditionals
[ ] no figmaId / node-id branches
[ ] no text-value / label-string matching in emit
[ ] no asset-filename-specific logic
[ ] no coordinate/padding magic for one fixture
[ ] no golden baseline update to pass
[ ] no production behavior from name/text regex
[ ] law named and documented
[ ] test/fixture proves next screen, not only current feature
[ ] one primary layer per item
[ ] no unrelated drive-by refactors
```

Output:

```text
per-item: PASS anti-patching | FAIL (cite line/snippet) | BLOCKED
batch-level shortcuts found
required tests before APPROVE
split recommendation (report-only vs production)
```

---

# Required output: DEBUG SYNTHESIS (full report)

Produce a **long, evidence-dense** report. Short summaries are insufficient.

```text
================================================================================
DEBUG SYNTHESIS — CONSILIUM REPORT
================================================================================

Meta
----
Subject:              <feature / failure / batch id>
Trigger:              <why consilium ran>
Active feature:
Project dir:
Agent debug root:     <agent_repo>/.debug/<feature>/
Artifact freshness:   <fresh | stale | partial — cite timestamps / last.log>
Source reports:       <BATCH PRE-FIX TRIAGE REPORT path or inline>
Prior agent analysis: <CONFIRMS | EXTENDS | CONTRADICTS | REDUNDANT — what it added or duplicated>
Decision:             APPROVE | REQUEST CHANGES | SPLIT REQUIRED | REVERT REQUIRED | DIAGNOSIS INCOMPLETE
Confidence:           <high | medium | low — why>

Executive summary (3–8 sentences)
-------------------------------
<what is broken, at what layer, whether batch repair is safe, blockers>
<explicit: current vs foreseen coverage — what is fully planned vs deferred>


Coverage statement (mandatory)
------------------------------
Current symptoms addressed:     S?, S?, … (all from register — none omitted)
Foreseen / adjacent failures:   F?, F?, … (evidence-backed predictions)
Intentionally deferred:         … (only with reason + follow-up)
Known gaps / cannot foresee:    … (missing artifacts, out of scope)
Batch completeness:             FULL | PARTIAL (justify)
------------------
Artifacts read (path + freshness + one-line finding):
  - last.log:
  - raw.json:
  - processed.json:
  - pre_emit.json:
  - screen.dart / screen.bug.dart:
  - semantics.json / provenance.json:
  - contract_emit_diff.*:
  - figma.png / flutter_render / capture:
  - dart-errors.json:
  - other:

Artifacts missing (blocked diagnosis):
  - <path> — expected stage — rerun command

User / runtime traces reviewed:
  - <paste or terminal ref>


Symptom register (complete)
---------------------------
For each distinct symptom S?:

  S?:
    user-visible:
    contract_kind:
    law (expected):
  evidence:
      artifact:
      node id:
      snippet:
    priority: P0|P1|P2|P3
    systemic: yes|no (why)
    maps to queue: R?


Foreseen failure register (mandatory)
-------------------------------------
For each predicted failure F? (not yet user-visible but supported by evidence):

  F?:
    prediction:
    trigger / condition:
    related current symptom(s): S?
    shared law or root cause:
    evidence (artifact + snippet — not guesswork):
    if unaddressed:
    maps to queue: R? (preventive) | DEFER (reason) | OUT OF SCOPE (reason)

Rules:
  - include propagation from first bad layer (downstream IR/emit/render)
  - include sibling contract kinds on same screen when artifacts show them
  - include corpus/fixture neighbors when same law is untested
  - do NOT invent F? without evidence; mark uncertainty explicitly


Pipeline synthesis
------------------
First failure layer (global):
Layer-by-layer notes:
  raw:
  processed:
  IR:
  semantic / contract:
  emit / Dart:
  render / capture:

Propagation chain:
  <which downstream symptoms are consequences vs separate bugs>


Contract / law synthesis
------------------------
Law table:
  | id | law | contract_kind | layer | symptoms |

Queue items missing a named law:
Unmapped symptoms:


Repair queue review (per item — mandatory detail)
-------------------------------------------------
Queue must cover **all** S? and all approved F? (current + foreseen). Flag PARTIAL
if any mapped symptom lacks an R? or acceptable DEFER.

For each R? in the proposed queue:

  R?:
    kind:               current | foreseen / preventive
    priority:
    symptom(s): S?
    law:
    layer:
    proposed fix (1–3 sentences):
    evidence (paths + snippets):
    files allowed:
    files forbidden:
    tests required:
      name:
      fixture:
      assertion:
      generalizes because:
    depends_on:
    anti-patching audit:
      status: PASS | FAIL | BLOCKED
      findings:
    risks if merged:
    recommendation: APPROVE item | REWRITE queue | DROP | SPLIT to separate PR


Anti-patching batch verdict
---------------------------
Forbidden shortcuts found (batch-level):
  - <none | list with file/line or plan citation>

Items that must not ship:
Items safe to implement:

Required before any code:
  - <tests to add first, artifacts to refresh, scope narrowings>


Scope / regression
------------------
Tests present / missing:
Unrelated files at risk:
Baseline / golden touch proposed: yes|no (forbidden unless explicit)
Mixed layers in one diff: yes|no → SPLIT?
Report-only work mixed with production: yes|no → SPLIT?


Recommended next action
-----------------------
Task type:           diagnose refresh | rewrite queue | batch repair | single-item repair | stop
Approved queue:      R?, R?, … | none
Deferred / blocked:  R? (reason)
Allowed files (union):
Forbidden files (union):
Tests required (union):
Acceptance criteria (checklist):
  - [ ] …

Final instruction (imperative, one paragraph)
---------------------------------------------
<exactly what the agent should do next; what not to touch>


Proceed without per-item consilium: yes|no
================================================================================
```

---

# Decision rules

```text
APPROVE BATCH
  → every in-scope R? passed anti-patching audit
  → every S? has R? or documented DEFER; foreseen F? with evidence included or deferred with reason
  → implement full queue (or listed subset) in one session

REQUEST CHANGES
  → direction ok but queue/law/tests/ordering incomplete
  → or anti-patching FAIL fixable by rewriting plan (not by patching)

SPLIT REQUIRED
  → report-only vs production mixed
  → unrelated laws/layers in one proposed diff

REVERT REQUIRED
  → shortcuts already in diff
  → baselines updated to hide failure
  → production screen-specific branches landed

DIAGNOSIS INCOMPLETE
  → stale/missing artifacts
  → symptoms not mapped to laws
  → cannot answer "why next screen"
```

Use **APPROVE** only if: scope matches task, every item has law + test + PASS anti-patching, no shortcuts.

For batch approval also output:

```text
Approved queue: R1, R2, …
Blocked: R? (forbidden shortcut)
Forbidden: <files / patterns>
Proceed without per-item consilium: yes
```

---

# Final rule

Do not average opinions. Make one clear call:

```text
what is wrong (all current symptoms)
what will break next if unaddressed (foreseen, evidence-backed)
where it belongs (layer + law)
what to do next (queue covers full current + foreseen scope)
what not to touch
which queue items are safe vs blocked
```

---

## Additional resources

- Diagnosis phase: `.cursor/skills/diagnose/SKILL.md`
- Repair phase: `.cursor/skills/repair/SKILL.md`
- Artifact map and forbidden shortcuts: `.cursor/rules/debug-context.mdc`
- Anti-patching rule: `.cursor/rules/anti-patching.mdc`
- Layout laws reference: `docs/projects/codex-hardening/element-layout-laws.md`
