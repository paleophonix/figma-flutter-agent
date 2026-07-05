---
name: repair
description: >-
  Batch repair after /diagnose: implement the full prioritized queue from
  BATCH PRE-FIX TRIAGE REPORT. Pairs with /diagnose only — screen/compiler
  layout, IR, emitter, golden. Use for /repair, "чиним всё", failed generate
  on a specific screen. MUST follow corpus skill before compiler code.
---

@.claude/prompts/debug-common.md

**Mandatory corpus:** Read and follow `.cursor/skills/corpus/SKILL.md` before any `src/` change. Emit-law pytest ≠ corpus done. Consilium "none strong" defers blocking only.

# Debug Repair Skill

Use after **`/diagnose`** — or start here if the user said `/repair`, "чиним всё",
or pasted a failed generate/wizard run on a **specific screen**.

**Separate flow (do not mix with debug-fix):**

```text
/diagnose → /repair     this skill
/debug → /fix             control panel / infra / imports — not this skill
```

If no fresh queue exists, run **`/diagnose`** first (same session), then repair.
Do not stop for per-item approval unless report-only was requested.

**`/repair` is not success.** Most sessions end with items still `OPEN`.
`FIXED` only when proof is conclusive (see Step 4). While working, status stays `OPEN`.

---

## Repair Goal

Implement all in-scope P0/P1/P2 root causes in one session.

Do not stop after the first green test while known P0/P1/P2 failures remain.
Do not split work artificially into a single-item ritual when the current traces
show multiple connected failures across layers or contract kinds.

It is acceptable to touch multiple layers in one repair session when the evidence
requires it. Keep each edit intentional and explain which symptom it fixes.

---

## Hard Limits

Never do these:

```text
hand-edit generated Dart under sandbox/demo_app/lib to pass
update golden baselines to hide the failure
add node-id, feature-name, customer-path, text-value, or fixture-only production branches
add magic padding/coordinate tweaks that only fit one screenshot
hardcode secrets or read .env in tests
make unrelated refactors while repairing failures
silently ignore a remaining P0/P1 failure
```

Use generated artifacts as evidence, not as files to patch.

## Anti-patching (mandatory)

Forbidden: screen/feature/`figmaId`/text-value/asset-filename/customer-path/fixture-specific production code; magic coordinates/padding/colors; baseline updates to hide failure; production text/name regex heuristics.

Required: named law + owning compiler layer; reusable fix for any Figma tree; regression proof per queue item.

If only a local workaround exists: stop — report forbidden shortcut, do not implement.

## Anti-loop (mandatory)

Agents often retry the same wrong fix many times. **Do not spin.**

Before coding on queue item `R?`:

Follow **`.cursor/skills/corpus/SKILL.md`** Step 3 (lookup + anti-loop) first.

```text
1. Resolve family_id → read corpus/index/<family_id>.yaml (not a glob of corpus/cases/).
2. Open the matching case row (same project+feature, status OPEN) for prior attempts.
3. If the case documents ≥2 failed repair attempts without a new /diagnose pass
   and fresh .debug artifacts → STOP that item; report blocked; ask for re-diagnose
   or user direction. Do not attempt R? again in the same pattern.
4. One mechanism → one case file. Update in place; never fork a new YAML per retry.
```

During repair:

```text
- Status stays OPEN until proof is conclusive — including while coding.
- After a failed attempt → still OPEN; append one line to case.summary:
  "Repair attempt N (YYYY-MM-DD): <what was tried> → <why it failed>".
- Do not mark FIXED because pytest passed on an unrelated file or a narrower test
  that does not prove the original law violation is gone.
```

**Max 2 implementation attempts per queue item per session** unless new evidence
appears (new artifact, revised root cause from diagnose, or user explicitly says
"try again with X").

If the user only says `/repair` again on the same known failure with no new
diagnose: refresh the queue from corpus + latest `.debug`, do not blindly re-apply
the previous patch.

---

## Workflow

### Step 0 — Build Or Refresh The Queue

