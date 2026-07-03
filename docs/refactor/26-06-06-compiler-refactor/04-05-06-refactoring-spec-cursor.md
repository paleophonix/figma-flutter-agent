# ТЗ: Program 04 + 05 + 06 — Extraction bijection, geometry algebra, visual ownership (Cursor workflow)

**Программы:** [04_extraction-dedup-bijection.md](04_extraction-dedup-bijection.md), [05_visual-ownership-layout-inference.md](05_visual-ownership-layout-inference.md), [06_geometry-constraint-algebra.md](06_geometry-constraint-algebra.md)  
**Стыковка:** [00-01-cursor-alignment.md](00-01-cursor-alignment.md) · [02-03-refactoring-spec-cursor.md](02-03-refactoring-spec-cursor.md) (Milestone 2 — prerequisite)  
**Контракт стрелок:** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md) · Cursor: `.cursor/rules/pipeline-contracts.mdc`  
**Статус:** consilium-approved v2 — Milestone 3 (Programs 04–06); поправки №1–№9 внесены  
**Аудитория:** агент / инженер в Cursor, владелец продукта (обзор инкрементов)  
**Architecture RFC:** [04-06-architecture-spec.md](04-06-architecture-spec.md) (non-normative)  
**Contracts:** [geometry_algebra.md](contracts/geometry_algebra.md) · [cluster_signature.md](contracts/cluster_signature.md) · [layout_hypothesis.md](contracts/layout_hypothesis.md)  
**M2 closure gate:** [generated/m2-closure-record.md](generated/m2-closure-record.md)

---

## 1. Цель

Устранить **три класса silent wrong behavior**, которые M2 не покрывает:

| Program | Вопрос | Blast |
|---------|--------|-------|
| **04** | Каждый cluster call-site имеет ровно одно определение виджета? | B2 — wrong `Cluster*Widget`, empty body, hang на plan |
| **06** | Constraint facts и emit slots — одна алгебра или две правды? | B2/B3 — wrong pin/center, slot loss, replan-маскировка |
| **05** | Кто владеет surface/content/chrome до emit? | B2 — layout «чинят» 570 if/elif вместо ownership |

**Совместный тезис 04 + 05 + 06:**

```text
Figma parent tree  ≠  cluster equivalence  ≠  visual ownership  ≠  constraint algebra
```

Пока графы не формализованы и не связаны conservation laws — emitter остаётся компенсатором.

**Не цель M3:**

- Полный constraint solver (CSS-level).
- Переписать все 17 reconcile passes за один PR.
- Full MDL / beam search по всему дереву (только tiered chooser на ambiguous subtrees).
- Golden refresh / fleet regen всех экранов (smoke + corpus only).
- Screen/`figmaId`/path-specific patches.

---

## 2. Scope

### In scope

| Track | Стрелки | Код / артефакты |
|-------|---------|-----------------|
| **06** Geometry algebra contract | parse → plan → IR → replan | `parser/geometry_frames.py`, `generator/geometry/`, `parser/layout/placement.py` |
| **06** Top-3 geometry families | CP1, plan, emit | `geometry/invariants/`, emit laws tests |
| **04** Cluster signature spec | parse, plan | `parser/dedup/signatures.py`, `contracts/cluster_signature.md` |
| **04** Bijection gate | plan, materialize | `widget_extractor.py`, `cluster_subtree.py`, `delegate_repair.py` |
| **04** Asset index reuse | plan, assets | `cluster_variants.py`, `boundaries/assets.py`, `stages/assets.py` |
| **05** Visual ownership edges | parse → normalize | новый pass / enrich в `parser/` или `parser/boundaries/` |
| **05** Layout hypothesis scorecard | IR ambiguous only | `layout_criteria.py`, `contracts/layout_hypothesis.md` |
| **05** Reconcile conflict registry | normalize | `reconcile_registry.py` |
| **00** Corpus | — | новые `family_id`, FIXED cases |

### Out of scope (Milestone 3)

