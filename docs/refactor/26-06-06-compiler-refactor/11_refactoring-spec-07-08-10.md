# Техническое задание на рефакторинг — Programs 07, 08, 10

**Версия:** 1.3 — consilium final (approved)  
**Дата:** 2026-07-03  
**Статус:** утверждено к поинкрементной реализации  
**Milestone:** M4  
**Аудитория:** разработчик, coding agent, reviewer, владелец продукта

> **Полный текст v1.2** — см. секции ниже. Changelog v1.1→v1.2: split `10-P0-1a/b/c`, `run.meta.json`, soft vs hard budgets, stroke **audit** before fix, `08-P0-0` parallel, M2 evidence variants A/B, PR discipline §13, stable laws §6, rename metamorphic refined §9.5.  
**Источники:** `07_decorative-primitive-fidelity.md`, `08_property-based-testing.md`, `10_provenance-cache-determinism.md`  
**Consilium:** analysis + task breakdown от peer review (2026-07-03)  
**Связанные контракты:** `contracts/PIPELINE_ARROWS.md`, `contracts/artifact_identity.md` (10-P0-3), `contracts/decorative_primitive.md` (07-P0-1)

**Вне scope:** программа 09.

**Сквозной тезис:** **07 unify · 08 build · 10 harden.** Все три встраиваются в M2/M3, conservation registry, corpus — без новых фреймворков.

---

## 1. Цель

| Программа | Действие | Результат |
|-----------|----------|-----------|
| **10** | harden | Composite identity для кэша; fail-loud budgets; post-LLM determinism gate |
| **08** | build | `tests/synthetic/` + properties над prog 02 laws |
| **07** | unify | `DecorativePrimitiveContract` вместо 10+ локальных копий plate⊕glyph |

**Блокер M3:** `FIGMA_M3_AUTHORITY_ENABLED` off до M2 signoff; modes `shadow` / `off`.

---

## 2. Peer review — принятые уточнения

### 07 — Decorative primitive

| Вопрос | Вердикт (код подтверждён) |
|--------|---------------------------|
| Где теряется plate? | **`collapse_render_boundaries` → `should_collapse_boundary`** (`parser/boundaries/collapse.py`, `heuristics.py`). Multiset-safe (`flatten_figma_node_ids`), но **role-blind**. Второй путь: `assets/composite_icons.py` — bake by design. |
| Stroke lost где? | **Asset stage.** Parser: stroke в `styles.py`, `forms.py`, `icons.py`… **0 hits в `assets/`**. Fix → exporter, не parser. |
| T1/T2 boundary? | `route_with_policy` + `baked_gate` есть; решение **per-node**, не per-role. Glyph raster + plate Container — в contract. |
| Text raster | Вне icon contract (`text_policy.py` отдельно). |

### 08 — Property-based

| Вопрос | Вердикт |
|--------|---------|
| hypothesis vs parametrize? | parametrize для матриц; **hypothesis только с `tests/synthetic/`** (shrink). Dev dep — при P0-1, не раньше. |
| CI budget | PR: **100–200 trees**, conservation only, <60s; nightly: 10k + differential. Golden вне property tier. |
| Synthetic layer | **Clean-tree only** — generalization существующих hand-built `CleanDesignTreeNode` тестов. |
| Corpus mix | Strategies seeded from `.debug` stats (depth/fanout/overlap) + corpus fixtures blocking. |

### 10 — Provenance & cache

| Вопрос | Вердикт |
|--------|---------|
| Filename vs content? | `sync/` уже content-hash. **Реальный баг:** `screen_ir_cache_fingerprint` = cleanTreeHash + root id/type/size — **без parser/IR schema/config**. |
| ir-offline invalidate | На mismatch: cleanTreeHash \| PARSER_VERSION \| IR schema \| config hash \| asset-manifest hash. |
| Stage budgets | `planner/timing.py` — telemetry only; **timeout отсутствует**. |
| provenance.json в cache key? | **Нет (advisory).** В determinism gate (same inputs → same provenance hash), не в invalidation. |
| LLM determinism | Boundary post-LLM: same validated IR + versions + config → same `pre_emit.json` hash. |

---

## 3. Ограничения

1. Anti-patching (screen / figmaId / text / asset filename).
2. Settings только на pipeline boundary.
3. Golden PNG не растим для structural bugs.
4. provenance.json **не** в cache key.
5. Byte-identical Dart с LLM — не gate.

**Corpus tags (prog 00)** на каждую закрытую family: `stale_ir_replay`, `plan_stage_hang`, `stroke_lost_on_export`, `rename_variance`, `role_blind_collapse`.

---

## 4. Program 10 — harden

**ROI:** highest per line. Первый инкремент эпика.

### P0

