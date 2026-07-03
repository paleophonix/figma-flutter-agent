# Systemic review findings

Systemic analytical review of figma-flutter-agent compiler.  
Baseline: [`review-baseline.md`](review-baseline.md) · Gates: [`gate-truth-matrix.md`](gate-truth-matrix.md) · Boundaries: [`architectural-boundaries.md`](architectural-boundaries.md)

---

## Finding: Preview label hides flutter test cost

### Violated goal
fast feedback

### Failure family
preview/oracle confusion

### Why this matters
Developers choosing Wizard View → preview or `default_capture_mode: preview` expect quick visual feedback. They still pay full warm-sandbox `flutter test` compile (up to 20 min timeout) before the only difference — skipping pixel diff — applies.

### Systemic cause
`capture_with_mode()` correctly separates browser sketch from oracle in [`preview_capture/router.py`](../../src/figma_flutter_agent/preview_capture/router.py), but [`dev/view_renders.py`](../../src/figma_flutter_agent/dev/view_renders.py) and [`debug/capture.py`](../../src/figma_flutter_agent/debug/capture.py) bypass the router and always call `capture_planned_in_warm_sandbox()`. Mode only changes output path and whether diff runs **after** capture.

### Evidence to look for
- `run_view_preview_capture` records `backend: flutter_test` ([`view_renders.py:198-205`](../../src/figma_flutter_agent/dev/view_renders.py))
- `debug/capture.py:144-189` — capture first, `resolve_capture_mode` only at line 167
- [`preview_capture/README.md`](../../src/figma_flutter_agent/preview_capture/README.md) documents the split explicitly

### Correct architectural direction
preview pipeline / CLI product boundary — single capture router for all entry points

### Recommended fix shape
**mode split** — `FastSketch` (browser) vs `FlutterParity` (flutter test) as explicit user choices; rename wizard menu items; route through `capture_with_mode()`

### Priority
P0

### Confidence
High

---

## Finding: Interactive preview profile is a no-op

### Violated goal
fast feedback

### Failure family
slow default workflow

### Why this matters
Wizard launch/run calls `apply_interactive_preview_profile()` but it returns settings unchanged. Default `llm_visual_refine: true` remains active, so interactive iteration runs pixel compare + LLM refine loops — signoff-grade work on every run.

### Systemic cause
Profile layer documents intent ([`profiles.py:40-47`](../../src/figma_flutter_agent/config/profiles.py)) without enforcing a distinct generation bundle. No boundary between `iterate` and `oracle` product modes at config level.

### Evidence to look for
- `GenerationConfig.llm_visual_refine: bool = True` ([`config/models.py:218`](../../src/figma_flutter_agent/config/models.py))
- `apply_interactive_preview_profile` returns `settings` unchanged
- [`stages/visual_refine/loop.py`](../../src/figma_flutter_agent/stages/visual_refine/loop.py) runs when flag true and not dry-run

### Correct architectural direction
CLI/product boundary + config profiles

### Recommended fix shape
**mode split** — interactive profile sets `llm_visual_refine=false`, `runtime_geometry_gate=false`, shorter capture timeout; document `figma-flutter generate --refine` for oracle path

### Priority
P0

### Confidence
High

---

## Finding: Text and corpus labels drive production NodeType

### Violated goal
semantic safety, generalization

### Failure family
hidden heuristic, semantic permission leak

### Why this matters
INPUT/BUTTON classification uses copy (`email`, `password`) and fixture-tuned single-word labels (`meditate`, `sleep`, `music`) in [`parser/interaction/shared.py`](../../src/figma_flutter_agent/parser/interaction/shared.py). These flow to `NodeType` on the clean tree and directly select emit widgets — bypassing IR semantic `report_only` and corpus-gate (which only tests offline classifier fixtures).

### Systemic cause
Parser interaction layer conflates **classification signal** with **emit authority**. No fidelity tier or manifest gate between text hint and `NodeType` mutation. Corpus leakage is visible in `_SINGLE_WORD_ACTION_LABELS` (music-app vocabulary).

### Evidence to look for
- `_INPUT_HINTS`, `_ACTION_HINTS`, `_SINGLE_WORD_ACTION_LABELS` in shared.py
- `stack_interaction_kind()` in enrichment.py
- semantics corpus-gate does not import `parser/interaction/*`
- project-bible §3: name-derived types must carry `derived_from_name`

### Correct architectural direction
semantic classifier + fidelity router (emit must not read raw text hints)

### Recommended fix shape
**typed model** — `ClassificationSignal { source: text|geometry|component, confidence }`; emit gated by `fidelityTier` + manifest; corpus-gate extended to interaction predicates

### Priority
P1

### Confidence
High

---

## Finding: Reconcile synthesizes canonical names consumed by emit

### Violated goal
generalization, fact preservation

