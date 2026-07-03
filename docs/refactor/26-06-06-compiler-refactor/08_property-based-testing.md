# 08 — Property-based & metamorphic testing

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| Fixture corpus | `tests/fixtures/screens.yaml`, `fixtures/` |
| Conservation harness | `tests/test_conservation_harness.py`, `tests/support/conservation.py` |
| Layout combinatorics | `tests/test_layout_combinatorics.py` |
| Oracle gate | `validation/oracle/runner.py`, `evaluator.py` |
| Corpus semantics | `parser/semantics/corpus.py` |
| Golden (expensive) | `validation/golden_capture/`, `scripts/generate_fixture_goldens.py` |
| Hypothesis (if used) | grep `hypothesis` in `pyproject.toml` / tests |

### Существующие metamorphic идеи (ручные)

- Rename layers → semantics unchanged
- Duplicate component instance → same widget class
- Reorder independent siblings → pixel equivalent

---

## 2. Анализ

### Что строить

- Synthetic Figma tree generator (depth, overlap, reuse knobs).
- Property tests на conservation laws (программа 02).
- Shrinking: минимальный counterexample на fail.
- Differential: deterministic vs LLM path; inline vs extracted widget.

### Вопросы

- Где hypothesis уже есть, где pytest parametrize достаточно?
- Какой бюджет runtime для CI (100 vs 10k trees)?
- Synthetic trees валидны для parser или только для clean tree layer?

### Гипотезы

- Shrunk counterexample даст быстрее insight чем 100 golden PNGs.
- Metamorphic rename-id ловит asset-key coupling bugs.

### Сомнения

- Synthetic ≠ real Figma mess — нужен mix с corpus fixtures.

---

## 3. Рефакторинг

### Целевое состояние

- `tests/synthetic/` — tree builder + strategies (depth, fanout, overlap).
- Каждый conservation law → ≥1 property test.
- CI tier: fast (100 trees) on PR; nightly (10k) optional.
- Failed property → artifact в `.temp/` с shrunk tree JSON.

### Критерии готовности

- ≥3 metamorphic tests в CI blocking.
- Один shrunk bug из synthetic воспроизводит production family.
- Golden count не растёт для закрытия structural bugs.
