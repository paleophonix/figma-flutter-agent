# 08 — Property-based & metamorphic testing

**Статус:** исследование завершено 2026-07-03; реализация в бэклоге.

## 1. Исследование

### Проверенный baseline

| Область | Путь | Состояние |
|---------|------|-----------|
| Fixture corpus | `tests/fixtures/screens.yaml`, `fixtures/` | Реальные screen fixtures |
| Conservation harness | `tests/test_conservation_harness.py`, `tests/support/conservation.py` | Проверки multiset и z-order |
| Layout combinatorics | `tests/test_layout_combinatorics.py` | Несколько ручных clean-tree fixtures |
| Geometry invariants | `tests/test_geometry_constraint_algebra.py` | Metamorphic CENTER/SCALE через pytest |
| Oracle | `validation/oracle/` | Проверяет corpus, но не создаёт новые структуры |
| Dependencies | `pyproject.toml` | Библиотека Hypothesis не подключена |

### Находки

1. Каталога `tests/synthetic/` нет.
2. Генераторы деревьев сейчас локальны отдельным тестам и не переиспользуются.
3. Conservation harness уже даёт основу для structural oracles.
4. Geometry algebra уже показывает рабочий пример metamorphic tests.
5. Нет автоматического уменьшения failing case, replay metadata и отдельного CI tier.
6. Текущие тесты хорошо удерживают известные regressions, но почти не перебирают неизвестные сочетания depth, overlap, reuse и sizing.

### Полезные преобразования

| Преобразование | Инвариант |
|----------------|-----------|
| Переименование незначимых layer ids/names | Решение компилятора не меняется |
| Дублирование reusable instance | Одна definition, новый call-site |
| Изменение parent extent | CENTER/SCALE laws сохраняются |
| Перестановка независимых siblings | Multiset и допустимый порядок сохраняются |
| Inline и extracted представления | Сохраняются обязательные contracts |

---

## 2. Анализ

### Рекомендуемый порядок

1. Создать deterministic builders на уровне `CleanDesignTreeNode`.
2. Вынести transforms и preconditions в `tests/synthetic/`.
3. Подключить существующие conservation laws как oracles.
4. Сохранять минимальный counterexample с `law_id`, исходным tree и compiler versions.
5. Только после стабилизации builders решить, нужна ли библиотека Hypothesis.

Первый слой не должен генерировать raw Figma JSON: это смешает ошибки parser и compiler core. Raw-input testing можно добавить отдельным последующим tier.

### Первый blocking набор

- rename no-op;
- duplicate reusable instance;
- CENTER/SCALE resize;
- cycle-safe traversal;
- permutation независимых non-overlapping siblings.

### CI

- PR: небольшой фиксированный набор воспроизводимых cases;
- signoff: corpus плюс выбранные generated cases;
- nightly: расширенный перебор после измерения runtime и flake rate.

---

## 3. Рефакторинг

### Целевое состояние

- `tests/synthetic/` содержит builders, transforms, preconditions и law oracles.
- Каждый conservation law имеет хотя бы один metamorphic test.
- Каждый failure сохраняется как воспроизводимый JSON artifact.
- Production counterexample после минимизации становится обычным regression test.
- Golden не используется как обязательный oracle для structural properties.

### Критерии готовности

- Не менее трёх metamorphic tests входят в blocking CI.
- Один минимизированный case воспроизводит реальную defect family.
- Failure повторяется по сохранённому artifact без нового перебора.