| ID | Task | Files | DoD |
|----|------|-------|-----|
| **10-P0-1** | IR fingerprint + **`PARSER_VERSION` + IR schema version + generation-config hash** | `debug/ir_cache.py`, `assert_cached_screen_ir_compatible`, write path in `ir_cache_metadata_for_write` | version/config bump → reject `llm_validated.json`; missing stamps = stale; wizard ir-offline: typed error + «refresh IR»; regression test |
| **10-P0-2** | Stage budgets on `plan_substage_*` wraps | `generator/planner/timing.py`, `plan.py` | soft WARN → hard `GenerationError` after cap (`FIGMA_PLAN_SUBSTAGE_TIMEOUT_S`); hung run always has `plan: <stage> started` + timeout name |
| **10-P0-3** | Cache-key schema doc | `contracts/artifact_identity.md` | table: artifact → fields → consumer; gaps marked vs live code |

### P1

| ID | Task | Files | DoD |
|----|------|-------|-----|
| **10-P1-1** | Post-LLM determinism gate | `tests/test_pre_emit_determinism.py` or fixture hook | same IR dump + versions + config → same `pre_emit.json` hash (2 fixtures, CI) |
| **10-P1-2** | Provenance layer merge | `passes/provenance_models.py`, `provenance_record.py` → `debug/provenance.py` facade | one recorder; import re-exports; tests green |
| **10-P1-3** | Provenance determinism (advisory) | `debug/provenance.py` | double run → same mutation-set hash; report-only |
| **10-P1-4** | Plan lifecycle + prefetch content hash | `pipeline/helpers.py`, `dump_prefetch.py`, `session_reset.py` | stale `plan.dart` marked/removed until `final`; prefetch compares raw hash |

### P2

| ID | Task | DoD |
|----|------|-----|
| **10-P2-1** | Scan-once policy (AssetIndex + font registry + dump prefetch) | one pattern, three instances |
| **10-P2-2** | Stale markers: `run.meta.json` extension (run-id, status) | wizard warns on stale leftovers |

**Defer:** full content-addressed `.debug/` store; `artifact_identity.py` module — после P0-3 doc, по необходимости P1.

---

## 5. Program 08 — build

**Зависимость:** 10-P0-1 желателен до properties, использующих cached IR paths.

### P0

| ID | Task | Files | DoD |
|----|------|-------|-----|
| **08-P0-1** | `hypothesis` dev dep + `tests/synthetic/strategies.py` | `pyproject.toml`, `tests/synthetic/` | recursive `CleanDesignTreeNode` strategy (depth, fanout, overlap, stack/flex); 100 trees pass validation; deterministic seed in CI |
| **08-P0-2** | First 3 conservation properties | `tests/synthetic/test_conservation_properties.py` | multiset after merge; graph_sync after reconcile; paint order after passes; PR 100 trees <60s; shrink → `.temp/conservation-shrink-<law>.json` |
| **08-P0-3** | Metamorphic **rename-invariance** | `tests/synthetic/test_metamorphic.py` | rename all layer ids/names → classification/verdicts unchanged; targets name-derived-truth ban |
| **08-P0-4** | **`LAW-CP1-TYPE-TRUTH` closure** | `tests/test_type_truth_conservation.py` | positive + negative + legacy permit path (registry gap) |

### P1

| ID | Task | DoD |
|----|------|-----|
| **08-P1-1** | +2 metamorphic: duplicate→same widget class; reorder→paint order preserved | 3 metamorphic blocking total (with P0-3) |
| **08-P1-2** | Differential: deterministic vs IR path, same tree, conservation equal | divergence → shrunk artifact |
| **08-P1-3** | Corpus-seeded strategy distributions from `.debug` stats | documented source in `tests/synthetic/README.md` |

### P2

| ID | Task | DoD |
|----|------|-----|
| **08-P2-1** | Nightly 10k + emit-compile sampling | optional CI job |
| **08-P2-2** | One shrunk synthetic → prog 00 production family case | готовности doc 08 closed |

**Markers:** `property_fast` in signoff; `property_nightly` excluded.

**Forbidden:** property tests call LLM; golden in property tier.

---

## 6. Program 07 — unify

**Зависимость:** 08-P1-1 helpful for resize-parent metamorphic; not blocking P0.

### P0 — contract + verified leaks

| ID | Task | Files | DoD |
|----|------|-------|-----|
| **07-P0-1** | `DecorativePrimitiveContract`: roles (substrate, glyph, stroke, badge) + bounds + flatten legality. **Report-only** | `generator/ir/contracts/decorative.py`, `contracts/decorative_primitive.md` | roles on fixture composites in `design_coverage.json` / provenance; **zero emit diff** |
| **07-P0-2** | Stroke on export: asset stage reads parsed stroke | `assets/exporter.py`, `assets/composite_icons.py` | stroked icon: stroke in SVG or named deviation; regression test |
| **07-P0-3** | Role-preserving collapse: record role map before `should_collapse_boundary` flatten | `parser/boundaries/collapse.py`, `heuristics.py` | collapsed composite retains substrate/glyph role map; test |

