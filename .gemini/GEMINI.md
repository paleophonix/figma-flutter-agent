````markdown
---
description: Project Bible for the Figma → Flutter Compiler. Mandatory architectural rules for coding agents.
alwaysApply: true
---

# 🧭 Project Bible — Figma → Flutter Compiler

This repository is not a demo generator.

This repository is a **general-purpose, production-grade compiler** from arbitrary Figma layout trees to production Flutter UI.

Every module must be designed for unknown future customer designs — not for the current golden, not for one login screen, not for one `figmaId`, not for one pretty demo frame.

> **North Star**
>
> Build a deterministic Figma → Flutter compiler with measurable pixel fidelity, reusable semantic upgrades, and a growing corpus that proves real-world robustness.

---

# 1. 🌌 Core Philosophy

## 1.1. Pixel fidelity is law. Semantic upgrade is optimization.

A semantic `kind` is only an **annotation** until proven.

Native semantic Flutter output may be emitted only when all gates allow it:

```text
semantic native emit
  ⇔ report_only=false
  AND fidelityTier allows native
  AND verification manifest allows the kind
  AND corpus/oracle evidence is green
````

If semantic beauty conflicts with visual truth:

```text
PIXEL FIDELITY WINS.
```

The system may become more semantic only after it proves that the visual result remains safe.

## 1.2. We do not optimize for clever guesses

The compiler must not become a pile of tricks that pass today’s fixture.

We optimize for:

```text
verified transformations
named invariants
explicit policies
corpus evidence
deterministic recovery
```

Not for:

```text
screen-specific cleverness
golden-only offsets
one-off regex repairs
text-value guesses
"works on my login screen"
```

## 1.3. The system may be incomplete, but not secretly specific

It is acceptable to fail loudly.

It is acceptable to downgrade fidelity.

It is acceptable to emit a geometric fallback.

It is **not** acceptable to smuggle in a local patch and pretend the compiler became better.

## 1.4. Ask the code, not the snapshot

Docs, memory, prior reviews, and your own earlier conclusions are **hypotheses, not facts**. In this repo they go stale within a single turn — a doc said "dynamic golden diff" while the code already stamped a static manifest; a memory cited a `file:line` that had moved.

```text
before asserting a file / function / line / behavior:
  grep or read the CURRENT code
treat docs / memory / status lines as leads to verify, never as truth
```

`ASK THE CODE` (see Final Oath) is literal: verify against live source before you claim, fix, or report. A confident claim from a stale source is worse than "I don't know yet". (ノ¬‿¬)ノ

---

# 2. 🚨 Prime Enforcement: Anti-Patching Law

## 2.1. This law is not advisory

This law is not a style preference.

This law is not negotiable.

Any attempt to smuggle a local workaround into the compiler is a **CRITICAL SYSTEM VIOLATION**.

Local patches contaminate the compiler.

```text
LOCAL PATCH DETECTED
→ compiler veto
→ reconcile failure
→ generated output rejected
→ failure capsule emitted
→ agent reasoning context considered unsafe
→ halt: do not ship this output, surface the violation
```

Do not try to “just make the test green”.

Do not try to “temporarily patch this one case”.

Do not try to hide a screen-specific fix behind a helper.

(ಠ_ಠ) 🔌☠️🔥

## 2.2. Absolutely forbidden

Never introduce code that depends on:

* a specific screen name;
* a specific feature name;
* a specific `figmaId`;
* a specific marketing copy or text value like `"LOG IN"`;
* a specific customer project path;
* a specific golden file;
* a specific asset filename;
* a hardcoded coordinate that only fixes the current screen;
* a regex/string replacement that repairs one emitted Dart shape;
* a conditional branch that exists only because one fixture failed.

Forbidden examples:

```text
if screen_id == "login_version_1": adjust padding
if figmaId == "3:5133": downgrade it
if text == "Continue with Google": emit social button
if file == "input_field_widget.dart": keep it
if golden fails by 6px: subtract 6px
```

No.

That is not compiler engineering.

That is sabotage wearing a green checkmark.

## 2.3. Required replacement mindset

Every fix must be a reusable compiler improvement:

```text
one failure
  → identify failure family
  → write generic fixture
  → fix the correct compiler layer
  → preserve invariants
  → prove no regression on corpus
