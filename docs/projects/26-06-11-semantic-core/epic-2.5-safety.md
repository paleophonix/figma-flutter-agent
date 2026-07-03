# EPIC 2.5 — Safety Envelope

**Source:** [semantic-core.md](semantic-core.md) (EPIC 2.5)  
**Prerequisite:** [epic-2-classifier.md](epic-2-classifier.md)

## Architecture (Variant B)

Three-layer envelope: **type truth** → **pipeline seam** → **emit gate** → **observability**.

```
normalize → validate/guards → layout_passes → classification_passes
  → CP2_post_classify → pre_emit snapshot → emit (report_only gate)
```

## Config

```yaml
semantics:
  enabled: true
  report_only: true                    # default until E3
  llm_gray_zone_annotations: false     # default
  confidence_threshold: 0.8
  grey_zone_min: 0.5
  authoritative_classifier: true
```

## Wave checklist

### Wave 2.5-0 — Emit gate (E2.5-D / E2.5-I)

- [x] `SemanticsSettings.report_only: true` default
- [x] `expression.py` — `_semantic_mvp_emit_enabled(ctx)` gate
- [x] `IrEmitContext.semantic_report_only` override for tests
- [x] `tests/test_semantics_emit_gate.py`

### Wave 2.5-1 — Classification report (E2.5-E)

- [x] `parser/semantics/report.py` — full bucket schema
- [x] `debug/semantics.py` — `.debug/semantics/<feature>.json`
- [x] Wired in `generator/ir/passes/semantic.py`
- [x] `tests/test_semantics_report_snapshot.py`

### Wave 2.5-2 — LLM gray-zone OFF (E2.5-F)

- [x] `llm_gray_zone_annotations: false` default
- [x] `classify_screen_ir` / sanitize respect flag
- [x] `tests/test_semantics_llm_gate.py`

### Wave 2.5-3 — Post-classification conservation (E2.5-H)

- [x] `run_cp_post_classify` in `checkpoints.py`
- [x] `check_ir_classification_scope` / `check_clean_tree_unchanged`
- [x] Wired in `materialize.py`
- [x] `tests/test_cp_post_classify.py`

### Wave 2.5-4 — Type truth (E2.5-A / E2.5-C)

- [x] `inv_type_truth` in `conservation.py` / `models.py`
- [x] `set_parse_type_baseline` post-parse
- [x] Legacy provenance via `note_legacy_semantic_type`
- [x] `tests/test_type_mutation_lint.py`

### Wave 2.5-5 — Guard provenance (E2.5-B)

- [x] `record_mutation` for min touch, nested scroll, keyboard scroll, row flex, viewport clamp
- [x] `tests/test_guard_provenance.py`

### Wave 2.5-6 — Negative corpus + manifest (E2.5-J)

- [x] 5 traps under `tests/fixtures/layouts/semantics/negative/`
- [x] `manifest.yaml` detector → trap mapping
- [x] `tests/test_semantics_detector_manifest.py`

### Wave 2.5-7 — Vocabulary markers + docs (E2.5-G)

- [x] `signalSource: legacy_interaction` in anatomy signals
- [x] `legacySemanticTypeDetected` / `nameSignalUsed` in report
- [x] This document + epic-2-classifier patch

## Verification

```bash
poetry run pytest tests/test_semantics_emit_gate.py tests/test_semantics_report_snapshot.py \
  tests/test_semantics_llm_gate.py tests/test_cp_post_classify.py tests/test_type_mutation_lint.py \
  tests/test_guard_provenance.py tests/test_semantics_corpus.py tests/test_semantics_detector_manifest.py -q
poetry run pytest tests/test_conservation_invariants.py tests/test_pass_manager.py -q
```

## Emit rule — outer gate (E2.5; retained in E3)

`generator/ir/expression.py` — today semantic MVP emit runs only when `_semantic_mvp_emit_enabled(ctx)` is true (`report_only=false`):

```text
if ir.kind in SEMANTIC_MVP_IR_KINDS and _semantic_mvp_emit_enabled(ctx):
    semantic_emit(...)    # E3.5 adds inner fidelity_tier router here — see epic-3-emit.md
else:
    render_node_body(...)
```

**E3 contract (Variant B, locked):** `report_only` is the **outer master kill-switch** (global). E3.5 adds an **inner per-node router** on `fidelity_tier` — **AND** composition, not a replacement. Do not collapse the two axes. See [epic-3-emit.md](epic-3-emit.md).