### P1 — per-role fidelity + emit guards

| ID | Task | Files | DoD |
|----|------|-------|-----|
| **07-P1-1** | T1/T2 **per role**: glyph bake, plate styled Container | `fidelity/router.py`, `baked_gate.py` | filtered-glyph fixture; downgrade with provenance |
| **07-P1-2** | Emit guard: no flatten plate+glyph without flatten fact | `layout/widgets/emit/dispatch.py` | DP-1 regression (complements P0-3) |
| **07-P1-3** | Generalize R6/R8 laws; delete subsumed local copies | `layout/navigation/`, `interaction/forms.py` | **≥5 tests:** plate, glyph center, stroke, fit, color ≠ bg-merge — `tests/test_decorative_plate_glyph_laws.py` |

### P2

| ID | Task | DoD |
|----|------|-----|
| **07-P2-1** | Concept-spread ratchet (plate/glyph term baseline) | local reimplementations only ↓ |
| **07-P2-2** | Corpus icons family frequency ↓ | prog 00 advisory metric |

**Forbidden:** text policy in icon contract; per-screen icon fixes; collapse without flatten fact.

---

## 7. Execution order (ROI)

```text
1. 10-P0-1   IR fingerprint (+3 fields)     ~20 LOC, kills stale_ir_replay
2. 10-P0-2   stage budgets                  kills plan_stage_hang
3. 10-P0-3   artifact_identity.md           doc + gap table
4. 07-P0-2   stroke on export               verified 0-hit assets gap
5. 08-P0-1   synthetic + hypothesis
6. 08-P0-2   first conservation properties
7. 08-P0-3   rename metamorphic
8. 08-P0-4   TYPE-TRUTH tests
── P1 wave ──
9.  10-P1-1  pre_emit determinism gate
10. 07-P0-1  decorative contract report-only
11. 07-P0-3  role map on collapse
12. 08-P1-1  duplicate + reorder metamorphic
13. 07-P1-1  per-role fidelity (after 07-P0-1)
14. 07-P1-2/3 emit guard + 5 law tests
── P2 ── optional / burn-down
```

**Первый инкремент для merge:** `10-P0-1` + tests + wizard message.

---

## 8. Сводный checklist

### 10
- [ ] 10-P0-1 IR fingerprint
- [ ] 10-P0-2 stage budgets
- [ ] 10-P0-3 artifact_identity.md
- [ ] 10-P1-1 pre_emit determinism
- [ ] 10-P1-2 provenance merge
- [ ] 10-P1-4 plan lifecycle + prefetch hash

### 08
- [ ] 08-P0-1 synthetic strategies
- [ ] 08-P0-2 conservation properties (×3)
- [ ] 08-P0-3 rename metamorphic
- [ ] 08-P0-4 TYPE-TRUTH
- [ ] 08-P1-1 duplicate + reorder
- [ ] 08-P1-2 differential
- [ ] property_fast in signoff

### 07
- [ ] 07-P0-1 contract report-only
- [ ] 07-P0-2 stroke export
- [ ] 07-P0-3 role map collapse
- [ ] 07-P1-1 per-role fidelity
- [ ] 07-P1-2 dispatch guard
- [ ] 07-P1-3 five law tests

---

## 9. Signoff критерии эпика

- Doc 10 готовности: hung run + timeout ✓; cache schema ✓; ir-offline stale ✓
- Doc 08 готовности: ≥3 metamorphic blocking ✓; shrunk→family ✓; golden flat ✓
- Doc 07 готовности: contract + ≥5 tests ✓; corpus icons ↓ advisory
- `./scripts/signoff.ps1` green
- M2 closure остаётся PENDING

---

## 10. Расхождения v1.0 → v1.1 (audit trail)

| Было (v1.0) | Стало (v1.1, consilium) |
|-------------|-------------------------|
| Plate drop = dispatch only | **Primary: `collapse.py` role-blind flatten** + dispatch guard P1 |
| Stroke в общем emit | **Explicit: assets exporter P0** |
| Фазы A→B→C строго | **ROI order: 10-P0 → 07-P0-2 → 08-P0** |
| `parser/layout/plate_glyph.py` | **`generator/ir/contracts/decorative.py`** |
| provenance в identity stamp | **provenance = determinism gate, not cache key** |
| Full `artifact_identity.py` в P0 | **Doc P0-3; module defer P1** |
| TYPE-TRUTH (наш gap) | **08-P0-4 explicit** (peer не назвал) |

---

## 11. Артефакты

| Артефакт | Путь |
|----------|------|
| Artifact identity | `contracts/artifact_identity.md` |
| Decorative contract | `contracts/decorative_primitive.md` |
| Decorative model | `generator/ir/contracts/decorative.py` |
| Synthetic | `tests/synthetic/` |
| Law tests | `tests/test_decorative_plate_glyph_laws.py`, `tests/synthetic/test_metamorphic.py`, `tests/test_type_truth_conservation.py` |