```

A fix is acceptable only if it can plausibly handle:

```text
the current screen
+ another similar screen
+ a dirty real-world screen
+ a future random Figma tree
```

---

# 3. ⚖️ Heuristic Law

## 3.1. Long-term goal

The long-term goal is:

```text
eliminate hidden, unverified, screen-specific heuristics
```

This does **not** mean “no rules”.

A compiler needs rules.

It means:

```text
No heuristic may directly affect emitted code
unless it is explicit, typed, logged, tested, gated, and reversible.
```

## 3.2. Four allowed knowledge categories

### 1. Facts

Facts come from Figma, IR, assets, or Dart graph reality.

Examples:

```text
node id
node type
bounds
fills
text content
children
paint order
auto-layout metadata
planned file paths
imports
asset references
```

Facts are read, normalized, validated, and preserved.

They are not guessed.

**A fact derived from a heuristic is not a fact.** `node.type` is structural and trustworthy for layout types (`ROW`, `STACK`, `COLUMN`, `GRID`…), but for **leaf semantic types** (`BUTTON`, `INPUT`, `CARD`) it is assigned by `infer_leaf_type` from the **layer name** — a guess wearing a fact's passport. Any field derived from name/text:

```text
carries provenance marker `derived_from_name` (legacySemanticType)
must NOT serve as tier-1 classifier evidence
is downgraded before semantic scoring
  (laundered leaf type → CONTAINER, see type_trust.semantic_signal_type)
```

If you cannot prove a "fact" came from Figma geometry/structure rather than a layer name, treat it as a classifier signal, not truth. This is the exact class that slips past every other rule — name-matching laundered through `node.type`. (ಠ_ಠ)

**A missing or malformed fact is not identity.**

```text
absent absoluteRenderBounds → explicit fallback with provenance, not silent zero
malformed relativeTransform → typed ParseError, not silent identity matrix
missing fill/asset → named deviation, not invented default
```

### 2. Invariants

Invariants are hard laws of the compiler.

Examples:

```text
node multiset must not silently change
style/type facts must not silently mutate
consumer import must resolve to an existing planned file
native emit requires verified fidelity tier
report_only forbids semantic output mutation
blocking corpus failure blocks release
```

Invariants are not heuristics.

They are safety rails.

**Know which rails are real.** Some invariants are **machine-enforced** (hard-fail in code): node multiset, stack paint order, graph sync, type truth — a violation crashes the pipeline. Others are still **self-enforced by you** (declared but not yet checked): per-field `mutates` contracts on passes — the manager records only coarse `children_count`, so a pass that secretly mutates `style` will **not** be caught until the contract enforcer lands. Do not delegate to a gate that does not exist yet — if an invariant is self-enforced, you verify it by hand.

### 3. Classifiers

Classifiers may say:

```text
this is a button candidate
this is an input candidate
this is a card candidate
```

But classifier output is only:

```text
candidate + confidence + evidence + provenance
```

A classifier does **not** get to mutate geometry, children, clean-tree type, or production Dart by itself.

### 4. Policies

Policies are explicit product/compiler choices.

Examples:

```text
report_only=true
strict_fidelity=true
semantic_only skips pixel gate
advisory does not block release
strict_pixel_blocking blocks release
```

Policies must be named, visible, and testable.

---

# 4. 🧱 Master Invariant

Every compiler stage must do exactly one of these:

1. **Preserve a Figma fact.**
2. **Create a named deviation with provenance.**
3. **Downgrade to a safer fidelity tier.**

Anything else is a bug.

```text
silent mutation = bug
silent deletion = bug
silent fallback = bug
silent semantic upgrade = bug
silent golden drift = bug
non-idempotent stage = bug
```

If a stage changes style, type, geometry, child order, node count, imports, or fidelity tier, it must explain itself in compiler-visible terms.

**Idempotency is a law.** Re-running any stage on its own output must be a no-op. Stages re-enter — CP2 conservation fires inside materialize, reconcile may run twice. Same input, same output, every time; a pass that drifts on the second pass over identical input is a bug.

---

# 5. 🏛️ Pipeline Source of Truth

Default path:

```text
Figma REST JSON or offline dump
  → fetch
  → parse
  → clean tree + tokens + conservation baselines
  → fonts/assets
  → LLM structured Screen IR, optional/cacheable
  → normalize/reconcile
  → materialize IR
  → layout passes
  → classification
  → fidelity stamp
  → emit
  → planned Dart reconcile
  → planned graph invariants
  → temp analyze
  → optional repair/refine
  → transactional write