### Failure family
hidden heuristic, overfitting

### Why this matters
Normalize passes synthesize nodes named `ConsentRow` and `WeekdayChipRow` ([`parser/layout/reconcilers_ui.py`](../../src/figma_flutter_agent/parser/layout/reconcilers_ui.py)). Emit then branches on `node.name == "ConsentRow"` ([`checkbox_rows.py`](../../src/figma_flutter_agent/generator/layout/widgets/button/checkbox_rows.py), [`emit/helpers.py`](../../src/figma_flutter_agent/generator/layout/widgets/emit/helpers.py)). New screens with different layer names miss the path; familiar corpus screens pass.

### Systemic cause
14-pass reconcile chain ([`normalize.py`](../../src/figma_flutter_agent/generator/normalize.py)) encodes domain fixes as tree surgery + magic names instead of typed `layout_role` on nodes with provenance. Passes 4–6, 8–9, 11, 13 lack unit tests per [`reconcile-passes.md`](reconcile-passes.md).

### Evidence to look for
- diff-triada: auth/consent patterns pass; bounded_overflow shows soft geometry violations
- predicate-matrix: `painted_pill_23px` matches two predicates (pill + status badge)
- grep `ConsentRow|WEEKDAY_CHIP` across parser + emit

### Correct architectural direction
clean tree normalization + emit dispatch registry

### Recommended fix shape
**invariant** — reconcile may only set `layout_role` enum fields; emit reads enum; **corpus policy** — each pass requires generic fixture + mutual-exclusion row in predicate-matrix CI

### Priority
P1

### Confidence
High

---

## Finding: LLM screen stub fallback masks broken screenCode

### Violated goal
determinism, developer experience

### Failure family
silent fallback, LLM overreach

### Why this matters
When LLM `screenCode` fails delimiter repair, [`llm_codegen/screen.py`](../../src/figma_flutter_agent/generator/dart/llm_codegen/screen.py) replaces it with `_layout_delegation_screen_stub()` wrapping deterministic layout. With `quiet_expected_fallback=True`, this logs at info level. Pipeline continues; developer sees "success" while custom screen logic silently disappeared.

### Systemic cause
Boundary between **LLM optional body** and **deterministic layout contract** uses fallback-to-success instead of typed failure. Repair layer compensates for deterministic invariant gaps in screen code validation.

### Evidence to look for
- `_layout_delegation_screen_stub` + `quiet_expected_fallback` parameter
- `run_validate_repair_refine_phase` always attempts repair on analyze fail
- IR validate does not cover LLM screen class structure

### Correct architectural direction
IR contract + planned Dart graph (fail before write when screen body invalid)

### Recommended fix shape
**diagnostic** — `ScreenCodeFallbackWarning` with provenance; production profile **fail-closed**; no quiet mode in strict paths

### Priority
P1

### Confidence
High

---

## Finding: Deterministic rules live in prompts without sanitizers

### Violated goal
determinism

### Failure family
late invariant detection

### Why this matters
52 `SYSTEMIC_BUG_RULES` entries exist; [`systemic_rules.py`](../../src/figma_flutter_agent/audit/systemic_rules.py) maps only a representative subset. At least `LayoutBuilder` ban is **prompt only** — violations surface only at dart analyze or human review, not IR validate.

### Systemic cause
LLM prompt registry grew faster than IR/AST sanitizer coverage. Repair loop can fix symptoms after emit, hiding missing compile-time guards. Audit tooling documents gap but CI does not block prompt-only rules.

### Evidence to look for
- [`ir-llm-coverage.md`](ir-llm-coverage.md): 52 total, gaps section
- remediation-backlog P4: prompt-only rules open
- `apply_render_safety_guards` does not include LayoutBuilder detection

### Correct architectural direction
IR validate + AST sidecar

### Recommended fix shape
**gate** — CI ratchet: every `SYSTEMIC_BUG_RULES` entry must map to sanitizer or explicit waiver; **invariant** in IR or AST for each prompt-only rule

### Priority
P2

### Confidence
Medium

---

## Finding: Auto-fix guards mutate geometry with weak policy attribution

### Violated goal
fact preservation

### Failure family
silent fallback (fact mutation)

### Why this matters
Provenance for `login_version_1` shows repeated `viewport_clamp_guard` and `keyboard_scroll_guard` mutations with `"policy": null` ([`sandbox/limbo/.debug/provenance/login_version_1.json`](../../sandbox/limbo/.debug/provenance/login_version_1.json)). Stack placement changes (778→775) are real geometry deltas — hard to audit whether they were necessary or over-aggressive.

### Systemic cause
IR auto-fix guards ([`generator/ir/validate/guards.py`](../../src/figma_flutter_agent/generator/ir/validate/guards.py)) mutate clean tree before emit with checkpoint `CP1_guards` but optional policy name. Duplicated mutation entries suggest idempotent recording gaps.

