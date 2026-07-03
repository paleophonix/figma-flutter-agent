# ТЗ: Codex Hardening — три параллельные ветки исполнения

> Статус: v1.1 — detailed split на 3 равновесные ветки
> Дата: 2026-06-13
> Источник: Codex Hardening v1.0: восстановление кодекса и архитектурных границ. 
> Цель: раздать 9 эпиков трём агентам так, чтобы они могли работать одновременно, не мешая друг другу, не размывая ownership и не легализуя shortcuts как expected behavior.

---

# 0. Сводка

## 0.1. Общая цель

Вернуть проект Figma → Flutter compiler к code-bible compliant состоянию:

```text
green gates
fast preview boundary
no hidden production heuristics
named degradation
deterministic compiler failures
truthful governance
```

Проект не должен чинить текущие visual bugs через:

```text
name/text production shortcuts
silent fallbacks
baseline suppression
LLM repair of deterministic failures
preview paths that secretly run flutter_test
```

---

## 0.2. Девять эпиков

```text
1. E0       — Unblock merge
2. E3-lite  — Vector red lint unblock
3. E4       — Compiler purity

4. F1       — SemanticEvidence
5. E2       — Heuristics → Evidence
6. E5       — Governance

7. F2       — DeviationRecord
8. E1       — Preview ≠ Oracle
9. E3-full  — Vector named degradation
```

---

## 0.3. Три равновесные ветки

| Ветка        | Агент   | Эпики           | Миссия                                                                                                                 |
| ------------ | ------- | --------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Branch A** | Agent A | E0, E3-lite, E4 | Остановить кровотечение: зелёные gates, убрать новые violations, закрыть settings leak и deterministic repair boundary |
| **Branch B** | Agent B | F1, E2, E5      | Построить semantic evidence boundary и governance, чтобы эвристики больше не маскировались под факты                   |
| **Branch C** | Agent C | F2, E1, E3-full | Закрыть preview/oracle boundary и ввести named degradation через DeviationRecord                                       |

---

# 1. Общие законы для всех веток

## 1.1. Закон merge gate

Пока E0 красный:

```text
do not merge dirty tree
do not update baselines
do not suppress fingerprints
do not argue architecture as excuse
```

E0 — единственный immediate merge blocker.

---

## 1.2. Закон границы

Чистый интерфейс не считается внедрённой границей, если production callsites могут его обойти.

```text
Boundary exists
  ⇔ all production callsites go through it
```

Пример:

```text
capture_with_mode(PREVIEW) exists
```

не значит, что preview boundary восстановлена, если:

```text
run_view_preview_capture
  → capture_planned_in_warm_sandbox
  → flutter_test
```

---

## 1.3. Закон evidence

`node.text` и `node.name` не являются facts.

Они могут создавать только evidence:

```text
SemanticEvidence(source=text_hint/name_hint, allowed_effect=candidate)
```

Они не могут напрямую менять:

```text
CleanDesignTreeNode.type
layout
wrap policy
variant state
obscureText
headline wrapping
production emit
```

---

## 1.4. Закон именованной деградации

Любая потеря fidelity обязана быть названа.

```text
missing vector asset
polluted screen downgrade
filesystem asset recovery
unsupported visual node
```

Нельзя молча заменить неизвестный/неэкспортированный визуальный факт на “примерно похожий” Flutter widget.

---

## 1.5. Закон детерминизма

Детерминированный сбой компилятора не чинится LLM.

```text
missing planned file
stale import
broken planned graph
invalid deterministic Dart
geometry invariant violation
asset/pubspec mismatch
```

должны идти в:

```text
typed compiler error
```

а не в:

```text
flutter analyze → LLM repair
```

---

## 1.6. Закон режима

Режим обязан менять поведение, а не только label.

```text
mode=preview
  must not call flutter test
  must not call pub get
  must not call golden
  must not call oracle
  must not call visual refine
  must not call LLM repair
```

---

# 2. Глобальные запреты

Запрещено всем агентам:

```text
update baseline
suppress fingerprint
rename-helper to bypass lint
move shortcut to unscanned file
preserve login visual quality through forbidden shortcuts
introduce production text/name heuristic effects
fallback preview → flutter_test
use LLM repair for deterministic compiler failures
add tests that cement forbidden shortcuts
```

---

# 3. Глобально разрешённые действия