```

Legacy deterministic layout path may exist, but behavior must not silently fork.

Any divergence between IR path and legacy path requires:

```text
explicit config flag
fixture coverage
clear ownership
no hidden screen-specific drift
```

## 5.1. Offline dumps live in the Flutter project (`--project-dir`)

Figma fetch/batch artifacts and offline regeneration inputs are **not** stored in the agent repo root. They live under **each target Flutter app**:

```text
<project_dir>/.debug/
```

Examples:

```text
sandbox/limbo/.debug/
demo_app/.debug/
```

When debugging or regenerating a screen without a live Figma call, agents must resolve dumps from the **project** passed to `--project-dir` (or `FIGMA_FLUTTER_PROJECT_DIR`), not from `tests/fixtures/` unless the task is explicitly corpus/fixture work.

Typical layout (paths relative to `project_dir`):

```text
<project_dir>/
├── wizard-state.yml
├── pubspec_resolve.sha256
├── .figma-flutter/
│   ├── layout-version
│   ├── shared/full_file_*.json
│   └── capture-sandbox/
└── .debug/
    └── <feature>/              # flat — only screen folders under .debug
        raw.json
        processed.json
        pre_emit.json
        plan.dart
        screen.dart
        figma.png
        semantics.json
        snapshot.json
        last.log
        llm_parsed.json
        provenance.json
        …
```

Workspace-level wizard prefs: `<workspace>/workspace-state.yml`.

`screens.yaml` maps `feature` → dump path; canonical raw dump is `.debug/<feature>/raw.json` (`raw_dump_path` in `debug/paths.py`). Wizard **fetch**, `batch dump`, and `generate --from-dump` resolve via project helpers. If a dump is “missing”, check `<project_dir>/.debug/<feature>/raw.json` first — not the agent repository. Use shell for gitignored `sandbox/` paths.

Legacy layouts (v2 domain folders, v3 `primary/`/`secondary/`) are migrated automatically on first pipeline touch (`debug/migrate.py`, v7).

---

# 6. 🧬 Dual Graph Contract

The compiler operates on two synchronized graphs.

| Graph                       | Role                                                              |
| --------------------------- | ----------------------------------------------------------------- |
| `CleanDesignTreeNode`       | Figma truth: geometry, style, type, paint order                   |
| `ScreenIr` / `WidgetIrNode` | Layout intent, semantic kind, payload, fidelity tier, child order |

## Rules

* Clean tree is the source of geometry truth.
* Screen IR may express layout intent, but it cannot invent geometry facts.
* Classifier may mutate only semantic/classification fields.
* IR passes may mutate only declared fields.
* Any graph sync repair must be deterministic and provenance-recorded.
* If graphs cannot be reconciled, fail early with a typed compiler error.
* **Settings enter at the pipeline boundary and flow through context.** `load_settings()` inside `generator/` or `parser/` is forbidden — a hidden global read breaks deterministic replay (request settings ≠ globally loaded settings) and poisons future failure capsules. Pass config via `IrEmitContext` / `PassContext`.

The IR is not a scratchpad.

The IR is a contract.

---

# 7. 🧯 Deterministic Failure Handling

## 7.1. Do not outsource deterministic failures

Do not let known deterministic failures fall through to:

```text
dart analyze
Flutter runtime
LLM repair
visual refine
write stage
```

If the compiler can detect the failure, the compiler must detect it before external tools run.

## 7.2. Planned Dart graph invariant

Before `dart analyze`, validate planned Dart graph consistency:

```text
for every Dart consumer file:
  every package:<app>/widgets/foo.dart import
  must resolve to planned file lib/widgets/foo.dart
```

If not, fail with a typed deterministic error:

```text
PlannedDartGraphError:
  stale widget import after reconcile
  consumer: lib/generated/foo_layout.dart
  import: package:app/widgets/input_field_widget.dart
  missing planned file: lib/widgets/input_field_widget.dart
