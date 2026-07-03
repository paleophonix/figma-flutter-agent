# 10 — Provenance, cache & determinism

## 1. Исследование

### Модули

| Область | Путь |
|---------|------|
| IR / parser version | `generator/ir/version.py`, `parser/version.py` |
| Provenance models | `generator/ir/passes/provenance_models.py`, `provenance_record.py` |
| Sync / incremental | `sync/snapshot.py`, `diff.py`, `regions.py` |
| Dump prefetch | `pipeline/dump_prefetch.py` — `ScreenDumpPrefetch` |
| Pipeline stages | `pipeline/run/stages.py`, `pipeline/run/fetch.py` |
| Planner timing | `generator/planner/timing.py` |
| Config hash surface | `config/` — `Settings`, `.ai-figma-flutter.yml` |
| Debug provenance | `.debug/screen/*/provenance.json`, `snapshot.json` |
| LLM cache / IR offline | wizard ir-offline paths, `llm_parsed.json` |
| Asset index | `parser/boundaries/assets.py` — `build_asset_node_index` |
| EMITTER_VERSION | grep in `src/` (emitter version stamps) |

### Инциденты (из практики)

- Stale `plan.dart` при hung run.
- Cached IR переживает parser semantics change.
- `main.dart wired: mismatch` — wizard bootstrap.

---

## 2. Анализ

### Идентичность артефакта

Каждый cache key должен включать:

```text
source dump hash
parser version
normalizer version
IR schema version
config hash
asset-manifest hash
upstream artifact hashes
```

### Вопросы

- Где cache keyed by filename, не content?
- Когда ir-offline должен invalidate?
- Stage budgets: hang без timeout — какой max per substage?

### Гипотезы

- `AssetIndexReuseLaw` — частный случай general «scan once» policy.
- Provenance.json не участвует в invalidation — bug.

### Сомнения

- Byte-identical emit при LLM — нереалистично; IR determinism достаточен.

---

## 3. Рефакторинг

### Целевое состояние

- Content-addressed artifact store под `.debug/screen/` + explicit stale markers.
- Invalidation: parser/IR version bump → force regen IR, не reuse `llm_validated.json`.
- Plan substage budgets: log + fail loud после threshold (не silent hang).
- Determinism gate: same inputs + versions → same `pre_emit.json` hash.

### Критерии готовности

- Hung run невозможен без `plan: <stage> started` + timeout error.
- Documented cache key schema в `refactor/contracts/artifact_identity.md`.
- Wizard ir-offline detects stale IR и предлагает refresh.
