# 09 — Hierarchical visual oracle & stage attribution

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Golden capture | `validation/golden_capture/`, `validation/compare.py` |
| Visual refine | `stages/visual_refine.py` |
| Oracle | `validation/oracle/` — `profile_compare.py`, `promotion_evidence.py` |
| Geometry metrics | `validation/geometry_metrics.py` |
| Design coverage | debug writer → `.debug/screen/*/design_coverage.json` |
| Contract vs emit diff | `.debug/screen/*/contract_emit_diff.json`, `contract_emit_diff.md` |
| Semantics JSON | `.debug/screen/*/semantics.json` |
| Spec23 eval | `validation/spec23/evaluate.py` |
| Fidelity report | `generator/ir/fidelity/report.py` |

### Тесты

- `tests/test_fixture_screen_golden.py`, `tests/test_corpus_oracle_*.py`
- `tests/test_golden_capture_assets.py`

---

## 2. Анализ

### Иерархия oracle

```text
screen → regions → components → primitives
```

Метрики по отдельности: recall, bbox error, alignment, text metrics, color, z-order, clipping.

### Stage attribution map (пример)

| Symptom | Likely stage |
|---------|----------------|
| missing icon | asset resolution / extraction closure |
| wrong position | grouping / layout inference |
| wrong size | geometry / constraint routing |
| wrong color | paint / a11y mutation |
| collapsed region | ownership / parent selection |

### Вопросы

- IoU-only gate что ловит / пропускает?
- Когда oracle blocking vs advisory (corpus-oracle signoff)?
- Как связать pixel defect с `provenance.json`?

### Гипотезы

- Stage attribution сократит «чиним emitter, болел parser».
- Hierarchical metrics стабильнее full-screen IoU.

### Сомнения

- Attribution без probabilistic model — rule-based first, ML later never.

---

## 3. Рефакторинг

### Целевое состояние

- `refactor/oracle/ATTRIBUTION.md` — symptom → stage → law lookup.
- Report: per-region scores + suggested stage, не один diff PNG.
- CI: blocking structural oracle; golden optional tier per bible §24.
- Visual refine = search over **compiler transforms**, не ad-hoc LLM Dart.

### Критерии готовности

- Diagnose skill использует attribution table.
- ≥10 symptoms mapped с regression fixture.
- food/home/transaction testbed: oracle report без ручного triage > 50% полей.