Разрешено:

```text
revert
park only as report-only / evidence-only / zero production effect
minimal-correct only when required by explicit compiler contract
new isolated model files
new isolated tests
non-blocking draft linters
docs/specs
callsite inventory
```

---

# 4. Cross-branch ownership

## 4.1. Dirty roots принадлежат Branch A до зелёного E0

Branch A имеет приоритет на файлы:

```text
src/figma_flutter_agent/generator/layout/widgets/svg.py
src/figma_flutter_agent/generator/layout/widgets/input/fields.py
src/figma_flutter_agent/generator/ir/materialize.py
src/figma_flutter_agent/parser/interaction/forms.py
src/figma_flutter_agent/generator/layout/flex_policy/row.py
src/figma_flutter_agent/generator/layout/flex_policy/stack.py
src/figma_flutter_agent/generator/layout/flex_policy/wrap.py
tests/test_login_form_emit_fixes.py
```

Branch B/C не трогают эти файлы до зелёного E0 без явной координации.

---

## 4.2. Branch B owns semantic/evidence policy

Branch B owns:

```text
SemanticEvidence
text/name heuristic policy
no-new-text/name-production-effect lint
semantic burndown strategy
governance budgets
tier-aware reporting
corpus diversity quotas
```

---

## 4.3. Branch C owns preview/deviation boundary

Branch C owns:

```text
DeviationRecord
preview purity
capture mode split
preview/combat/oracle naming
lint_preview_purity
named degradation for vectors
recovery/downgrade provenance
```

---

# 5. Merge order

```text
1. Branch A lands E0 + E3-lite first.
2. Branch B/C may land isolated F1/F2 prep only if gates stay green.
3. After E0 green:
   - Branch C lands E1 preview boundary.
   - Branch C lands E3-full vector named degradation.
   - Branch B lands E2 staged heuristic migration.
   - Branch A completes E4 compiler purity.
   - Branch B lands E5 governance.
```

---

# 6. Parallel execution plan

## Day 0

```text
Agent A:
  start E0 surgical revert per fingerprint
  close red gates
  rewrite shortcut-locking tests

Agent B:
  start F1 SemanticEvidence model + tests
  draft E2 lint/spec
  draft E5 governance schema

Agent C:
  start F2 DeviationRecord model + tests
  inventory preview callsites
  draft lint_preview_purity
  prepare E1 routing plan
```

---

## After Branch A green

```text
Agent A:
  continue E4 compiler purity work

Agent B:
  start E2 migration in stages

Agent C:
  switch preview production callsites
  enable lint_preview_purity
  implement E3-full vector degradation
```

---

# Branch A — Merge Unblock & Compiler Purity

## A.0. Branch summary

```text
Agent: Agent A
Mission: stop the bleeding
Epics:
  1. E0 — Unblock merge
  2. E3-lite — Vector red lint unblock
  3. E4 — Compiler purity
```

Branch A отвечает за immediate unblock и за самые близкие к compiler core deterministic issues.

---

## A.1. E0 — Unblock merge

### Axis

```text
Merge P0
```

### Goal

Вернуть dirty tree в состояние, где code-bible gates зелёные.

E0 не должен решать всю архитектуру. Он должен:

```text
remove new violations
avoid baseline suppression
avoid shortcut cementing
restore mergeability
```

---

### Verified problem roots

```text
lint_dart_in_python:
  generator/layout/widgets/svg.py | dart_widget_literal

lint_settings_purity:
  generator/ir/materialize.py | load_settings_call

semantics_legacy_burndown:
  parser/interaction/forms.py ×4
  generator/layout/flex_policy/row.py
  generator/layout/flex_policy/stack.py ×2
  generator/layout/flex_policy/wrap.py

tests:
  tests/test_login_form_emit_fixes.py protects shortcuts
```

---

### Execution principle

Default action:

```text
revert
```

Allowed alternatives:

```text
park:
  only report-only / evidence-only / zero production effect

minimal-correct:
  only if required to remove violation while preserving explicit compiler contract
```

Forbidden:

```text
baseline update
suppress fingerprint
rename helper
move violation
preserve login visual quality via forbidden shortcut
```

---

### Scope by file

#### `parser/interaction/forms.py`

Default:

```text
revert new production name/text heuristics
```

Specifically forbidden in E0:

```text
node.name → system chrome production behavior
text/hint/name → password behavior
text/name → consent behavior that mutates layout/output
```

Allowed:

```text
report-only evidence stub
no production effect
```

---

#### `generator/layout/flex_policy/row.py`

Default:

```text
revert new production predicates that depend on text/name/archetype recognition
```

Forbidden:

```text
row behavior changes from copy/name pattern
login-specific flex salvage
```

Allowed:

```text
pure geometry rule if already legal and no new fingerprint
```

---

#### `generator/layout/flex_policy/stack.py`

Default:

```text
revert new production stack predicates that infer semantic chrome/status/form role
```

Forbidden:

```text
name/status/chrome-based wrapping or positioning
```

Allowed:

```text
geometry-only correction with no text/name read
```

---

#### `generator/layout/flex_policy/wrap.py`

Default:

```text
revert WIP wrapping heuristics
```

Forbidden:

```text
font/text/name/chrome/card/status/pill/stepper archetype shortcuts
```

Allowed:

```text
existing baseline behavior only
```

---

#### `generator/layout/widgets/svg.py`

Handled by E3-lite.

Immediate E0 requirement:

```text
remove inline Dart literal causing lint_dart_in_python
remove silent vector→Container fallback if newly introduced
```

---

#### `generator/layout/widgets/input/fields.py`

Immediate E0 requirement:

```text
remove new fingerprint source if present
do not introduce Dart string literal fallback
do not preserve login field visual fix via shortcut
```

---

#### `generator/ir/materialize.py`

Handled as minimal-correct if revert is not enough.

Requirement:

```text
no load_settings() inside generator internals
pass semantics/fidelity policy explicitly through context
```

---

#### `tests/test_login_form_emit_fixes.py`

Must be rewritten.

Remove assertions that encode:

```text
name → chrome
hint/name/text → obscureText
font-size → single-line / FittedBox
missing vector → Container
text/name → flex wrapping
```

Replace with assertions:

```text
text/name produces evidence only
production effect requires gated source
missing vector produces unsupported/degraded diagnostic
no shortcut is required to keep login visual quality
```

---

### Local acceptance

Run after each meaningful patch:

```text
lint_dart_in_python
lint_settings_purity
semantics_legacy_burndown
lint_hardcoded_colors
lint_regex_dart_surgery
ruff
targeted tests for touched modules
```

---

### Merge-ready acceptance

Before ready-for-review / merge:

```text
pytest -q -m "not live_figma"
```

or equivalent CI proof.

---

### E0 DoD

```text
all code-bible lint gates green
no new baseline fingerprints
no fingerprint suppression
shortcut-locking tests removed or rewritten
login_version_1 visual regression accepted if needed
dirty tree no longer violates codex gates
```

---

## A.2. E3-lite — Vector red lint unblock

### Axis

```text
Merge P0 component
```

### Goal

Close the current vector-related red lint without implementing full named degradation yet.

---

### Problem

Current behavior:

```text
VECTOR without vector_asset_key/path
  → Container(width, height, color)
```

This is invalid because it:

```text
invents visual geometry
hides missing vector export
violates pixel fidelity
adds Dart literal in Python
cements fallback as expected behavior
```

---

### Allowed E3-lite outcomes

```text
revert fallback
park fallback out of production path
emit unsupported diagnostic
emit typed degraded stub without Dart string literal
```

---

### Forbidden E3-lite outcomes

```text
silent rectangle
Container fallback in production
inline Dart widget literal in Python
test asserting missing vector → Container
baseline update
```

---

### Required test changes

Remove:

```text
assert missing vector emits Container
```

Add:

```text
assert missing vector reports unsupported/degraded visual node
assert no inline Dart literal is introduced
assert production path does not silently approximate vector as rectangle
```

---

### E3-lite DoD

```text
[x] lint_dart_in_python green
[x] vector red fingerprint gone (render_filled_vector_leaf removed from svg.py)
[x] no silent vector→Container in production path (VECTOR without asset → SizedBox.shrink)
[x] tests no longer protect rectangle fallback; vector_missing_export audit added
[x] full DeviationRecord not required yet
```

---

## A.3. E4 — Compiler purity

### Axis

```text
P1 determinism
```

### Goal

Make compiler core deterministic:

```text
same IR + clean tree + tokens + policy
  → same Dart
```

No hidden dependency on:

```text
cwd
.env
YAML
global settings
process state
```

---

### Immediate responsibility

The immediate E4 piece inside Branch A is:

```text
materialize.py settings leak
```

Requirement:

```text
remove load_settings() from generator/ir/materialize.py
```

---

### Correct direction

Settings are read only at boundary:

```text
CLI
pipeline
wizard
```

Compiler internals receive explicit typed policy:

```text
CompilerPolicy
SemanticPolicy
FidelityPolicy
RuntimePolicy
```

or through existing context:

```text
IrEmitContext
```

---

### Materialize minimal-correct path

If `materialize.py` needs semantics settings, pass them through context.

Allowed:

```text
ctx.semantic_policy
ctx.fidelity_policy
ctx.semantic_report_only
explicit semantics object
```

Forbidden:

```text
from figma_flutter_agent.config import load_settings
load_settings().agent.semantics
```

---

### Later E4 responsibilities

After E0 green:

```text
settings_purity baseline → ratchet-to-zero
emit_parse_gate default true
native Dart parser / ast_sidecar after serialization
repair ownership matrix
geometry invariant no longer enters LLM repair loop
```

---

### Parse gate law

Correct wording:

```text
Invalid deterministic Dart must be caught immediately after serialization,
before dart analyze,
before LLM repair,
before write.
```

---

### LLM repair ownership

Allowed for:

```text
LLM-owned screenCode
semantic ambiguity
bounded syntax repair of model-owned output
```

Forbidden for:

```text
deterministic *_layout.dart
planned graph closure
missing imports/files
asset sync
pubspec
geometry invariant failure
compiler-owned syntax
```

---

### E4 DoD

Immediate Branch A DoD:

```text
materialize.py does not introduce load_settings fingerprint
lint_settings_purity green
policy is explicit at compiler boundary touched by E0
```

Full E4 DoD:

```text
generator internals do not call load_settings()
settings_purity baseline empty or ratchet-to-zero with deadline
emit_parse_gate true
deterministic invalid Dart fails before analyzer/repair/write
deterministic files never route to LLM repair
geometry invariant failure produces typed error/report, not repair prompt
```

---

# Branch B — Semantic Evidence & Governance

## B.0. Branch summary

```text
Agent: Agent B
Mission: stop heuristic-as-knowledge
Epics:
  4. F1 — SemanticEvidence
  5. E2 — Heuristics → Evidence
  6. E5 — Governance
```

Branch B отвечает за semantic/evidence boundary и за то, чтобы gates начали мерить доверие, а не просто отсутствие нового долга.

---

## B.1. F1 — SemanticEvidence

### Axis

```text
Foundation
```

### Goal

Ввести typed model для semantic signals.

`node.text` и `node.name` больше не должны напрямую менять production behavior.

Они могут производить только evidence.

---

### Model

```text
SemanticEvidence:
  source: text_hint | name_hint | geometry | component_property | visual_anatomy
  confidence: float [0..1]
  provenance:
    node_id
    rule
    input values
    source field
  locale_scope: global | locale_dependent
  allowed_effect: report_only | candidate | gated_emit
```

---

### Core law

```text
source in {text_hint, name_hint}
  => allowed_effect <= candidate
```

Meaning:

```text
text/name can suggest
text/name cannot decide
```

---

### Allowed effect semantics

#### `report_only`

```text
visible in debug/report
no compiler behavior change
no production output effect
```

#### `candidate`

```text
can be consumed by later arbiter
cannot directly mutate facts
cannot directly emit native widgets
```

#### `gated_emit`

```text
allowed to affect production
only after fidelity-router / manifest / corpus / explicit policy gate
```

---

### Placement

Preferred locations:

```text
src/figma_flutter_agent/generator/ir/passes/provenance_record.py
```

or adjacent typed model module if existing structure demands.

Do not duplicate existing provenance concepts.

---

### Tests

Add mock fixture tests:

```text
text_hint creates SemanticEvidence(candidate)
name_hint creates SemanticEvidence(candidate)
geometry evidence can be higher effect if policy allows
component_property can become gated source
text/name cannot be gated_emit directly
```

---

### Allowed before Branch A green

```text
new model files
isolated unit tests
debug/report draft plumbing
no production callsite migration
no blocking lint enable
```

---

### F1 DoD

