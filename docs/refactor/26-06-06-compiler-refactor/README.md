# RAR — Research, Analysis & Refactoring

Программы рефакторинга компилятора Figma → Flutter. Каждый файл — отдельный трек с тремя разделами:

1. **Исследование** — связанные модули и артефакты (точки входа для агента).
2. **Анализ** — что измерить, вопросы, гипотезы, сомнения.
3. **Рефакторинг** — целевое состояние и критерии готовности.

Практический поток `/diagnose` → `/repair` кормит corpus (программа 00). Теоретический поток превращает families в laws и удаляет compensator-слой.

## Порядок работ

| Фаза | Файл | Приоритет |
|------|------|-----------|
| 0 | [00_defect-taxonomy-corpus.md](00_defect-taxonomy-corpus.md) | P0 — данные |
| 1 | [01_compiler-semantics-ir-contract.md](01_compiler-semantics-ir-contract.md) | P0 |
| 1 | [02_conservation-framework.md](02_conservation-framework.md) | P0 |
| 2 | [03_classification-theory.md](03_classification-theory.md) | P1 |
| 2 | [04_extraction-dedup-bijection.md](04_extraction-dedup-bijection.md) | P1 |
| 3 | [05_visual-ownership-layout-inference.md](05_visual-ownership-layout-inference.md) | P1 |
| 3 | [06_geometry-constraint-algebra.md](06_geometry-constraint-algebra.md) | P1 |
| 4 | [07_decorative-primitive-fidelity.md](07_decorative-primitive-fidelity.md) | P2 |
| 4 | [08_property-based-testing.md](08_property-based-testing.md) | P2 |
| 4 | [09_hierarchical-visual-oracle.md](09_hierarchical-visual-oracle.md) | P2 |
| 5 | [10_provenance-cache-determinism.md](10_provenance-cache-determinism.md) | P2 |

## Связь с кодом

- Источник правды по путям: `src/figma_flutter_agent/`, `tests/`, `.debug/screen/`, `AGENTS.md`.
- Старые markdown-спеки в `docs/` — справочно; для RAR не использовать как primary map.
- **Системный промпт агента:** [AGENT_SYSTEM_PROMPT.md](AGENT_SYSTEM_PROMPT.md)
- **Карта проекта (модули и файлы):** [PROJECT_MAP.md](PROJECT_MAP.md)
- **Program 01 — ТЗ под Cursor:** [01_refactoring-spec-cursor.md](01_refactoring-spec-cursor.md)
- **Program 02+03 — ТЗ под Cursor:** [02-03-refactoring-spec-cursor.md](02-03-refactoring-spec-cursor.md)
- **Согласование 00 ↔ 01:** [00-01-cursor-alignment.md](00-01-cursor-alignment.md)
- **Матрица стрелок (contract):** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md)
