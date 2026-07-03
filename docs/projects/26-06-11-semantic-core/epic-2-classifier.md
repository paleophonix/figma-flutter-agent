# EPIC 2 — Semantic Classifier

**Source:** [semantic-core.md](semantic-core.md) (EPIC 2)  
**Prerequisite:** [epic-1-pass-manager.md](epic-1-pass-manager.md)

## Pipeline seam

```
normalize → validate → apply_ir_layout_passes (CP2 layout)
  → apply_ir_classification_passes (CP2 semantic)
  → run_cp_post_classify (CP2b)
  → pre_emit snapshot → emit (report_only gate until E3)
```

See [epic-2.5-safety.md](epic-2.5-safety.md) for the safety envelope (`report_only`, classification report, LLM gray-zone OFF).

**Pass contract (`classify_screen_ir`):**

| Mutates | Preserves |
|---------|-----------|
| `screen_ir.kind`, `screen_ir.payload`, consumes `classification_hint` | multiset, stack paint order, graph sync, style, geometry (no child flattening in E2) |

**Overlay rollback:** `OVERLAY_*` kinds require tier-1 overlay signal (`NodeType.DIALOG` or variant overlay metadata); otherwise rollback to `auto`.

## Wave checklist

### Wave 2a — Schema + config + PassManager hook

- [x] `schemas/ir_payloads.py` — `KindPayload`, `LlmClassificationHint`
- [x] `SemanticsSettings` in `config/models.py`
- [x] `SEMANTIC_PASSES` + `apply_ir_classification_passes`
- [x] Wired in `generator/ir/materialize.py` after layout passes
- [x] `test_semantics_materialize.py`

### Wave 2b — Semantics core

- [x] `parser/semantics/` — models, signals (3 tiers), prefilter, arbiter, classify
- [x] `record_decision` on accepted classifications
- [x] `test_semantics_arbiter.py`

### Wave 2c — Detectors (full registry)

- [x] `parser/semantics/detectors/` — inputs, actions, controls, navigation, display, overlays
- [x] `test_semantics_registry.py` — all `SEMANTIC_IR_KINDS` covered

### Wave 2d — LLM migration (E2.5)

- [x] Prompt: `classificationHint` only (no authoritative `kind`)
- [x] `sanitize_screen_ir_semantic_kinds` when `authoritative_classifier: true`

### Wave 2e — Corpus + lint + signoff

- [x] `tests/fixtures/layouts/semantics/` positive + negative traps
- [x] `parser/semantics/corpus.py` + `test_semantics_corpus.py`
- [x] `test_semantics_name_lint.py`
- [x] Classification report artifact: `.debug/classification_report.json`

## Verification

```bash
poetry run pytest tests/test_semantics_*.py tests/test_pass_manager.py -q
poetry run pytest -q -m "not live_figma"
```
