---
name: repair
description: >-
  Batch repair after /diagnose: implement the full prioritized queue from
  BATCH PRE-FIX TRIAGE REPORT. Pairs with /diagnose only — screen/compiler
  layout, IR, emitter, golden. Use for /repair, "чиним всё", failed generate
  on a specific screen.
disable-model-invocation: false
---

@.claude/prompts/debug-common.md

# Debug Repair Skill

Use after **`/diagnose`** — or start here if the user said `/repair`, "чиним всё",
or pasted a failed generate/wizard run on a **specific screen**.

**Separate flow (do not mix with debug-fix):**

```text
/diagnose → /repair     this skill
/debug → /fix             control plane / infra — not this skill
```

## Entry modes

```text
BATCH (default)
  → diagnose if no fresh queue exists
  → implement every queue item P0 → P1 → P2 in one session
  → one BATCH REPAIR REPORT at the end

SINGLE ITEM
  → user scoped one law/id (e.g. "only S1")
  → implement only that item; list others as deferred

INLINE
  → user pasted an approved queue or consilium batch approval
  → implement the listed ids without re-diagnosing
```

If no triage exists and artifacts are stale, run diagnosis first (read `.debug`, build queue), then repair — **same session**, no stop between them.

Do not require a separate consilium approval per queue item.

---

# Repair goal

Implement **all items in the repair queue** (unless user narrowed scope).

Each item must still be one transferable law-level fix — no screen-specific patching.

## Anti-patching (mandatory)

Forbidden: screen/feature/`figmaId`/text-value/asset-filename/customer-path/fixture-specific production code; magic coordinates/padding/colors; baseline updates to hide failure; production text/name regex heuristics.

Required: named law + owning compiler layer; reusable fix for any Figma tree; regression proof per queue item.

If only a local workaround exists: stop — report forbidden shortcut, do not implement.

Do not stop after the first green test if P0/P1 items remain.

---

# Scope lock (per queue item)

Before each item `R?`, restate briefly:

```text
R?:
  contract_kind / law / layer
  files allowed / forbidden
  tests
  expected behavior change
```

If an item needs forbidden files or a different layer than diagnosed, **skip that item**, document why, continue the queue — do not abort the whole batch unless P0 is blocked.

---

# Batch repair = many laws, one session

A batch may implement **multiple** queue items when each has:

```text
its own named law
its own regression test (or existing test)
its own minimal diff
no anti-patching violation
```

**Do** combine in one session:

```text
P0 runtime crash (emitter) + P1 empty IR children (materializer) + P1 nav stub (emitter)
```

**Do not** combine in one *diff* without diagnosis:

```text
unrelated drive-by refactors
baseline updates to hide failures
screen-specific node-id branches
one magic padding tweak with no law
```

Single-item mode (user-scoped) still applies **one law per item** — just only one item is in scope.

---

# Repair classes

Use the approved repair class only.

## A. Report-only/schema repair

Allowed:

```text
add/adjust report-only models
add/adjust debug artifact writer
add/adjust serializer
add tests
```

Forbidden:

```text
changing emit
changing parser production behavior
changing report_only
```

## B. Element contract recovery repair

Allowed:

```text
recover boundary/ownership/state into elementContracts
add fixture tests
improve report-only contract output
```

Forbidden:

```text
applying contracts to emit
inventing geometry/text
production text/name heuristics
```

## C. Contract recipe registry repair

Allowed:

```text
add/adjust ContractEmitRecipe
add/adjust law/effect constants
add validation helpers
add tests/docs
```

Forbidden:

```text
emitting Dart from recipes
wiring recipes into production emit
```

## D. Contract-vs-emit diff repair

Allowed:

```text
compare contracts/recipes against generated Dart
add report-only diagnostics
add fake-Dart tests
```

Forbidden:

```text
changing generated Dart
making diff findings block normal generation unless explicitly approved
```

## E. Policy gate repair

Allowed:

```text
add policy decision model
gate one approved effect
add tests for allow/deny
```

Forbidden:

```text
broad rollout
high-risk effects without explicit approval
direct semanticVerdict -> emit
```

## F. Emitter law repair

Allowed:

```text
implement the approved deterministic law
touch only approved emitter/style/template files
add targeted tests
preserve ungated behavior unless approved
```

Forbidden:

```text
fixture-specific padding/coordinates
node-id-specific branches
new text/name production heuristics
unrelated contract kinds
baseline updates
```

## G. Legacy heuristic removal repair

Allowed:

```text
remove or demote one approved legacy shortcut
replace with contract/policy path
add corpus tests
```

Forbidden:

```text
removing heuristics without replacement proof
broad heuristic purge
```

---

# Required repair workflow

## Step 0 — Obtain or refresh the repair queue

If missing: read `.debug/<feature>/` per diagnose skill and emit `BATCH PRE-FIX TRIAGE REPORT`.

Sort: P0 → P1 → P2. Respect `depends_on` (e.g. layout crash before pixel polish).

## Step 1 — For each queue item: failing proof first

Before implementation, ensure there is a failing or meaningful proof:

```text
unit test
fixture/corpus test
contract-vs-emit diff assertion
golden/visual test if approved
```

If no proof exists, add the test first.

Do not rely on limbo `.debug` as the only proof.

## Step 2 — Implement minimal change for this item

Implement the smallest change that satisfies the approved law.

Rules:

```text
no unrelated cleanup
no broad refactor
no opportunistic fixes
no baseline update
no parser behavior change unless approved
no repair/preview/vector side quest
```

## Step 3 — Run tests for this item + touched modules

After **each** item: run its proof test(s) plus the smallest surrounding set for touched `src/` paths.

After **all** items (or end of session): run the union of touched-module tests once.

Do **not** run full `signoff` / `pytest -q -m "not live_figma"` unless the user asks.

If a failure is **outside** touched modules, stop and report — do not silent broadening.

## Step 4 — Verify item before moving to next

```text
before / after for this law
test results
changed files
```

## Step 5 — Next queue item

Repeat Steps 1–4 until the queue is done or blocked.

## Step 6 — Confirm batch non-targets

Explicitly state:

```text
No baseline updates.
No repair bot changes.
No preview/oracle changes.
No vector degradation changes.
No production text/name heuristics added.
No unrelated contract kinds changed.
No screen-specific branches added.
```

---

# Required output: BATCH REPAIR REPORT

After the queue (or blocked stop), produce:

```text
BATCH REPAIR REPORT

Feature / run:
Queue source: BATCH PRE-FIX TRIAGE REPORT | inline | user-scoped

Completed:
  R1: law — files — tests — pass/fail
  R2: …

Skipped / blocked:
  R?: reason

Per-item detail:
  [same fields as former REPAIR REPORT for each completed R?]

Before/after (screen-level):
  before:
  after:

Scope control:
  unchanged areas:
  forbidden shortcuts avoided:

Remaining:
  P3 / out-of-scope / needs regen:

Rollback:
  per-item or single revert commit
```

---

# Rejection conditions

Reject or stop the repair if any of these happen:

```text
fix depends on one screen/node id
fix uses magic coordinate/padding for a fixture
fix adds production text/name regex heuristic
fix updates baseline to hide failure
fix touches repair bot without approval
fix touches preview/oracle without approval
fix changes vector behavior without approval
fix broadens to another contract_kind/law
fix has no regression test/proof
fix cannot explain why it applies to the next screen
```

---

# Final repair invariant (per completed item)

Each completed queue item must answer:

```text
Which named law was implemented?
Which test proves it?
Why will it apply to the next screen?
```

For compiler-law fixes (Program 00/01): create or update a case under `corpus/cases/` and run `poetry run figma-flutter defects validate` (exit 0).

The batch is done when **all in-scope P0/P1 items** are completed or explicitly blocked with evidence.

---
