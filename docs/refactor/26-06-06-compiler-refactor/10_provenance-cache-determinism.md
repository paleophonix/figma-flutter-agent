# 10 — Provenance, cache & determinism

**Статус:** исследование завершено 2026-07-03; реализация в бэклоге.

## 1. Исследование

### Проверенные модули

| Область | Путь |
|---------|------|
| Parser / emitter versions | `parser/version.py`, `generator/ir/version.py` |
| IR snapshots | `debug/ir_dumps.py`, `debug/ir_load.py` |
| Provenance | `debug/provenance.py`, `generator/ir/passes/provenance_models.py`, `provenance_record.py` |
| Incremental state | `sync/snapshot.py`, `sync/diff.py`, `sync/regions.py`, `pipeline/incremental.py` |
| Dump prefetch | `pipeline/dump_prefetch.py` |
| Planner timing | `generator/planner/timing.py` |

### Находки

- Processed dump знает `PARSER_VERSION`; cached IR эту версию не проверяет.
- `pre_emit` и sync snapshot знают `EMITTER_VERSION`.
- Snapshot уже хранит hashes дерева, токенов, generated files, regions и clusters.
- В общей идентичности пока нет normalizer version, IR schema version, settings fingerprint и asset-manifest fingerprint.
- Dump prefetch сопоставляет только путь к файлу.
- Planner timing пишет start/finish и duration, но не имеет stage budget.
- Provenance объясняет изменения полей, однако отдельно от жизненного цикла snapshot/IR artifacts.
- Atomic snapshot write, lock, optimistic version и quarantine уже реализованы и должны быть сохранены.

### Вывод

В проекте есть отдельные механизмы versioning, provenance и incremental state, но нет единого `ArtifactIdentity`, который одинаково применяется к processed dump, cached IR, pre-emit и snapshot.

---

## 2. Анализ

### Приоритеты

1. Описать typed `ArtifactIdentity`.
2. Проверять cached IR перед использованием.
3. Добавить признак полного завершения producer stage.
4. Учитывать содержимое dump, settings и asset manifest.
5. Ввести stage budgets и typed diagnostics.
6. Проверять стабильность canonical `pre_emit.json` при одинаковых входах и версиях.

### Граница детерминизма

Нормативная цель — одинаковый canonical pre-emit для одинаковых normalized inputs, versions и settings. Byte-identical final Dart для LLM-assisted path не является первым gate.

### Scope

Visual refine не входит в Program 10 и остаётся в backlog.

---

## 3. Рефакторинг

### Целевое состояние

- Одна identity model для reusable artifacts.
- Несовместимая версия или settings/assets change дают явный stale verdict.
- Незавершённый stage не создаёт пригодный для повторного использования artifact.
- Planner substages имеют duration, budget и typed failure report.
- Same identity даёт одинаковый canonical pre-emit.

### Критерии готовности

- Cached IR с несовместимой identity не загружается молча.
- Version change требует regeneration.
- Settings или asset change обновляют зависимые artifacts.
- Identity schema описана в `contracts/artifact_identity.md`.
- Determinism test не зависит от visual refine.