```text
SemanticEvidence typed model exists
unit tests pass
text/name allowed_effect law tested
no production behavior changed
no new red gates
```

---

## B.2. E2 — Heuristics → Evidence

### Axis

```text
Architecture P0
```

### Goal

Migrate the system from:

```text
heuristic → production mutation
```

to:

```text
heuristic → SemanticEvidence → explicit gate → optional production effect
```

---

### Disease map

The problem crosses three layers:

```text
parser
reconcile
emit
```

Therefore E2 must cover all three.

---

### Parser problem zones

```text
parser/components.py
parser/tree.py
parser/interaction/forms.py
```

Problem examples:

```text
node.name contains role → semantic NodeType
node.text/hint indicates password → input behavior
status/home indicator name → system chrome role
```

---

### Reconcile problem zones

```text
generator/normalize.py
parser/layout/reconcilers_*
```

Problem examples:

```text
reconcile_consent_checkbox_rows_in_tree
reconcile_weekday_chip_row_in_tree
reconcile_payment_selection_state_in_tree
reconcile_playback_timestamp_row_in_tree
reconcile_auth_button_icon_placements_in_tree
```

Issue:

```text
archetype detector mutates geometry/layout
```

instead of:

```text
structural operator with provenance
```

---

### Emit problem zones

```text
generator/variant/state.py
generator/layout/widgets/emit/text.py
generator/layout/flex_policy/*
```

Problem examples:

```text
text/name → obscureText
font_size >= 24 → single-line
chrome/name/status → flex-wrap change
```

---

### E2 staged rollout

## E2a — Evidence alongside legacy

Add evidence production without removing legacy immediately.

```text
legacy behavior remains only where already baselined
no new production effects from text/name
new tests assert evidence creation
```

---

## E2b — No-new-text/name-production-effect lint

Draft a lint that rejects new direct production decisions from:

```text
node.text
node.name
text contents
layer name
copy string
```

in zones:

```text
parser semantic mutation
layout reconcilers
flex policy
variant state
emit policy
```

Allowed usage:

```text
construct SemanticEvidence
write debug/report
test evidence creation
```

Forbidden usage:

```text
change NodeType
change layout
change wrap
change variant state
change emitted widget behavior
```

---

## E2c — Critical callsite migration

Migrate in priority order:

```text
forms.py
wrap.py
row.py
stack.py
state.py
text.py
```

Expected transformations:

```text
password by text/hint
  → SemanticEvidence(candidate)
  → no obscureText unless gated source exists

system chrome by name
  → SemanticEvidence(candidate)
  → no layout/wrap effect unless gated source exists

headline by font-size
  → temporary no-op or existing legal behavior
  → later text metrics policy

chip/stepper/status/card by name/text
  → evidence only
  → no flex-wrap mutation
```

---

## E2d — Reconcile archetype burn-down

Replace archetype reconcilers with structural operators:

```text
group-by-row
group-by-grid
align-by-shared-parent-and-top
```

These operators may use:

```text
bounds
parent identity
paint order
top/left epsilon
overlap
spacing
size
layout constraints
```

They must not use:

```text
node.text
node.name
copy
locale-specific labels
screen archetype names
```

---

## E2e — Stop parser semantic overwrites

Longer-term migration:

```text
raw Figma type
  separate from
semantic evidence
```

`CleanDesignTreeNode.type` must stop being a sink for name-based semantic guesses.

---

### E2 rules

Forbidden:

```text
node.name contains "button" → NodeType.BUTTON
node.text contains "password" → obscureText=true
node.name contains "status bar" → layout/wrap change
font_size >= 24 → single-line policy
weekday labels → chip row mutation
payment copy → payment card state mutation
```

Allowed:

```text
node.name/text → SemanticEvidence(candidate)
geometry → structural grouping
component_property → possible gated source
manifest/corpus confidence → gated emit
```

---

### Tests

Add tests:

```text
text/name produces evidence only
candidate evidence has no production effect
gated evidence can affect output only through explicit policy
parser does not overwrite structural type from name hint
reconcile structural operator does not read text/name
```

---

### E2 DoD

```text
SemanticEvidence used in migrated callsites
no new text/name production effects
lint drafted and eventually blocking
semantics_legacy_burndown decreases by milestone
critical callsites migrated in stages
tests prove evidence-only behavior
no production shortcut introduced to save login visual
```

---

## B.3. E5 — Governance