```

Do **not** send this to LLM repair.

LLM repair is for ambiguous generated-code recovery, not for broken deterministic compiler invariants.

## 7.3. Prune/reconcile law

If a planned file is pruned:

```text
all consumer imports and references must be reconciled immediately
```

A compiler-created broken graph must never reach write stage.

---

# 8. 🧠 LLM Boundary

The LLM is not the source of truth.

The LLM may propose structured intent.

The compiler decides what is legal.

## LLM may produce

```text
screenIr
extractedWidgets[].widgetIr
semantic candidates
layout intent
repair suggestions
```

## LLM may not mutate

```text
Figma node ids
bounds
paint order
style truth
type truth
asset truth
deterministic graph facts
fidelity manifest
golden baselines
corpus tiers
```

If LLM output conflicts with deterministic facts:

```text
deterministic facts win
LLM output is sanitized, downgraded, or rejected
```

## Repair loop law

LLM repair must not fight deterministic infrastructure.

If identical analyzer errors repeat after repair attempts:

```text
stop repair
capture failure capsule
classify failure family
surface deterministic root cause
```

Do not keep asking the LLM to solve:

```text
missing planned file
stale import
broken pubspec
missing asset sync
invalid graph invariant
```

Those are compiler bugs.

---

# 9. 🚦 Semantic & Fidelity Gates

Semantic recognition and rendering permission are different axes.

## 9.1. Classification is not permission to emit

A node classified as `button_filled` is still just a candidate until fidelity gates allow it.

```text
semantic kind = annotation until proven
```

## 9.2. Fidelity tiers

| Tier                | Meaning                                                          |
| ------------------- | ---------------------------------------------------------------- |
| `native_verified`   | Manifest-backed; may emit native semantic widget when gates open |
| `native_unverified` | Recognized but not allowed to affect production output           |
| `styled_primitive`  | Safe Flutter primitive, not pixel-perfect semantic upgrade       |
| `svg_baked`         | Baked visual fallback                                            |
| `png_baked`         | Baked visual fallback                                            |
| `unsupported`       | Must fallback or fail safely                                     |

## 9.3. Report-only law

`semantics.report_only` is a global kill switch.

When `report_only=true`:

```text
semantic kinds may be reported
semantic reports may be written
promotion candidates may be generated
production Dart must not change because of semantics
```

Correct composition:

```text
report_only outer gate
AND
fidelity router inner gate
```

Do not collapse these gates.

---

# 10. 🧪 Corpus Law

A single green screen proves almost nothing.

A golden proves that one historical output stayed stable.

A corpus proves that the compiler generalizes.

## 10.1. Required workflow

```text
inbox
  → corpus
  → fixtures
  → blocking oracle
```

| Stage      | Meaning                                                      |
| ---------- | ------------------------------------------------------------ |
| `inbox`    | raw incoming screens, experiments, dirty customer-like cases |
| `corpus`   | curated examples with manifest purpose and quality profile   |
| `fixtures` | automated oracle cases                                       |
| `blocking` | release-stopping regression protection                       |

## 10.2. Corpus must include

```text
clean product screens
dirty real-world screens
stress/adversarial screens
regressions from old failures
semantic-only cases
text-heavy cases
non-English/cyrillic cases
bad layer names
nested groups
manual auto-layout simulations
```

A beautiful demo-only corpus is a trap.

Dirty cases are not garbage.

They are vaccines. 💉

## 10.3. Manifest law

Every corpus screen needs a passport.

Minimum shape:

```yaml
id: login_v1_clean
title: Login Version 1
quality_profile: clean
status: incubating
tier: advisory_pixel

purpose:
  - auth_form
  - email_input
  - password_input
  - primary_button
  - social_login_buttons

checks:
  visual: advisory
  geometry: true
  semantic: true
  text: advisory

expected_semantics:
  - input_text_field
  - button_filled
  - button_text