If missing, read `.debug/<feature>/` and pasted traces per diagnose, then produce
a concise queue:

```text
R1 [P0]: symptom -> root cause -> layer(s) -> files -> proof
R2 [P1]: ...
R3 [P2]: ...
```

Sort P0 -> P1 -> P2. Respect real dependencies, for example runtime crash before
pixel polish hidden by the crash.

### Step 1 — Add Or Identify Proof

For each root cause, use the fastest meaningful proof:

```text
unit test
fixture/corpus test
contract-vs-emit assertion
analyzer/capture/runtime smoke
golden/visual test when the bug is visual and capture is available
```

Add tests before or alongside the fix when practical. For urgent P0 runtime
crashes, a focused reproducer plus analyzer/runtime smoke is acceptable; add a
regression test before final report unless impossible.

### Step 2 — Implement The Fixes

Fix the lowest correct layer for each root cause. Multiple root causes may be
fixed in one pass when they are connected by the same trace or artifact bundle.

Allowed examples:

```text
parser classification fix + emitter guard + fixture test
IR validation guard + materializer fallback + analyzer test
asset extraction fix + capture smoke + visual assertion
```

Keep changes surgical:

```text
touch only files needed for the queue
prefer existing helpers and repo patterns
avoid speculative abstractions
avoid unrelated cleanup
```

### Step 3 — Verify Continuously

After meaningful groups of fixes, run the smallest relevant tests. At the end,
run the union of touched-module tests and any feature-specific smoke needed to
show the original failure is gone.

Do not run full signoff unless the user asked or the change is broad enough to
justify it.

**Regen and visual verification are user-owned by default.** Do not run full
`figma-flutter generate`, `dart analyze` on `sandbox/*`, hot-restart checks, or
manual Figma/screenshot comparison unless the user explicitly asks. Deliver code
+ targeted `pytest` proof + `BATCH REPAIR REPORT`; the user regens and
validates on device.

If the user says they will regen/sverka themselves, note it in the report under
`Verification` (agent: unit tests only; user: regen + visual).

If a test failure is outside the touched area, report it clearly. If it blocks
the current repair, include it in the queue and fix it when causally connected.

### Step 4 — Corpus: OPEN or FIXED (binary)

Follow **`.cursor/skills/corpus/SKILL.md`** Steps 3–4 for every compiler-law queue item with a matching case.

```text
OPEN   — not proven fixed
FIXED  — regression proof + repair block + defects validate
WONT_FIX | DEFERRED_BY_POLICY — rare; explicit only
```

Then: `status: FIXED`, fill `repair.*` when proof is conclusive (see corpus skill).

### Step 5 — Continue Until Done Or Blocked

Continue through all P0/P1/P2 items. Stop only when:

```text
all in-scope failures are fixed and verified
required artifacts/secrets/tools are unavailable
the remaining fix would require an explicitly forbidden shortcut
the user interrupts or narrows scope
```

P3 items may be fixed in the same session when cheap and safe, but do not let
them delay P0/P1/P2.

---

## Required Output

After repair:

```text
BATCH REPAIR REPORT

Feature / run:
Queue source:

Fixed:
  R1 [P0]: symptom -> change -> proof result
  R2 [P1]: ...

Corpus status (per mechanism):
  R1: OPEN | FIXED | WONT_FIX — path + one-line reason

Still blocked:
  R?: reason / missing artifact / command needed

Verification:
  commands run and result
  agent: targeted pytest / analyzer smoke on touched modules
  corpus: only items with conclusive proof promoted to FIXED + `defects validate`
  items attempted but unproven: OPEN + repair attempt noted in case.summary
  user (default): full generate, sandbox regen, dart analyze, Figma/screenshot compare — only if user did not take ownership

Scope control:
  generated Dart not hand-edited
  baselines not updated to hide failures
  no screen-specific production branches

Remaining:
  P3 or out-of-scope items

Rollback:
  files/commit to revert
```

Keep the final answer concise, but include enough detail that the user can see
which original traces are fixed.