| Тема | Когда |
|------|-------|
| Full extractor bijection proof (все widget paths) | **04-P2** |
| Убить `replan_geometry_after_layout_passes` полностью | **06-P2** (после incremental slot on pass contract) |
| Замена всего `flex_policy` на chooser | **05-P2** |
| `semantic_conflict_without_arbiter_rule` | **03-P1** (уже в M2 defer) |
| CP3_post_emit formal runner | **M3.1** unless audit escape |

### Зависимости

| Prerequisite | Статус |
|--------------|--------|
| Milestone 2 (02 + 03) — executable registry, PolicyDecision, shadow ratchet, omission contract | **required** |
| Program 01 IR pass contract | **готово** |
| Program 00 corpus CLI | **готово** |

### Порядок треков (обязательный)

```text
06-P0 (contract + 3 laws)  ──┐
04-P0 (cluster bijection)   ──┼── parallel OK
                              ↓
05-P0 (ownership + chooser) ── only after 06-P0-0 contract merged
```

**05 без 06** — запрещён merge в `main` (ownership без algebra = новый if/elif слой).

---

## 3. Baseline (после Milestone 2)

| Артефакт | Путь | Пробел |
|----------|------|--------|
| Cluster signature | `parser/dedup/signatures.py` | нет contract; coarse merge (status bar ↔ tab bar) |
| Bijection | `widget_extractor.py`, `cluster_classes` dict | topology split → last wins; empty representative |
| Cycle guard | `tree_walk.py` | dedup/prune/hydrate без visited |
| Asset index | `normalize.py` | plan/assets paths без index reuse |
| Geometry facts | `stack_placement`, `geometry_frame`, `layout_slot` | две правды + replan |
| Replan | `replan_geometry_after_layout_passes` | симптом double truth |
| Layout decisions | 17 reconcile + 4 IR passes + flex_policy | нет ownership graph; нет scorecard |
| Hero reconcile | `reconcile_product_hero_photo_viewport_in_tree` | вне registry runner |
| Contracts | `contracts/cluster_signature.md`, `geometry_algebra.md`, `layout_hypothesis.md` | **отсутствуют** |

---

## 4. Воркфлоу в Cursor

### 4.1 Поток

```text
/diagnose → /repair     compiler (layout, cluster, geometry families)
/debug → /fix           infra — не этот ТЗ
```

### 4.2 Старт сессии

```text
.cursor/rules/project-bible-lite.mdc
.cursor/rules/pipeline-contracts.mdc
docs/refactor/04-05-06-refactoring-spec-cursor.md
docs/refactor/contracts/PIPELINE_ARROWS.md
corpus/families.yaml
AGENTS.md
```

### 4.3 Жёсткие правила

- **Anti-patching:** никаких screen/feature/`figmaId`/golden-specific веток.
- Новый reconcile pass **без** `conflicts_with` + `priority` в registry — не merge (после **05-P0-2**).
- Absolute→flow transform **без** `DeviationRecord` / pass provenance — не merge (после **06-P0-2**).
- Cluster `cluster_id` → **один** widget class mapping; split variants → distinct cluster keys или explicit bijection table.
- Dedup/prune/hydrate walks **только** через `walk_clean_tree` или эквивалент с `CleanTreeCycleError`.
- `preserve_placement` = named fidelity downgrade; не маскировать как success без provenance stamp.
- Settings только на boundary pipeline (`PassContext`, `IrEmitContext`) — не `load_settings()` внутри compiler.

---

## 5. Инкременты

### Merge order (после M2 на `main`)

```text
Commit 0 (docs-only): 04-05-06-refactoring-spec-cursor.md + contract stubs (empty headers OK)
  ↓
06-P0-0  geometry_algebra.md contract
  ↓
04-P0-0  cluster_signature.md contract     } parallel
  ↓
06-P0-1 … 06-P0-3  ||  04-P0-1 … 04-P0-4
  ↓
05-P0-0 … 05-P0-3
  ↓
M3 signoff
```

---

### Track 06 — Geometry constraint algebra

#### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **06-P0-0a** | **Raw constraint consumer inventory + ratchet** (поправка №4). Machine-readable список всех прямых чтений raw строк (`"LEFT_RIGHT"`, `"TOP_BOTTOM"`, `"SCALE"`). Verified baseline: **11 файлов** (reconcilers_align/media, placement, positioned/text/svg/position emit, responsive, slots, validate/graph, schemas/types) | `docs/refactor/generated/constraint-consumers.json`, `tests/test_constraint_consumer_ratchet.py` | CI: новый direct read → FAIL; удаление → ALLOW; существующий → временно ALLOW. Паттерн M2 shadow ratchet |
| **06-P0-0b** | Contract: types (constraint op, static edge, resolved pin), legal transforms, viewport regions | `docs/refactor/contracts/geometry_algebra.md` | Parser facts vs planner slots vs emit law — одна таблица; replan documented as compensator |
| **06-P0-1** | **Law 1:** wrong pin/center. Typed **`AxisConstraint(op, start_offset, end_offset, size, center_delta, scale_offset_ratio, scale_size_ratio)`** (поправка №5 — параметризованная операция, не голый enum; raw `horizontal`/`vertical` остаются для compatibility/audit; аддитивно, ноль output-изменений в первом commit) + authoritative resolver `resolve_constraint_axis`. В P0 мигрируют только authoritative consumers: planner/slots, `validate/graph.py`, positioned emit; остальные — под ratchet | `schemas/geometry.py`, `generator/geometry/slots.py`, `parser/layout/placement.py`, `tests/test_layout_constraints.py` | bell / center constraint family FIXED case; round-trip raw↔typed; inventory count ↓ |
| **06-P0-2** | **Law 2:** absolute→flow slot loss — named transform + provenance on parser reconcile clamp | `parser/layout/placement.py`, `sectionize.py` audit | FID-26 class: flatten must not drop absolute slot without deviation |
| **06-P0-3** | **Law 3:** viewport/chrome partition — region owner field on clean tree (`layout_region` or equivalent) | `viewport_inset.py`, `stack_chrome.py`, IR guards | bottom nav + tall scroll body laws green; documented in contract |

**06-P0 verify:**

```powershell
poetry run pytest tests/test_geometry_invariants.py tests/test_layout_constraints.py tests/test_placement_conservation.py tests/test_sectionize_root_pass.py tests/test_light_theme_06_emit_laws.py tests/test_transaction_income_emit_laws.py tests/test_planner_corpus_gate.py -q
poetry run figma-flutter defects validate
```

#### P1