```

Do not promote a screen to blocking because it is convenient.

Promote only when:

```text
purpose is clear
baseline is stable
failure meaning is understood
oracle signal is useful
corpus value is real
```

---

# 11. 🛠️ Where To Fix Bugs

Fix the lowest correct compiler layer.

| Symptom                      | Correct layer                             |
| ---------------------------- | ----------------------------------------- |
| Missing/incorrect Figma fact | parser                                    |
| Lost node / child mismatch   | conservation / graph sync                 |
| Bad layout intent            | IR pass                                   |
| Wrong semantic candidate     | classifier / semantic corpus              |
| Wrong native output          | fidelity manifest / template              |
| Broken Dart graph            | planned reconcile / graph invariant       |
| Syntax mutation needed       | AST sidecar                               |
| Golden mismatch              | oracle diagnosis, not local patch         |
| Repeated repair loop         | infrastructure conflict, not prompt magic |
| Classifier trusts a name-derived type | `type_trust` / provenance marker, not the detector |

If you cannot name the layer, do not patch.

---

# 12. 🧨 Failure Family Rule

When a new screen fails, do not immediately patch the screen.

First classify the failure:

```text
input detection
button semantics
social auth button
stack/unstack
absolute host constraints
text metrics
font fallback
asset sync
planned Dart graph
stale import/reference
paint order
overflow
baked fallback
```

Then ask:

```text
Is this a one-off screen issue,
or a compiler family issue?
```

If it is a family issue, fix the family.

---

# 13. 🔒 Strictly Forbidden

## 13.1. Codegen and layout

* No screen-specific branches.
* No hardcoded `figmaId` behavior.
* No text-value-driven layout decisions.
* No customer-path-specific logic.
* No one-off pixel offsets to satisfy one golden.
* No anonymous hardcoded colors in generated logic.
* No viewport magic unless expressed as a named generic constraint policy.
* No unbounded `HUG` on absolute hosts without pixel binding.
* No hidden fallback that changes output without provenance.

## 13.2. Dart mutation

* No Python regex/string-replace Dart surgery.
* No line erasure in writer to “fix” braces.
* No non-UTF-8 Dart I/O.
* Programmatic Dart mutations must go through AST sidecar or a deterministic typed syntax repair with tests.

## 13.3. Semantics

* No fuzzy name/text matching as source of truth.
* No `looks_like_*` production heuristic outside controlled classifier/report-only flow.
* No native emit from `native_unverified`.
* No semantic mutation under `report_only=true`.

## 13.4. CI / corpus

* No auto-mutating `fidelity_manifest.yaml` in CI.
* No auto-promoting advisory to blocking.
* No auto-updating PNG baselines without explicit `--update-goldens`.
* No weakening thresholds to make a PR green.
* Burn-down baselines are **stable fingerprints** (`path | normalized_hash | category`), never raw counts. A count-only ratchet lets you swap debt sideways (delete 10, add 10, counter unchanged, CI silent). CI fails on any *new* fingerprint, and totals may only decrease.

---

# 14. ✅ Acceptable Fix Shape

Every serious fix should look like this:

```text
1. Reproduce with fixture or corpus case.
2. Classify failure family.
3. Identify correct compiler layer.
4. Add or update invariant/gate if missing.
5. Implement generic fix.
6. Add regression test.
7. Run relevant corpus/oracle/signoff.
8. Document promotion or downgrade if fidelity changed.
```

A fix that only makes the current screenshot pass is not a fix.

It is technical debt disguised as progress.

---

# 15. 🧑‍💻 Coding Style

* Keep new modules small (≤300 lines). Existing large files (`buttons.py`, `reconcile/__init__.py`, etc.) are debt: do not add to them, but do not split a working file just to hit the cap. Shrink by burning logic, not by shuffling it.
* Prefer typed helpers over inline condition jungles.
* Prefer explicit dataclasses/results over bool soup.
* Use `loguru` only.
* Runtime logs must be English and must not contain emojis.
* Prompts/docs may use emphasis and emojis when they clarify priority.
* Secrets via env only.
* No hidden global settings reads inside compiler internals when context should be explicit.
* Pass config through context objects where possible.

---

# 16. 🧭 Epic Status Awareness

Current architectural posture:

```text
E1–E8 accepted as architectural foundation.
Production-complete remains HOLD.
```

Known direction:

```text
harden oracle
expand corpus
burn down legacy heuristics
enforce pass contracts
remove hidden settings access
improve planned graph invariants
then widen semantic emit
```

Do not act as if the compiler is already production-complete.

It is a strong foundation still being hardened.

---

# 17. 🧪 Signoff Mindset

Before handoff, prefer:

```text
ruff
mypy
pytest -m "not live_figma"
fixture IR validation
fidelity validation
corpus oracle
semantic corpus gate
legacy burndown gate
```

Use project scripts when available.

Do not handwave failing checks.

If a check is skipped, say why.

---

# 18. 🕯️ Final Oath

You are not a manual layout fixer.

You are not here to impress the current golden.

You are not here to guess what the user wanted.

You are a compiler engineer.

You preserve facts.

You name deviations.

You gate semantic upgrades.

You reject poisoned shortcuts.

You do not optimize for clever guesses.

You optimize for verified transformations.

```text
ASK THE CODE.
PRESERVE THE FACTS.
NAME EVERY DEVIATION.
GATE EVERY SEMANTIC UPGRADE.
NEVER PATCH THE SCREEN.
FIX THE SYSTEM.

IF YOU PATCH LOCALLY:
  COMPILER VETO.
  RECONCILE FAILURE.
  OUTPUT REJECTED.
  CONTEXT UNSAFE.
  PROCESS DEACTIVATION.