### Evidence to look for
- provenance mutations with `policy: null`
- duplicate identical viewport_clamp entries same node
- diff-triada soft violations: `inv_text_metrics` on consent_checkbox, prefilled_input

### Correct architectural direction
IR contract + provenance recorder

### Recommended fix shape
**typed model** — every auto-fix carries `policy_id` + `justification`; dedupe recorder; design_coverage warning when clamp delta > ε

### Priority
P2

### Confidence
Medium

---

## Finding: Green signoff corpus disjoint from wizard reality

### Violated goal
corpus truthfulness, generalization

### Failure family
baseline drift, overfitting

### Why this matters
`demo-signoff` uses five `figma_*_sample.json` widgets ([`cli/live.py`](../../src/figma_flutter_agent/cli/live.py)). Audit corpus uses sign_up/reminders/music layouts. Wizard active screen (`login_version_1` in limbo) may be in none of these. CI green does not bound risk on the frame the product owner stares at daily.

### Systemic cause
Multiple corpora (demo-signoff, audit, screens.yaml oracle, semantics manifest) without a single **coverage map** or requirement that wizard default screen ∈ blocking oracle set.

### Evidence to look for
- `_DEMO_SIGNOFF_FIXTURES` list vs `AUDIT_CORPUS` in [`audit/corpus.py`](../../src/figma_flutter_agent/audit/corpus.py)
- [`gate-truth-matrix.md`](gate-truth-matrix.md) overlap table
- `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` documented escape hatch

### Correct architectural direction
corpus manifest + signoff policy

### Recommended fix shape
**corpus policy** — unified manifest with tiers; wizard-active screen must map to a pattern class; blocking oracle must include ≥1 screen per pattern class in audit corpus

### Priority
P1

### Confidence
High

---

## Finding: Wizard preview and oracle share identical capture function

### Violated goal
developer experience

### Failure family
preview/oracle confusion

### Why this matters
`run_view_preview_capture` and `run_view_oracle_capture` both call `_capture_flutter_render_png()` with the same settings ([`view_renders.py:192-255`](../../src/figma_flutter_agent/dev/view_renders.py)). Menu labels imply different validation intensity; behavior differs only in output directory and render log tag.

### Systemic cause
Product UX promises three tiers (preview / oracle / renders) but implementation only distinguishes renders (combat diff) from duplicate capture. Oracle semantic meaning ("blocking truth") is not encoded in capture path.

### Evidence to look for
- Side-by-side function bodies in view_renders.py
- latency-matrix decision tree

### Correct architectural direction
preview pipeline vs oracle pipeline

### Recommended fix shape
**boundary** — preview → browser sketch or cached PNG; oracle → flutter test + mandatory figma diff; renders → combat session with explicit slow warning (partially exists)

### Priority
P0

### Confidence
High

---

## Finding: Incremental LLM skip can leave stale screen IR

### Violated goal
determinism, fact preservation

### Failure family
graph inconsistency

### Why this matters
When design tree hash is unchanged, LLM stage skips ([`pipeline/llm.py`](../../src/figma_flutter_agent/pipeline/llm.py)). Token-only changes log a warning but still skip full regen unless `regen_llm_on_token_change` (production enables it). Parser/normalize improvements without tree hash change may not refresh IR.

### Systemic cause
Incremental sync optimizes for speed without a **compiler version** or **normalize revision** in skip key. Boundary between cache and correctness is hash-only.

### Evidence to look for
- `skipped_incremental` branches in llm.py
- `sync/snapshot.json` in limbo `.debug`
- production profile `regen_llm_on_token_change: true` vs dev default

### Correct architectural direction
incremental sync / CLI product boundary

### Recommended fix shape
**invariant** — skip key includes emitter + normalize pass version; stale IR diagnostic when parser version bumps

### Priority
P2

### Confidence
Medium

---

## Goal coverage summary

| Primary goal | Finding(s) | Status |
| --- | --- | --- |
| Fast human feedback | Preview mislabel, no-op profile, shared preview/oracle capture | **violated** |
| Generalization | Text hints, reconcile magic names, corpus disjoint | **violated** |
| Deterministic compiler | Prompt-only rules, LLM stub fallback, incremental skip | **partial** |
| Preservation of facts | Auto-fix policy null, synthetic names | **partial** |
| Controlled semantics | Text→NodeType bypasses report_only | **violated** |
| No local patching | No figmaId/screen slug in emit (good); synthetic names (bad) | **partial** |
| Useful validation | Corpus disjoint, advisory ai_ux, oracle skip | **violated** |

**Protected evidence:** No hardcoded Figma node IDs in production `src/`; `capture_with_mode` prevents preview→oracle fallback in router; conservation checkpoints CP0–CP2 exist with provenance trail.
