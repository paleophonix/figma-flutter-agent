# 03 — Classification theory (abstain, evidence, gates)

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Semantic detectors | `parser/semantics/detectors/` — `controls.py`, `inputs.py`, `navigation.py`, `actions.py`, `overlays.py`, `display.py`, `registry.py` |
| Signals / anatomy | `parser/semantics/signals/` — `anatomy.py`, `geometry.py`, `chip_anatomy.py`, `type_trust.py`, `properties.py` |
| Arbiter / classify | `parser/semantics/arbiter.py`, `classify.py`, `prefilter.py` |
| Models / report | `parser/semantics/models.py`, `report.py`, `metrics.py`, `corpus.py` |
| Interaction heuristics | `parser/interaction/forms.py`, `input_fields.py`, `inline_input_hosts.py`, `selection.py` |
| IR semantic passes | `generator/ir/passes/semantic.py`, `presence/semantics.py`, `presence/kinds.py` |
| Policy gate | `generator/ir/passes/policy.py`, `fidelity/promote.py`, `fidelity/baked_gate.py` |
| Contracts | `generator/ir/contracts/`, `semantic_emit.py` |
| Root kind veto | `generator/ir/validate/root_kind.py` |
| LLM rules | `llm/prompts/` — systemic bug registry |
| Audit overlap | `audit/predicate_matrix.py` |

### Тесты

- `tests/test_cp_post_classify.py`
- `tests/test_semantics_sectionized_root.py`
- `tests/test_screen_root_nav_kind_laws.py`
- `tests/fixtures/semantics/`

### Debug

- `.debug/screen/*/semantic_verdicts.json`, `semantic_context.json`, `element_contracts.json`

---

## 2. Анализ

### Что проанализировать

Для каждого contract kind (checkbox, input, button, nav_bar, tabs, segmented_control, …):

- **minimal structural evidence** — что лицензирует kind;
- **anti-evidence** — что должно veto (icon → input, arrow → checkbox, artboard → nav);
- confidence / abstain threshold;
- путь: `detector → verdict → policy → emit` (где сейчас emit обходит gate).

### Вопросы

- Почему одни и те же структуры дают FP и FN на разных экранах?
- Где production emit идёт от name/text regex (запрещено bible)?
- Classification vs `parser/interaction/*` — дублирование или слои?

### Гипотезы

- Abstain-by-default + structural evidence снимет top bleed без новых predicates.
- FP и FN — одна теория: недокалиброванный evidence graph.

### Сомнения

- Слишком жёсткий abstain даст «пустые» экраны без fallback tier.
- Нужен явный structural fallback (Container/Stack), не silent wrong widget.

---

## 3. Рефакторинг

### Целевое состояние

- Playbook: kind → required signals → veto signals → gate policy (report | fidelity | emit).
- `SemanticVerdict` не может напрямую менять emit без `PolicyDecision.allow`.
- Detectors возвращают evidence node ids, не только label.
- Corpus тест на FP/FN pairs из программы 00.

### Критерии готовности

- Top-5 misclassification families из corpus имеют written evidence spec.
- ≥1 тест на FP veto и ≥1 на FN recall per kind.
- Predicate overlap matrix: нет двух winning detectors на одном node без arbiter rule.