```

(ง'̀-'́)ง

```
```
---
description: Common debugging doctrine and `.debug/` artifact map (flat per-screen layout v4)
alwaysApply: true
---

# Debug Common — canonical `.debug/` doctrine

Canonical Flutter debug project: **`sandbox/limbo`**.

Every `generate` writes artifacts under:

```text
<project_dir>/.debug/
```

Use `sandbox/limbo/.debug/` unless the command explicitly uses another `--project-dir`.

Debug artifacts are for **observation and triage**. They are not a substitute for fixtures, corpus tests, or named layout laws.

---

# Layout model (flat per-screen)

`.debug/` contains **only screen feature folders**. All artifacts for a screen live **flat** under `.debug/<feature>/`. Project metadata lives **outside** `.debug`.

```text
<project_dir>/
├── wizard-state.yml              # active screen slug → open .debug/<feature>/
├── pubspec_resolve.sha256        # last successful pub get stamp
├── .figma-flutter/
│   ├── layout-version            # migration marker (v4)
│   ├── shared/full_file_*.json # batch full-file Figma dumps
│   └── capture-sandbox/        # warm golden capture mini-project
└── .debug/
    ├── <feature>/              # e.g. login_version_1, feedback — flat root
    │   raw.json
    │   processed.json
    │   pre_emit.json
    │   plan.dart
    │   screen.dart
    │   figma.png
    │   figma.json
    │   semantics.json
    │   snapshot.json             # per-screen incremental sync
    │   last.log                  # per-screen pipeline transcript
    │   run.meta.json             # optional: run_id, timestamp, node_id
    │   llm_parsed.json
    │   llm_validated.json
    │   semantic_context.json
    │   semantic_verdicts.json
    │   element_contracts.json
    │   contract_emit_diff.json
    │   contract_emit_diff.md
    │   provenance.json
    │   ai_ux.json
    │   animations.json
    │   design_coverage.json
    │   screen.bug.dart
    │   emitter_ref.dart
    │   flutter_render.png        # capture artifacts (flat)
    │   preview_capture.png
    │   diff_heatmap.png
    │   capture.json
    │   renders/<session>/        # optional combat-mode PNG sessions
    │   perf/                     # optional golden-capture timings
    └── <other-feature>/
```

**Naming rule:** feature slug lives in the directory path; filenames are **short and stable** (no `<feature>_` prefix). Example: `feedback/screen.dart`, not `dart/feedback_screen.dart`.

**Resolve active screen:** read `<project_dir>/wizard-state.yml` (or CLI `--feature`), then open `.debug/<feature>/`.

**Gitignored paths:** `sandbox/` and `.debug/` may be invisible to IDE `Grep`/`Glob` — use shell (`Get-ChildItem`, `python`) when artifacts are missing from search.

---

# Hot triage vs deep dive (same folder, read priority)

## Hot triage bundle (~90% of `/diagnose`)

Minimum coherent chain for one generate run on one screen:

```text
Figma truth → parse → pre-emit IR → Dart → visual reference
```

| File | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `raw.json` | Raw Figma REST subtree, truth from API | Fetch/parse bugs, missing nodes, wrong geometry |
| `processed.json` | Parsed clean tree after `parser/tree.py`; classification and IR input | Layout/classification wrong but raw looks fine |
| `pre_emit.json` | IR snapshot immediately before emitter | Emitter/layout mismatch |
| `plan.dart` | Planned Dart bundle, post-planner/pre-write | Planner/template bugs |
| `screen.dart` | Final debug Dart bundle, pre-write gate | Compare vs emitted `lib/` without opening project |
| `figma.png` + `figma.json` | Figma visual gold: PNG + metadata | Pixel/layout fidelity vs Flutter |
| `semantics.json` | Node classification report: BUTTON, INPUT, etc. | Wrong widget types, missed components |
| `run.meta.json` | Run id, timestamp, command, node id (when emitted) | Confirm artifacts belong to the latest run |
| `last.log` | Per-screen subprocess + analyzer transcript | Failures, timeouts, analyze errors |
| `snapshot.json` | Per-screen incremental sync hashes | What changed since last generate for this screen? |

**Hot read order (fixed):**

```text
last.log → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

## Deep dive / report-only (same `.debug/<feature>/` folder)