| ID | Задача | DoD |
|----|--------|-----|
| **06-P1-1** | Scoped replan c **dependency closure** (поправка №8): dirty IDs → nearest planning roots → ancestor/descendant closure → subtree replan → **equivalence compare с full replan**. Touched IDs недостаточно (child меняет parent flex, siblings' gaps, ancestor extent, viewport partition). Full replan остаётся CP2 safety oracle до доказанной equivalence (вкл. late product-hero reconcile) | equivalence test green на fixtures; plan time ↓ на macro screens; full replan НЕ удалён |
| **06-P1-2** | `preserve_placement` provenance stamp in `DeviationRecord` | report names downgrade tier |
| **06-P1-3** | Corpus families: `wrong_pin_center`, `absolute_slot_loss`, `viewport_partition_drift` | 3 FIXED synthetic cases |

**Responsive MVP (определение, поправка №9):** fixed structural topology + per-axis parent-relative constraints (pin start/end, stretch, center, per-axis scale, viewport pin) + explicit adaptive rules only. Uniform whole-screen scale — это увеличение фотографии, не сохранение constraints; **не MVP**. Automatic breakpoint topology rewrite — out of scope.

#### P2

- Partial zone solver (bands) for ambiguous stacks — hypothesis doc only until corpus proves need.
- Remove `replan_geometry_after_layout_passes` when P1 incremental covers WAVE_1 passes.

---

### Track 04 — Extraction & dedup bijection

#### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **04-P0-0** | Contract: signature fields, discriminators, component vs structural cluster, prune/hydrate bijection | `docs/refactor/contracts/cluster_signature.md` | explicit IN/OUT of hash; asset ownership on prune |
| **04-P0-1** | **Discriminator pass** before structural bucket (role band: chrome / icon-row / content) — не только тоньше hash | `parser/dedup/clusters.py` или sibling `discriminators.py` | test: status bar ≠ tab bar на synthetic fixture |
| **04-P0-2a** | **Ранний bijection gate** (поправка №1): `ExtractionPlan` validation call-site ↔ definition **до** render Dart → typed `ExtractionBijectionError`. `PlannedDartGraph` не перегружать extraction-корректностью | `widget_extraction/collect.py` / новый `validate.py`, `errors.py` | missing/duplicate definition пойман pre-render; `delegate_repair` `SizedBox.shrink()` surgery не достигается на fixture |
| **04-P0-2b** | `PlannedDartGraph` остаётся финальным projection gate (imports/classes/files closure), без новых обязанностей | — (guard test) | regression: planned-graph gate unchanged |
| **04-P0-2c** | **Topology variant identity — silent wrong widget, P0** (поправка №3). Verified last-wins `{spec.cluster_id: spec.class_name}` на **двух** сайтах: `widget_extractor.py:391` и `subtree/render.py:42`. `DefinitionKey` различает topology variants; lookup не через `dict[cluster_id]` для split family | `widget_extractor.py`, `generator/subtree/render.py`, `cluster_variants.py` | два topology groups одного cluster → distinct authoritative keys; callsite → конкретный variant; regression: no last-wins на обоих сайтах; empty body closed |
| **04-P0-3** | All dedup/asset walks on `walk_clean_tree`; budget test plan normalize | `prune.py`, `hydrate.py`, `clusters.py`, `assets.py` | `CleanTreeCycleError` on malformed tree; N=500 M=200 smoke < 30s |
| **04-P0-4** | Asset `build_asset_node_index` на plan/asset finalize paths | `cluster_variants.py`, `stages/assets.py` | no per-node glob in plan stage (extend AssetIndexReuseLaw) |

**04-P0 verify:**

```powershell
poetry run pytest tests/test_cluster_dedup_ref.py tests/test_pruned_cluster_assets.py tests/test_plan_asset_resolution.py tests/test_cluster_delegate_cycles.py tests/test_layout_chrome_repair_laws.py -q -k "cluster or delegate or pruned or asset"
poetry run figma-flutter defects validate
```

**04-P0 smoke (manual / CI optional):**

```text
food_add_new_items + 9_a_home_bottom_navigation — plan stage < 30s
```

#### P1

| ID | Задача | DoD |
|----|--------|-----|
| **04-P1-1** | `materialize_missing_cluster_delegate_files` — terminal representative invariant | fails fast on pruned/empty rep |
| **04-P1-2** | Bijection test: each `Cluster*Widget` in plan → exactly one body source | `tests/test_cluster_bijection_plan.py` |
| **04-P1-3** | Corpus: `cluster_wrong_merge`, `cluster_empty_body`, `cluster_delegate_cycle` | 3 FIXED cases |

#### P2

- Full extractor bijection (non-cluster extracted widgets).
- Closure audit extracted ids ⊆ clean tree ids wired to conservation registry.

---

### Track 05 — Visual ownership & layout inference

#### P0 (blocked until **06-P0-0** merged)

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **05-P0-0** | Contract: ownership edge types, scorecard dimensions, ambiguous subtree definition | `docs/refactor/contracts/layout_hypothesis.md` | references `geometry_algebra.md` for pin/slot |
| **05-P0-1** | **Ownership pass** (parse/normalize): build `visual_ownership` edges on clean tree | новый модуль под `parser/boundaries/` или `parser/layout/ownership.py` | persisted or sidecar on node; provenance recorded |
| **05-P0-2** | Reconcile registry: `conflicts_with`, `priority`, runner order | `reconcile_registry.py` | hero inside runner OR explicit late-pass slot with conflict declaration |
| **05-P0-3** | **5 ownership laws** + tests: card surface, icon plate, navbar chrome, field host, scroll chrome | tests `test_ownership_*.py` | card siblings case without hero-at-index-0 patch |
| **05-P0-4** | Layout chooser (tier-0): ≥2 candidates on ambiguous subtree only. **Score = breakdown struct, не float** (поправка №6): `LayoutCandidateScore(geometry_residual, exceptional_offsets, paint_order_penalty, ownership_violations, flutter_invalidity, complexity_cost, total)`; `aabb_residual` — компонент, не вся scorecard. **Merge blocked до 06-P0 resolver API** (gate). Кандидаты P0 — только текущие (preserve-stack, row/column/wrap); ownership-derived (row-of-groups, scroll+overlay) — **только 05-P1** (поправка №7 — иначе костыль для будущего костыля) | `layout_criteria.py` extension | no full-tree search; beam width ≤ 3; breakdown в provenance |

**05-P0 verify:**

```powershell
poetry run pytest tests/test_sectionize_root_pass.py tests/test_layout_criteria.py tests/test_ir_layout_passes.py tests/test_ownership_laws.py -q
poetry run figma-flutter defects validate
```

#### P1

| ID | Задача | DoD |
|----|--------|-----|
| **05-P1-0** | Ownership-derived candidate families: row-of-groups + scroll+overlay в chooser (перенесено из P0, поправка №7 — зависят от ownership edges 05-P0-1) | beam of 4 с veto pruning; ambiguous-stack fixture scored |
| **05-P1-1** | Migrate hero / bottom-nav / grid conflicts to registry priorities | delete ad-hoc ordering in `normalize.py` where possible |
| **05-P1-2** | Benchmark: exceptional offset count on corpus sample | advisory report in `docs/refactor/generated/layout-benchmark.md` |
| **05-P1-3** | `emit_recipes.ownership_rules` → enforced checks (not report-only) for P0 laws | contract emit gate |

#### P2

- Numeric MDL scorecard on chooser tier-1.
- Reduce flex_policy branches only where chooser subsumes (measured burn-down, not big-bang).

---

## 6. Routing

| Симптом | Track | Первый слой |
|---------|-------|-------------|
| Wrong `Cluster*Widget` / empty widget body | 04 | `cluster_signature` + bijection table |
| Plan hang после subtree render | 04 | asset index + `walk_clean_tree` |
| Status bar merged with tabs | 04 | discriminator pass |
| Wrong pin / centered icon drift | 06 | `slots.py` + geometry algebra |
| Bottom bar floats / scroll partition | 06 | viewport region owner |
| Absolute child lost after sectionize | 06 | pass provenance + slot conservation |
| Card content beside surface (siblings) | 05 | ownership pass |
| Hero vs grid aspect conflict | 05 | reconcile conflict registry |
| New layout if/elif в emitter | 05 | chooser + ownership law missing |
| `replan_geometry` still fires | 06 | incremental slot (P1) or pass contract gap |

---

## 7. Критерии готовности Milestone 3

M3 закрывается **только вместе**:

### Contracts (docs)

- [ ] `contracts/geometry_algebra.md` — merged, linked from PIPELINE_ARROWS
- [ ] `contracts/cluster_signature.md` — merged
- [ ] `contracts/layout_hypothesis.md` — merged, references geometry algebra

### Track 06

- [ ] 3 geometry laws + FIXED corpus cases (pin/center, slot loss, viewport partition)
- [ ] `test_planner_corpus_gate` green
- [ ] No new coordinate patches in emitter for those families

### Track 04

- [ ] Cluster discriminator + bijection table (no last-wins on split)
- [ ] Dedup walks cycle-safe
- [ ] Plan-stage asset index reuse
- [ ] Budget / smoke test documented (hang class closed)

### Track 05

- [ ] Ownership pass produces edges for 5 laws
- [ ] Reconcile conflict registry with ≥3 declared conflicts (hero, bottom-nav, grid)
- [ ] Chooser on ambiguous subtrees only (tests prove not full-tree)

### Gates

- [ ] `defects validate` green
- [ ] Targeted pytest bundles (§8)
- [ ] `.\scripts\signoff.ps1` before `main`
- [ ] No regression: M2 conservation + PolicyDecision + shadow ratchet tests green

**Не в M3:** flex_policy rewrite, full replan removal, fleet golden regen.

---

## 8. Gates

| Уровень | Команда |
|---------|---------|
| 06 fast | `pytest tests/test_geometry_invariants.py tests/test_layout_constraints.py tests/test_placement_conservation.py tests/test_sectionize_root_pass.py -q` |
| 04 fast | `pytest tests/test_cluster_dedup_ref.py tests/test_pruned_cluster_assets.py tests/test_plan_asset_resolution.py tests/test_cluster_delegate_cycles.py -q` |
| 05 fast | `pytest tests/test_sectionize_root_pass.py tests/test_layout_criteria.py tests/test_ir_layout_passes.py tests/test_ownership_laws.py -q` |
| M2 regression | `pytest tests/test_conservation_registry.py tests/test_shadow_classifier_inventory.py tests/test_semantics_emit_gate.py -q` |
| Corpus | `poetry run figma-flutter defects validate` |
| Full | `.\scripts\signoff.ps1` |

---

## 9. Запреты

- Screen/`figmaId`/customer-path/golden-specific codegen
- Новый reconcile pass без conflict declaration (после 05-P0-2)
- Coarse cluster hash tweak без discriminator (ломает explosion / under-merge баланс)
- Ownership edges из emitter retroactively (только parse/normalize → IR consume)
- Full constraint solver в P0/P1
- Смешение `LAYOUT_LAWS` emit recipes с blocking conservation registry
- Обновление ratchet/shadow baseline без explicit remediation commit

---

## 10. Corpus linkage (M3 minimum)

| Инкремент | `family_id` | `law_ids` / notes |
|-----------|-------------|-------------------|
| 06-P0-1 | `wrong_pin_center` | geometry algebra Law 1 |
| 06-P0-2 | `absolute_slot_loss` | geometry algebra Law 2 |
| 06-P0-3 | `viewport_partition_drift` | geometry algebra Law 3 |
| 04-P0-1 | `cluster_wrong_merge` | `cluster_signature` discriminator |
| 04-P0-2 | `cluster_empty_body` | bijection table |
| 04-P1-3 | `cluster_delegate_cycle` | delegate repair + bijection |
| 05-P0-3 | `ownership_surface_content_sibling` | ownership Law: card |
| 05-P0-3 | `ownership_navbar_chrome` | ownership Law: navbar |
| 05-P0-2 | `reconcile_pass_conflict` | registry priority |

---

## 11. Checklist (implementation)

1. [ ] **Commit 0** — этот ТЗ + пустые заголовки contract stubs в `docs/refactor/contracts/`
2. [ ] **06-P0-0a** — constraint consumer inventory + ratchet
3. [ ] **06-P0-0b** — `geometry_algebra.md`; **04-P0-0** — `cluster_signature.md` (parallel)
4. [ ] **06-P0-1** — AxisConstraint + resolver + wrong pin/center law + case
5. [ ] **06-P0-2** — absolute slot provenance
6. [ ] **06-P0-3** — viewport region owner
7. [ ] **04-P0-1** — cluster discriminator + wrong merge test
8. [ ] **04-P0-2a/2b/2c** — early bijection gate + planned-graph guard + DefinitionKey (last-wins, оба сайта)
9. [ ] **04-P0-3** — walk_clean_tree + budget test
10. [ ] **04-P0-4** — asset index on plan paths
11. [ ] **05-P0-0** — `layout_hypothesis.md`
12. [ ] **05-P0-1** — ownership pass
13. [ ] **05-P0-2** — reconcile conflict registry
14. [ ] **05-P0-3** — 5 ownership laws
15. [ ] **05-P0-4** — tier-0 layout chooser
16. [ ] M3 signoff — §7 criteria + `signoff.ps1`

---

## 12. История документа

| Дата | Изменение |
|------|-----------|
| 2026-07-03 | Initial Milestone 3 TZ (Programs 04–06) after M2 research + analysis |
| 2026-07-03 | Consilium v2 (3:0): поправки №1–№9 — early bijection gate (04-P0-2a/2b), DefinitionKey topology split P0 (04-P0-2c, два сайта verified), constraint consumer inventory+ratchet (06-P0-0a), параметризованный AxisConstraint, LayoutCandidateScore breakdown, ownership-derived candidates → 05-P1, scoped replan dependency closure + full replan safety oracle, responsive MVP per-axis. PR #6 → architecture RFC |
