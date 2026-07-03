# 00 — Defect taxonomy & diagnose corpus

## 1. Исследование

### Модули и точки входа

| Область | Путь |
|---------|------|
| Debug-артефакты экрана | `.debug/screen/<project>/<feature>/` — `last.log`, `dart-errors.json`, `semantic_verdicts.json`, `contract_emit_diff.md`, `provenance.json`, `design_coverage.json` |
| Доктрина triage | `.cursor/rules/debug-context.mdc`, `.claude/prompts/debug-common.md` |
| Skills diagnose/repair | `.claude/skills/diagnose/SKILL.md`, `.claude/skills/repair/SKILL.md` |
| Fidelity / coverage | `src/figma_flutter_agent/debug/fidelity.py`, `generator/ir/fidelity/` |
| Oracle / corpus gate | `src/figma_flutter_agent/validation/oracle/` |
| Audit overlap | `src/figma_flutter_agent/audit/predicate_matrix.py`, `audit/docs.py` |
| Fixture manifest | `tests/fixtures/screens.yaml` |
| Emit-law tests (примеры families) | `tests/test_*_emit_laws.py`, `tests/test_conservation_*.py` |
| OpenCode repair prompts | `.opencode/prompts/`, `.opencode/skills/` |

### Артефакты для mining

- `.debug/screen/**/last.log` — stage + stack
- `semantic_verdicts.json`, `element_contracts.json` — classification FP/FN
- `contract_emit_diff.json` — emit vs contract
- `logs/figma_flutter_agent.log` — plan substage timing (после H3)

---

## 2. Анализ

### Что измерить

- Частота family по экранам и по стадии pipeline (`parse` … `visual`).
- Blast radius: crash vs visual-only vs silent wrong emit.
- Корреляция family с compensator-кодом (archetype predicates, reconcile passes).
- Доля `COMPILER` vs `SOURCE` vs `AMBIGUOUS` (пока эвристически, потом формально).

### Вопросы

- Какие 5 families дают 80% `/repair` времени?
- Какие families уже закрыты named law, но без corpus-записи?
- Где один симптом маскирует два root cause (например hang = asset scan + cycle)?

### Гипотезы

- Classification FP и extraction/desync — top-2 по frequency × blast.
- Golden-only тесты не покрывают families с «правильным скриншотом, неправильной семантикой».

### Сомнения

- `.debug` неполон на hung runs (нет `last.log`) — нужен fallback на global log.
- Ручная разметка family субъективна без чеклиста стадий.

---

## 3. Рефакторинг

### Целевое состояние

- Живая таблица `corpus/families.yaml` (или JSON): id, stage, law_candidate, screens, status.
- Каждый `/diagnose` → одна строка в corpus (автоматически или полуавтоматически).
- Ranked backlog: `frequency × blast_radius` обновляется после каждого repair batch.
- Теги defect origin: `COMPILER | SOURCE | AMBIGUOUS | UNSUPPORTED | FIDELITY_DEFERRED`.

### Критерии готовности

- Top-10 families задокументированы с ≥2 независимыми примерами.
- Приоритет программ 01–10 выведен из таблицы, не из intuition.
- Новый `/repair` без family tag считается незавершённым.
