# EPIC 5.W1 — MVP Semantic Components (first mergeable slice)

> Status: **in progress**

## Purpose

First mergeable slice of EPIC 5: prove semantic classification is **safer** than legacy heuristics
for eight MVP widget kinds, with FP-first corpus gates before widening native emit.

Parent umbrella: [semantic-core.md](semantic-core.md) EPIC 5.

## E5 Scope and Wave Acceptance

E5 is an umbrella epic for semantic component rollout and legacy heuristic burn-down.

E5 must not be merged as one large W1→W4 batch. Each wave is an independently mergeable slice with its own:

- detector contract;
- typed payload;
- template or explicit fallback;
- positive corpus;
- negative/adversarial corpus;
- classification report;
- fidelity manifest entries;
- legacy heuristic burn-down list;
- precision/false-positive gates.

The first mergeable E5 slice is **E5.W1** only.

W2–W4 remain planned follow-up waves and must not block W1 merge unless W1 introduces architecture that makes later waves impossible.

## E5.W1 Precision Gate

W1 target kinds:

- `BUTTON_FILLED`
- `BUTTON_OUTLINED`
- `BUTTON_TEXT`
- `INPUT_TEXT_FIELD`
- `CHIP_CHOICE`
- `CONTAINER_CARD`
- `CONTAINER_LIST_TILE`
- `TECHNICAL_DIVIDER`

W1 merge gate:

| Metric | Gate |
| --- | ---: |
| Overall precision on W1 positive corpus | `>= 0.95` |
| Per-kind precision | `>= 0.90` |
| Recall on W1 positive corpus | `>= 0.80` |
| Blocker negative false positives | `0` |
| Full-tree unexpected W1 semantic nodes | `0` |
| Semantic no-op before verified emit | required |
| Classification report generated | required |
| New legacy `looks_like_*` outside semantic detector package | `0` |
| New Dart-in-Python emitter debt | `0 new fingerprints` |
| Native emit without `native_verified` manifest tier | forbidden |

Precision definition:

```text
precision = true_positive / (true_positive + false_positive)
```

Recall definition:

```text
recall = true_positive / (true_positive + false_negative)
```

Policy:

```text
False positive blocks merge.
False negative creates backlog.
```

## W1 kind inventory

| Kind | Detector | Template | Manifest tier | Legacy deps |
| --- | --- | --- | --- | --- |
| `BUTTON_FILLED` | `detectors/actions.py` | `button_filled.dart.j2` | `native_verified` | `interaction/buttons.py` (burn) |
| `BUTTON_OUTLINED` | `detectors/actions.py` | `button_outlined.dart.j2` | `native_unverified` | `interaction/buttons.py` (burn) |
| `BUTTON_TEXT` | `detectors/actions.py` | `button_text.dart.j2` | `native_unverified` | `interaction/buttons.py` (burn) |
| `INPUT_TEXT_FIELD` | `detectors/inputs.py` | `input_text_field.dart.j2` | `native_unverified` | — |
| `CHIP_CHOICE` | `detectors/actions.py` | `chip_choice.dart.j2` | `native_verified` | `interaction/chips.py` (burn) |
| `CONTAINER_CARD` | `detectors/display.py` | `container_card.dart.j2` | `native_unverified` | — |
| `CONTAINER_LIST_TILE` | `detectors/display.py` | `container_list_tile.dart.j2` | `native_unverified` | — |
| `TECHNICAL_DIVIDER` | `detectors/display.py` | `technical_divider.dart.j2` | `native_unverified` | — |

Out of W1 gate (remain in codebase): `NAV_SCROLL_HOST`, `BUTTON_ICON`, `NAV_BOTTOM_BAR`.

## Three-phase pipeline

### Phase 1 — Safety net

- W1 corpus manifest + `>= 3` positives per kind
- `parser/semantics/metrics.py` aggregator
- `figma-flutter semantics corpus-gate` CLI + signoff wire
- Semantic no-op oracle on W1 subset
- `semantics.report_only: true` stays default

**Stop-gate:** blocker-negative FP = 0; metrics module + CLI exist.

### Phase 2 — Emit completeness

- `BUTTON_OUTLINED` / `BUTTON_TEXT` in `SEMANTIC_MVP_IR_KINDS`
- Jinja templates + fidelity manifest rows
- 0 new lint fingerprints

**Stop-gate:** templates compile; corpus gate still green.

### Phase 3 — Legacy burn-down

- `signals/chip_anatomy.py` decouples chip detector from lexicon
- Burn W1 overlap in `buttons.py`, `auth_buttons.py`, `emit/controls.py`
- `docs/figma-feature-coverage.md` (W1 rows)
- `logs/semantics/legacy_burndown.json` in signoff

**Stop-gate:** full W1 merge gate table; no `parser/interaction` imports from `parser/semantics/detectors/`.

## Legacy burn-down allowlist

| Module | W1 kinds | Action | Target PR |
| --- | --- | --- | --- |
| `parser/interaction/chips.py` | `CHIP_CHOICE` | Shim → `chip_anatomy` → delete lexicon path | W1 Phase 3 |
| `parser/interaction/buttons.py` | `BUTTON_*` | Shrink W1-overlapping predicates | W1 Phase 3 |
| `generator/subtree/auth_buttons.py` | `BUTTON_*` | Geometry-only social row; no button heuristics | W1 Phase 3 |
| `generator/layout/widgets/emit/controls.py` | `BUTTON_*` | Drop `interaction.buttons` for W1 paths | W1 Phase 3 |

## S5.1 — Full-tree FP audit

Target-level `run_case()` checks only `target_figma_id`. S5.1 adds a full IR-tree audit:

| Field | Meaning |
| --- | --- |
| `allowed_semantic_target_ids` | Per-fixture figma ids allowed to carry a W1 semantic kind |
| `unexpected_semantic_nodes` | W1 kinds on any other node in the classified tree |
| `full_tree_semantic_fp_count` | `len(unexpected_semantic_nodes)` |

Gate: `unexpected_semantic_nodes == 0` (release-blocking).

Positive fixtures: allowed set = `{target_figma_id}`; any other W1 kind in the tree is unexpected.

Trap fixtures: scan the full tree for kinds in `forbidden_kinds`. Structural neighbors
(e.g. outlined buttons inside a size-picker row) are not flagged unless they match a
forbidden kind. `require_zero_semantic` traps reject any W1 kind anywhere.

## S5.1 — Real-design corpus (deferred to E6)

Synthetic unit gate stays in S5.W1 (`positive/` programmatic builders).

**Real-design W1 corpus** is **S6.1.W1** under [epic-6-corpus-oracle.md](epic-6-corpus-oracle.md):

- >=10 real W1 cases, >=5 real negative traps
- Same semantic gates (`unexpected_semantic_nodes == 0`, blocker FP = 0)
- Pixel oracle tags: `semantic_only` | `advisory_pixel` | `strict_pixel_blocking`

Do not expand `w1.real_design_cases` in the S5 manifest as a release blocker; E6 owns offline Figma dumps.

## Usage

```bash
poetry run figma-flutter semantics corpus-gate --write-report logs/semantics/w1_classification_gate.json
poetry run figma-flutter fidelity validate
poetry run pytest -q tests/test_semantics_w1_metrics.py tests/test_semantics_noop_w1.py -m "not live_figma"
```

## Non-goals (W1)

- W2–W4 kinds and overlay research spike
- Full E6 corpus (>= 25 fixtures) as W1 blocker
- `geometry_primitive` pixel-safe fallback tier
- Global `semantics.report_only: false` flip
- Removing entire `parser/interaction/` package