### Axis

```text
P1/P2 validation and governance
```

### Goal

Make gates measure actual trust, not merely:

```text
known debt did not grow
```

---

### Problems

Current baseline gates may say green while:

```text
large accepted debt remains
advisory failures are hidden
corpus lacks diversity
recovery/downgrade is not named
reports overstate confidence
```

---

### Debt budget model

For every baseline-driven gate:

```text
settings_purity
regex_dart_surgery
semantics_legacy_burndown
```

track:

```text
current
target
delta
deadline
owner
```

---

### Budget rule

```text
current <= baseline
```

is not enough.

Need:

```text
current <= target_by_milestone
```

After deadline:

```text
fail if debt did not decrease
```

---

### Tier-aware reporting

Current risk:

```text
blocking_pass=True
```

can make a screen appear green even if advisory signal failed.

Required status model:

```text
strict_pixel_blocking:
  status = blocking_pass

advisory_pixel:
  status = advisory_pass
  label = ADVISORY_FAIL when failed

semantic_only:
  status = semantic/advisory status
  never pretend pixel blocking pass
```

---

### Recovery/downgrade reporting

Governance owns reporting shape for:

```text
filesystem asset recovery
polluted screen downgrade
missing vector degradation
layout reconcile mutation
```

These must appear in:

```text
debug report
release summary
audit output
```

---

### Corpus diversity quotas

Corpus should cover families, not just number of screens.

Required families:

```text
dirty names
localization
nested layout
semantic ambiguity
asset stress
keyboard/scroll
mirror/det<0
short input <48
complex vectors
missing assets
non-auth screens
```

---

### Allowed before Branch A green

```text
docs
schema drafts
non-blocking tests
report model drafts
budget config drafts
```

Forbidden before implementation is ready:

```text
turning new governance lints blocking
claiming release confidence from draft reports
```

---

### E5 DoD

```text
each baseline gate has budget + deadline
reports show current/target/delta/deadline
advisory failures visible
tier-aware status implemented
recovery/downgrade named in reports
corpus diversity quotas defined
CI/signoff reflects trust, not only no-new-debt
```

---

# Branch C — Preview Boundary & Named Degradation

## C.0. Branch summary

```text
Agent: Agent C
Mission: stop silent fallback and preview/oracle confusion
Epics:
  7. F2 — DeviationRecord
  8. E1 — Preview ≠ Oracle
  9. E3-full — Vector named degradation
```

Branch C отвечает за fact mutation provenance, preview boundary и full vector degradation.

---

## C.1. F2 — DeviationRecord

### Axis

```text
Foundation
```

### Goal

Introduce typed model for any fact mutation, degradation, or recovery.

---

### Model

```text
DeviationRecord:
  node_id
  field
  before
  after
  reason: enum
  source: pass/function
  severity: recoverable | degraded
  provenance
```

---

### Core law

```text
fact mutation
  => DeviationRecord required
```

No record:

```text
no mutation
```

---

### Reason enum candidates

```text
missing_vector_asset
filesystem_composite_icon_recovery
layout_pollution_tokens
invalid_screen_class
artboard_preview_leak
unsupported_visual_node
structural_grouping_reconcile
asset_recovery
fidelity_downgrade
```

---

### Severity

#### `recoverable`

Used when compiler recovers without intended fidelity loss:

```text
asset key discovered from filesystem
polluted screen replaced by existing deterministic delegate
structural grouping normalized with evidence
```

#### `degraded`

Used when fidelity is known to be lower:

```text
missing vector asset
unsupported visual node
placeholder in preview/debug
```

---

### Used by

```text
vector degradation
asset recovery
polluted screen downgrade
layout reconcile mutation
filesystem composite icon recovery
future geometry-preserving reconcile passes
```

---

### Placement

Preferred integration:

```text
generator/ir/passes/provenance_record.py
```

or adjacent module if current architecture requires.

Must not duplicate existing provenance recorder.

---

### Tests

Add mock tests:

```text
fact mutation requires record
degraded vector record serializes to debug report
filesystem recovery record uses recoverable severity
reason enum rejects free-text reasons
```

---

### Allowed before Branch A green

```text
new model files
mock tests
debug-report draft
no production migration
no dirty root modification without coordination
```

---

### F2 DoD

