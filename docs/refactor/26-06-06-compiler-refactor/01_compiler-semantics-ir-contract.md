# 01 — Compiler semantics & UI IR contract

## 1. Исследование

### Цепочка компиляции

```text
Figma API / dump
  → parser/ (clean tree)
  → llm/ + generator/ir/ (screen IR, widget IR)
  → generator/normalize.py
  → generator/planner/plan.py
  → generator/ir/emitter.py + generator/layout/
  → validation/ + golden capture
```

### Модули

| Слой | Путь |
|------|------|
| Parse → clean tree | `parser/tree.py`, `parser/geometry.py`, `parser/tree_node.py`, `parser/render_bounds.py` |
| Truth snapshot | `parser/truth_snapshot.py` |
| Screen / widget IR | `generator/ir/screen.py`, `tree.py`, `materialize.py`, `extracted.py` |
| IR validate | `generator/ir/validate/` — `__init__.py`, `root_kind.py`, `graph.py`, `guards.py` |
| IR passes | `generator/ir/passes/` — `manager.py`, `registry.py`, `semantic.py`, `sync.py`, `geometry.py` |
| Normalize | `generator/normalize.py` |
| LLM structured output | `llm/`, `llm/prompts/` (`SYSTEMIC_BUG_RULES`) |
| Schemas | `schemas/` — `CleanDesignTreeNode`, IR models |
| Provenance (зачатки) | `generator/ir/passes/provenance_models.py`, `provenance_record.py` |
| Fidelity manifest | `generator/ir/data/fidelity_manifest.yaml`, `fidelity_manifest.py` |
| IR version | `generator/ir/version.py` |

### Тесты

- `tests/test_ir_layout_passes.py`, `tests/test_extracted_ir_emit.py`
- `tests/test_screen_root_nav_kind_laws.py`
- `tests/test_ir_tree_unique_ids.py`

### Debug

- `.debug/screen/*/raw.json`, `processed.json`, `pre_emit.json`, `llm_parsed.json`, `llm_validated.json`

---

## 2. Анализ

### Что проанализировать

Для каждой стрелки `A → B` в цепочке:

- **preserved** — поля, которые обязаны пережить переход;
- **inferred** — что добавляется без Figma fact;
- **lossy** — что теряется намеренно;
- **illegal** — мутации, которые запрещены без provenance.

Приоритетные стрелки:

1. `clean tree → screen IR` (LLM + materialize)
2. `screen IR → normalize_clean_tree`
3. `clean tree + IR → emitter Dart`
4. `parse → clean tree` (geometry truth)

### Вопросы

- Где LLM может **переписать** geometry, которую clean tree уже зафиксировал?
- Какие поля IR — intent, а какие — cache of facts?
- Нужен ли lens `parse → emit → inspect` для выборочных truths?

### Гипотезы

- Большинство «emitter bugs» — information-loss на стрелке 1–2.
- `ensure_ir_direct_children_match_clean` и подобные — симптом отсутствия явного contract.

### Сомнения

- Полный formal contract на весь IR сразу — слишком тяжёлый; нужен incremental по family.
- Screen IR и widget IR могут требовать разных preservation rules.

---

## 3. Рефакторинг

**Исполняемое ТЗ (Cursor workflow):** [01_refactoring-spec-cursor.md](01_refactoring-spec-cursor.md)  
**Матрица стрелок:** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md)

### Целевое состояние

- Документ `refactor/contracts/PIPELINE_ARROWS.md` (или YAML): матрица полей по стрелкам.
- Каждый IR pass регистрирует: `reads`, `writes`, `must_preserve`.
- LLM output = **proposals**; deterministic layer = **commit** только после validate.
- Violation → `GenerationError` с named law, не silent mutate.

### Критерии готовности

- Стрелки 1–3 описаны с примерами counterexample из corpus (программа 00).
- ≥3 regression tests: «поле X не исчезает после pass Y».
- Новый IR pass без записи в contract matrix — reject в review.