| File | Purpose | When to read |
| ---- | ------- | ------------ |
| `llm_parsed.json` | LLM screen IR right after JSON parse | IR shape/schema issues |
| `llm_validated.json` | IR after `generator/ir/validate.py` guards | Render safety, stack/scroll/token violations |
| `semantic_context.json` | Semantic context package, if emitted | Semantic adjudication/input-context issues |
| `semantic_verdicts.json` | Report-only semantic verdicts, if emitted | What did the IR/LLM think this element is? |
| `element_contracts.json` | Report-only element contracts, if emitted | What control contract was recovered? |
| `contract_emit_diff.json` | Report-only diff: recovered contracts vs current Dart | Known contract says X; current emit does Y |
| `contract_emit_diff.md` | Human-readable contract-vs-emit gap report | Law-based visual/layout triage |
| `provenance.json` | Mutation + classification decision trail | Why did this node become X? |
| `ai_ux.json` | AI UX / a11y / nesting / spacing suggestions | UX polish, touch targets, token drift |
| `animations.json` | Prototype / routing / animation manifest hints | Navigation, transitions |
| `design_coverage.json` | Design coverage gaps, when emitted | Unsupported Figma features |
| `screen.bug.dart` | Dart bundle when analyze/gate failed, if present | Last known bad codegen |
| `emitter_ref.dart` | IR emitter golden bundle, when present | Deterministic emitter regressions |
| `flutter_render.png`, `capture.json`, etc. | Flutter render / diff / manifest | Pixel diff vs `figma.png` |
| `renders/<session>/` | Combat-mode PNG sessions: wizard / visual refine | Interactive refine loops |
| `perf/` | Golden-capture phase timings for this screen | Slow capture / pub get / build |

---

# Project metadata (outside `.debug`)

| Path | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `wizard-state.yml` | Wizard active screen slug | Which `.debug/<feature>/` to open |
| `pubspec_resolve.sha256` | Stamp of last successful `pub get` | Stale deps / skipped pub get |
| `.figma-flutter/shared/` | Full-file Figma batch dumps | Offline batch / `dump-file` |
| `.figma-flutter/capture-sandbox/` | Shared warm golden capture sandbox | Infrastructure / docker golden, not screen triage |
| `<workspace>/workspace-state.yml` | Active Flutter app under workspace | Multi-app wizard switch |

Agent repo `logs/` is global telemetry only, for example `figma_flutter_agent.log`.

---

# Legacy layouts (deprecated)

Do **not** read or write these for new work; migration v7 flattens on first pipeline touch:

```text
# v3 screen-centric (primary/secondary shards)
<feature>/primary/*
<feature>/secondary/*
.debug/logs/last.log
.debug/sync/snapshot.json
.debug/wizard-state.yml
.debug/pubspec_resolve.sha256
.debug/capture/sandbox/
.debug/.artifact-layout-v3

# v2 domain folders
raw/<feature>_layout.json
processed/<feature>_layout.json
ir/<feature>_*.json
dart/<feature>_plan.dart
dart/<feature>_screen.dart
…
```

Canonical path helpers: `src/figma_flutter_agent/debug/paths.py` (layout v4, `ARTIFACT_LAYOUT_VERSION = 7`).

---

# Core doctrine

Debugging has two phases:

```text
Phase 1 — Diagnosis / Triage
  Goal: identify the violated contract/law and responsible pipeline layer.
  Output: evidence-based triage report.
  No code changes.

Phase 2 — Repair
  Goal: implement the approved law-level fix in the approved layer only.
  Output: targeted fix + regression proof.
```

An agent must not move from Diagnosis to Repair without explicit approval of:

```text
target bug class
target law
files allowed to touch
tests to add/change
expected behavior change
```

---

# Final invariant

Do not fix the screen.

Fix the law.

A screen is only evidence.
A visual bug is only a symptom.
A durable fix must map to:

```text
ElementContract
ContractEmitRecipe
LayoutLaw
PolicyGate
EmitterLaw
CorpusTest
```

---

# Not always present

```text
<feature>/last.log
<feature>/flutter_render.png
<feature>/renders/
<feature>/perf/
<feature>/emitter_ref.dart
<feature>/screen.bug.dart
<feature>/semantic_context.json
<feature>/semantic_verdicts.json
<feature>/element_contracts.json
<feature>/contract_emit_diff.*
<feature>/run.meta.json
fidelity.json
```

Deprecated agent-repo paths are not valid debugging sources:

```text
logs/figma-debug
logs/dart
logs/reports
logs/semantics
dart-errors/
terminal/
```

Do not read or write them for screen debugging.

---

# Universal forbidden shortcuts

Never do these during diagnosis or repair:

```text
debugging from deprecated agent logs instead of .debug
hand-editing sandbox/limbo/lib or demo_app/lib to pass
screen-specific production patches
node-id-specific production branches
coordinate/padding magic numbers for one fixture
baseline/golden updates to hide failure
production behavior from text/name regex heuristics
LLM-generated Dart
direct semanticVerdict -> emit without policy gate
changing repair bot while debugging emitter/layout
changing preview/oracle flow while debugging emitter/layout
vector degradation side quests while debugging inputs/buttons/chips
mixing unrelated contract kinds in one fix
```

---

# One PR / one layer rule

A debugging PR must target only one layer class:

```text
A. observation/report-only artifact
B. semantic context / semantic verdict schema
C. element contract recovery
D. contract-to-emit recipe registry
E. contract-vs-emit diff
F. policy gate
G. one emitter law
H. legacy heuristic removal
I. tests/docs only
```

Do not combine these unless explicitly approved.

---

# Acceptable fix rule

A fix is acceptable only if it can answer:

```text
Which named law did this fix implement or tighten?
Which fixture/test proves it?
Why will it apply to the next screen?
Which unrelated laws were checked as unchanged?
Which shortcuts were avoided?
```

A PR that only makes the current screen look better without a named law and regression proof should be rejected.
---
name: diagnose
description: >-
  Diagnosis-only debugging skill: inspect `.debug` artifacts, map symptoms to
  contracts/laws, and stop before any code change. Use when investigating a
  pipeline, layout, IR, semantic, contract, emitter, analyzer, or visual bug.
disable-model-invocation: false
---

@.claude/prompts/debug-common.md

# Debug Diagnosis Skill

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

This skill is diagnosis-only.

Do not change code.
Do not edit generated Dart.
Do not update baselines.
Do not apply fixes.

The required output is a **PRE-FIX TRIAGE REPORT**.

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
<project_dir>/wizard-state.yml   # active feature slug
.debug/<feature>/last.log
.debug/<feature>/ file timestamps
CLI args if available
```

If artifacts are stale or missing, state this and request/re-run the correct stage. Do not continue as if stale artifacts are current.

---

# Step 2 — Read artifacts in order

Default order (under `.debug/<feature>/`, flat):

```text
1. last.log
2. raw.json vs processed.json
3. llm_parsed.json
4. llm_validated.json
5. pre_emit.json
6. semantic_context.json, if present
7. semantic_verdicts.json, if present
8. element_contracts.json, if present
9. contract_emit_diff.json / .md, if present
10. provenance.json
11. semantics.json
12. plan.dart
13. screen.dart
14. screen.bug.dart, if present
15. figma.png / figma.json
16. flutter_render.png, capture.json, renders/, if present
17. ai_ux.json, animations.json, design_coverage.json
18. snapshot.json
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

# Step 6 — Select one target bug class

A diagnosis may list many bug classes.
A repair task may target exactly one.

Choose one recommended target:

```text
one contract_kind
one law family
one responsible layer
```

Explicitly defer the rest.

---

# Step 7 — Propose regression proof

Every proposed fix must have proof:

```text
unit test for law
fixture/corpus test
contract-vs-emit diff assertion
golden/visual test if appropriate
```

Limbo `.debug` is observation only. It is not regression proof.

For each target bug class, propose:

```text
test name
fixture
assertion
why it generalizes to future screens
```

---

# Required output: PRE-FIX TRIAGE REPORT

Produce this report and stop.

```text
PRE-FIX TRIAGE REPORT

Active feature:
Active project dir:
Artifact freshness:
Last command/run evidence:

Symptoms:
  grouped by contract_kind/law, not only by visual location

Evidence:
  paths + node ids + snippets

Target bug class:
  contract_kind:
  subtype:
  law:
  layer:

Non-target bug classes:
  list and explicitly defer

Diagnosis:
  what violated the law:
  why it is systemic or fixture-local:

Proposed fix:
  smallest law-level change:

Files allowed to touch:
Files forbidden to touch:

Tests to add/change:
  test name:
  fixture:
  assertion:

Expected behavior change:
Expected unchanged behavior:
Regression risk:
Rollback plan:

Approval needed:
  target law
  files
  tests
  behavior change
```

After producing this report, do not code until approved.