```text
DeviationRecord typed model exists
reason enum exists
unit tests pass
debug-report draft path exists
no production behavior changed
no new red gates
```

---

## C.2. E1 — Preview ≠ Oracle

### Axis

```text
Product P0
```

### Goal

Make:

```text
capture_with_mode(mode=PREVIEW)
```

the only entrypoint for interactive preview.

Preview must be fast, explicit, and separate from oracle/golden/combat render.

---

### Verified roots

```text
dev/view_renders.py:run_view_preview_capture
  → _capture_flutter_render_png
  → capture_planned_in_warm_sandbox
  → backend="flutter_test"

config/profiles.py:apply_interactive_preview_profile
  → return settings

combat render path:
  pulls Figma reference/diff
  can be perceived as preview
```

---

### Required mode split

#### `preview-capture`

```text
generated scene only
no Figma reference
no diff
no golden
no oracle
no flutter test
no pub get
no visual refine
no LLM repair
```

#### `combat-render`

```text
generated scene + Figma reference + diff
explicit user action
may be slower
not default preview
```

#### `oracle-capture`

```text
golden/corpus/blocking validation
explicit validation action
slow allowed
CI/signoff path
```

---

### Target zones

```text
src/figma_flutter_agent/dev/view_renders.py
src/figma_flutter_agent/wizard/debug.py
src/figma_flutter_agent/debug/capture.py
src/figma_flutter_agent/config/profiles.py
src/figma_flutter_agent/preview_capture/router.py
src/figma_flutter_agent/preview_capture/*
```

---

### `run_view_preview_capture`

Must route through:

```text
capture_with_mode(mode=CaptureMode.PREVIEW)
```

Must not call:

```text
_capture_flutter_render_png
capture_planned_in_warm_sandbox
capture_planned_flutter_golden_png
```

---

### `apply_interactive_preview_profile`

Scope:

```text
preview-only path
```

It must not silently weaken full generation/write validation unless command is explicitly preview-only.

For preview-only it must set behavior equivalent to:

```text
llm_visual_refine = false
runtime_geometry_gate = false
golden_capture = off
oracle = off
pub_get = off
flutter_test = off
llm_repair_after_analyze = off
default_capture_mode = preview
```

---

### `lint_preview_purity`

Draft before E0 green.

Enable as blocking only after E1 production switch.

Must forbid preview paths from calling:

```text
capture_planned_in_warm_sandbox
capture_planned_flutter_golden_png
flutter test
pub get
golden
oracle
backend="flutter_test"
```

Special rule:

```text
function/module/path contains preview
  ⇒ cannot stamp backend="flutter_test"
```

---

### Browser/static preview backend

If backend already exists:

```text
verify it is reachable from real preview callsites
```

If not complete:

```text
prepare minimal browser/static scene capture
```

Preview unavailable behavior:

```text
raise FastPreviewUnavailableError
```

Forbidden:

```text
fallback to flutter_test
```

---

### Tests

Add tests:

```text
preview path does not call flutter_test
preview path does not call pub_get
preview path does not write golden
preview path uses capture_with_mode(PREVIEW)
preview unavailable raises FastPreviewUnavailableError
combat render still allowed explicitly
oracle capture still allowed explicitly
```

---

### E1 DoD

```text
all wizard/dev/debug preview callsites route through capture_with_mode(PREVIEW)
no warm sandbox in preview
no flutter_test backend in preview metadata
no pub_get/golden/oracle/diff/visual_refine in preview
lint_preview_purity blocking and green
combat/oracle explicit paths still work
```

---

## C.3. E3-full — Vector named degradation

### Axis

```text
P1 fidelity hardening
```

### Goal

Implement full named degradation for missing vector assets using DeviationRecord.

E3-full happens after Branch A’s E3-lite has stopped the red lint.

---

### Required behavior

For:

```text
VECTOR without vector_asset_key/path
```

production must not silently emit:

```text
Container(width, height, color)
```

Instead:

```text
diagnostic: missing_vector_asset
severity: degraded
DeviationRecord emitted
debug-report visible
```

---

### Production policy

Production fidelity path may do one of:

```text
emit real asset
emit supported vector path
fail/degrade with named diagnostic
use explicit degraded policy with DeviationRecord
```

It may not:

```text
invent rectangle
hide missing export
pretend fidelity is preserved
```

---

### Preview/debug policy

Preview/debug may use a placeholder if:

```text
placeholder is visibly diagnostic
DeviationRecord exists
metadata says degraded
not used as oracle/golden truth
```

---

### Tests

Add tests:

```text
missing vector emits DeviationRecord(reason=missing_vector_asset)
missing vector does not emit Container fallback in production
preview placeholder is allowed only in preview/debug mode
production path records degraded severity
debug report contains vector degradation
```

---

### E3-full DoD

```text
no silent vector→Container fallback
DeviationRecord emitted for missing vector
debug report shows degradation
preview/debug placeholder policy explicit
production path does not invent geometry
lint_dart_in_python remains green
```

---

# 7. Integration boundaries

## 7.1. Branch A ↔ Branch B

Branch A may temporarily remove shortcuts.

Branch B later reintroduces useful signals only as:

```text
SemanticEvidence
```

Branch B must not ask Branch A to preserve illegal behavior for visual quality.

---

## 7.2. Branch A ↔ Branch C

Branch A handles E3-lite:

```text
stop red lint
remove silent fallback
```

Branch C handles E3-full:

```text
DeviationRecord
debug report
placeholder policy
named degradation
```

Branch C must not modify `svg.py` before Branch A green without coordination.

---

## 7.3. Branch B ↔ Branch C

Branch B owns semantic evidence.

Branch C owns deviation records.

They meet at:

```text
reconcile mutation
asset recovery
downgrade reporting
debug reports
governance summaries
```

Rule:

```text
SemanticEvidence explains why compiler believes something.
DeviationRecord records what compiler changed or degraded.
```

---

# 8. Acceptance matrix

| Branch   | Local acceptance                                               | Merge acceptance                                    |
| -------- | -------------------------------------------------------------- | --------------------------------------------------- |
| Branch A | 6 lint gates + targeted tests                                  | full pytest or CI proof                             |
| Branch B | unit tests for models/lints + no new red gates                 | after E0, staged migrations with gates green        |
| Branch C | unit tests for DeviationRecord/preview lint + no new red gates | after E0, production preview switch with lint green |

---

# 9. Detailed priority map

|  # | Epic                       | Branch |        Priority | Blocks merge |  Can start before E0 green |
| -: | -------------------------- | ------ | --------------: | -----------: | -------------------------: |
|  1 | E0 Unblock merge           | A      |              P0 |          yes |                        yes |
|  2 | E3-lite Vector red lint    | A      |              P0 |          yes |                        yes |
|  3 | E4 Compiler purity         | A      |              P1 |    partially | yes, scoped to materialize |
|  4 | F1 SemanticEvidence        | B      |      Foundation |           no |                        yes |
|  5 | E2 Heuristics → Evidence   | B      | Architecture P0 |           no |        planning/model only |
|  6 | E5 Governance              | B      |           P1/P2 |           no |           docs/schema only |
|  7 | F2 DeviationRecord         | C      |      Foundation |           no |                        yes |
|  8 | E1 Preview ≠ Oracle        | C      |      Product P0 |           no |                  prep only |
|  9 | E3-full Vector degradation | C      |              P1 |           no |                design only |

---

# 10. Final execution order

```text
Parallel start:

Agent A:
  E0 + E3-lite
  materialize settings leak minimal-correct

Agent B:
  F1 SemanticEvidence
  E2 lint/design
  E5 governance schema

Agent C:
  F2 DeviationRecord
  E1 callsite inventory + lint draft
  E3-full degradation design
```

```text
After Agent A green:

Agent C:
  E1 production switch
  enable lint_preview_purity
  E3-full vector degradation

Agent B:
  E2 staged migration
  E5 governance implementation

Agent A:
  E4 full compiler purity completion
```

---

# 11. Final DoD for the whole Codex Hardening split

The split is complete when:

```text
E0:
  gates green
  no new baselines
  no shortcut tests

E1:
  preview never reaches flutter_test/warm sandbox

E2:
  text/name is evidence only, not production authority

E3:
  missing vector is named degradation, not rectangle invention

E4:
  deterministic compiler failures do not go to LLM/analyzer first

E5:
  reports show trust/debt honestly, not only no-new-debt
```

---

# 12. One-line mission per agent

```text
Agent A:
  stop the bleeding.

Agent B:
  stop heuristic-as-knowledge.

Agent C:
  stop silent fallback and preview/oracle confusion.
```
