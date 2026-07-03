# ТЗ: Program 07 + 08 + 10 — Decorative fidelity, metamorphic testing, artifact identity

**Программы:** [07_decorative-primitive-fidelity.md](07_decorative-primitive-fidelity.md), [08_property-based-testing.md](08_property-based-testing.md), [10_provenance-cache-determinism.md](10_provenance-cache-determinism.md)  
**Статус:** research-complete v1.0 — Milestone 4  
**Аудитория:** инженер / coding agent, reviewer, владелец продукта  
**Не входит:** Program 09, hierarchical visual oracle, visual refine

---

## 1. Цель

Закрыть три класса системных дефектов:

| Program | Вопрос | Риск |
|---------|--------|------|
| **07** | Сохраняются ли substrate, glyph, stroke и badge как отдельные визуальные роли? | plate/glyph collapse, stretched icon, lost stroke, wrong background |
| **08** | Можно ли автоматически найти и минимально воспроизвести нарушение compiler law? | regressions ловятся только на известных экранах |
| **10** | Можно ли доверять повторно используемому IR/snapshot/debug artifact? | stale cache, partial run, incompatible versions |

Общий тезис:

```text
Program 07 сохраняет визуальную структуру.
Program 08 доказывает законы на множестве входов.
Program 10 гарантирует, что доказательство относится к правильному запуску и артефакту.
```

### Не цели

- Не реализовывать Program 09.
- Не запускать visual refine или поиск по pixel diff.
- Не обновлять golden fleet.
- Не добавлять screen, feature или figmaId-specific patches.
- Не строить full content-addressed artifact store в P0.
- Не требовать byte-identical final Dart для LLM-assisted path.
- Не генерировать raw Figma JSON в первой версии property framework.

---

## 2. Scope

### In scope

| Track | Область | Основные пути |
|-------|---------|----------------|
| **07** | Decorative role contract и shadow inventory | `assets/composite_icons.py`, `parser/interaction/`, `generator/layout/`, `generator/ir/extracted_paint.py`, `generator/ir/fidelity/` |
| **07** | Generic bounds, flatten и downgrade laws | `generator/layout/widgets/`, `generator/ir/fidelity/`, `debug/provenance.py` |
| **08** | Synthetic clean-tree builders | новый `tests/synthetic/` |
| **08** | Metamorphic transforms, law oracles, replay artifacts | `tests/support/`, `tests/test_conservation_*`, geometry/extraction tests |
| **10** | Typed artifact identity | новый `compiler/artifact_identity.py` или `debug/artifact_identity.py` |
| **10** | Cached IR compatibility gate | `debug/ir_dumps.py`, `debug/ir_load.py`, `pipeline/llm.py` |
| **10** | Snapshot/prefetch identity и stage budgets | `sync/`, `pipeline/dump_prefetch.py`, `generator/planner/timing.py` |

### Out of scope

| Тема | Когда |
|------|-------|
| Hierarchical visual oracle | Program 09, backlog |
| Visual refine | backlog |
| Raw Figma property generator | 08-P2 |
| Hypothesis integration | 08-P1 после стабилизации builders |
| Content-addressed artifact store | 10-P2 |
| Полная миграция всех decorative special cases | 07-P2 |
| ML attribution / visual search | не входит в M4 |

---

## 3. Зависимости и порядок

### Prerequisites

| Зависимость | Требование |
|-------------|------------|
| Program 02 | conservation laws и stable `law_id` доступны |
| Program 03 | semantic evidence / veto не обходятся decorative classifier |
| Program 04 | extraction call-site/definition proof работает в shadow |
| Program 06 | geometry resolver и intrinsic bounds доступны как typed facts |

### Разрешённая параллельность

```text
10-P0-0 artifact inventory ───────────────┐
08-P0-0 synthetic builder contract ───────┼─ parallel
07-P0-0 decorative decision inventory ────┘
                    ↓
10 identity envelope + 08 replay metadata
                    ↓
07/08/10 shadow gates
                    ↓
per-route enforce decisions
```

Program 08 не должен зависеть от завершения Program 07. Program 07 authority migration не начинается до появления replayable Program 08 tests для соответствующей law family.

---

## 4. Нормативные правила

### 4.1 Общие

- Один increment = один PR.
- Additive model, shadow comparison и authority switch не смешивать.
- `law_id` и `family_id` хранить отдельно.
- Любой blocking gate сначала проходит `report_only → shadow → enforce`.
- Settings и rollout policy передавать через pipeline context; не читать env внутри compiler hot path.
- Новый generated artifact должен иметь deterministic serialization.

### 4.2 Program 07

- Exported SVG не является доказательством source flatten.
- Substrate, glyph, stroke и badge не схлопываются без explicit flatten decision.
- Glyph intrinsic bounds не заменяются plate bounds.
- Stroke рисуется ровно один раз.
- Fidelity downgrade записывает reason и provenance.
- Decorative facts не повышают semantic control kind без Program 03 evidence.

### 4.3 Program 08

- Generated case обязан пройти schema/structural validity check до law oracle.
- Metamorphic transform обязан объявить precondition.
- Random-only failure запрещён: нужен seed и replay artifact.
- Property test не использует full-screen golden как обязательный structural oracle.
- Минимизированный production-relevant case добавляется как обычный regression test.

### 4.4 Program 10

- Filename/path не является достаточной cache identity.
- Artifact без valid identity не используется автоматически после enforce.
- Incomplete producer stage не публикует reusable artifact.
- Upstream version/config/assets drift даёт explicit stale verdict.
- Timeout и performance regression не смешивать в один verdict.

---

## 5. Stable laws

### Program 07

```text
LAW-DECORATIVE-ROLE-PRESERVATION
LAW-DECORATIVE-GLYPH-INTRINSIC-BOUNDS
LAW-DECORATIVE-STROKE-SINGLE
LAW-DECORATIVE-FLATTEN-DECLARED
LAW-DECORATIVE-DOWNGRADE-PROVENANCE
```

### Program 08

```text
LAW-SYNTHETIC-CASE-VALID
LAW-METAMORPHIC-PRECONDITION-DECLARED
LAW-PROPERTY-FAILURE-REPLAYABLE
LAW-PROPERTY-ORACLE-DETERMINISTIC
```

### Program 10

```text
LAW-ARTIFACT-IDENTITY-COMPLETE
LAW-ARTIFACT-REUSE-COMPATIBLE
LAW-ARTIFACT-PRODUCER-COMPLETE
LAW-ARTIFACT-UPSTREAM-CLOSED
LAW-PIPELINE-STAGE-BOUNDED
LAW-PREEMIT-DETERMINISTIC
```

---

## 6. Merge order

```text
Commit 0: ТЗ + contract stubs
  ↓
07-P0-0 || 08-P0-0 || 10-P0-0
  ↓
10-P0-1 identity envelope
  ↓
08-P0-1 builders + first metamorphic laws
  ||
07-P0-1 decorative shadow facts
  ↓
10-P0-2 cached IR shadow compatibility
08-P0-2 replay artifact
07-P0-2 flatten/downgrade shadow
  ↓
10-P0-3 producer completion
08-P0-3 expanded structural laws
07-P0-3 generic bounds/stroke laws
  ↓
M4 shadow signoff
  ↓
per-route enforce PRs
```

Enforce PRs разрешены только после отдельного decision record:

```text
law_id
route/artifact kind
baseline evidence
known mismatches
fallback
rollback
owner
approval
```

---

## 7. Track 07 — Decorative primitive fidelity

### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **07-P0-0** | Inventory decorative decisions | `audit/decorative_primitive_inventory.py`, generated JSON | Все whole-group export, icon-badge, checkbox glyph, nav substrate и raster downgrade routes классифицированы |
| **07-P0-1** | Additive `DecorativePrimitiveFacts` | `schemas/` или `generator/ir/contracts/` | roles: substrate/glyph/stroke/badge; output unchanged |
| **07-P0-2** | Shadow role inference и flatten diagnostics | parser/assets/layout consumers | mismatch report с node id, source route и evidence |
| **07-P0-3** | Generic intrinsic-bounds и stroke laws | `generator/ir/extracted_paint.py`, widget emit | stretched glyph и double/lost stroke ловятся до final emit |
| **07-P0-4** | Fidelity downgrade provenance | fidelity router, design coverage/provenance | baked/native fallback имеет named reason |
| **07-P0-5** | Corpus cases | `corpus/cases/`, tests | минимум 4 families: dropped plate, stretched glyph, lost/double stroke, undeclared flatten |

### P1 — controlled migration

Один consumer family на PR:

```text
07-P1-1 icon badge/extracted paint
07-P1-2 navigation substrate
07-P1-3 decorative checkbox/checkmark
07-P1-4 composite SVG export
07-P1-5 remaining compact vector routes
```

Каждый PR:

- shadow parity artifact;
- general law tests;
- минимум один real corpus fixture;
- rollback к legacy route;
- без screen-specific branch.

### Program 07 acceptance

- Все P0 routes присутствуют в inventory.
- Один и тот же node не получает несовместимые decorative roles без diagnostic.
- Glyph bounds сохраняются независимо от plate extent.
- Flatten и baked fallback объяснимы.
- Минимум две consumer families переведены на общий contract.

---

## 8. Track 08 — Property-based & metamorphic testing

### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **08-P0-0** | Typed clean-tree builder | `tests/synthetic/builders.py` | stack/row/column/vector/cluster/viewport builders; deterministic ids |
| **08-P0-1** | Transform protocol + preconditions | `tests/synthetic/transforms.py` | transform id, input, precondition, expected law |
| **08-P0-2** | Replay artifact schema | `tests/synthetic/artifacts.py` | seed, law id, versions, settings fingerprint, source/minimal tree |
| **08-P0-3** | First blocking metamorphic tests | new tests | rename no-op, duplicate reusable instance, CENTER/SCALE resize |
| **08-P0-4** | Structural expansion | new tests | cycle path и independent sibling permutation |
| **08-P0-5** | Minimal reduction strategy | support code | deterministic reducer; no Hypothesis requirement |

### P1

| ID | Задача | Gate |
|----|--------|------|
| **08-P1-1** | Evaluate/add Hypothesis | builders stable, runtime measured |
| **08-P1-2** | PR fast budget | stable replay and low flake rate |
| **08-P1-3** | Nightly expanded search | advisory first |
| **08-P1-4** | Differential deterministic vs LLM | compare contracts, not source text |

### Required metamorphic semantics

- Rename only fields outside evidence set.
- Sibling permutation only for explicitly independent siblings.
- Duplicate instance changes call-site count, not definition identity.
- Geometry resize computes symbolic constraint once at source extent.
- Invalid generated tree is generator failure, not compiler law violation.

### Program 08 acceptance

- Не менее 5 transforms с explicit preconditions.
- Не менее 3 tests blocking в PR CI.
- Failure воспроизводится из сохранённого artifact.
- Один production defect family сведён к минимальному synthetic case.
- Generated tests не требуют visual refine или golden capture.

---

## 9. Track 10 — Provenance, cache & determinism

### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **10-P0-0** | Reusable artifact inventory | generated JSON + test ratchet | processed, cached IR, pre-emit, snapshot, prefetch consumers перечислены |
| **10-P0-1** | Typed `ArtifactIdentity` | new module + contract doc | canonical serialization и fingerprint |
| **10-P0-2** | Cached IR shadow validation | `debug/ir_load.py`, pipeline boundary | compatible/stale/unknown verdict; legacy reuse authoritative |
| **10-P0-3** | Producer completion marker | IR/snapshot writers | partial stage не считается complete |
| **10-P0-4** | Dump content identity | `pipeline/dump_prefetch.py` | same path + changed content invalidates prefetch |
| **10-P0-5** | Settings and asset fingerprints | settings/assets boundary | semantic input change invalidates dependent artifacts |
| **10-P0-6** | Canonical pre-emit determinism test | debug IR + tests | same identity → same hash |

### Artifact identity minimum

```text
artifact_kind
artifact_schema_version
source_dump_hash
parser_version
normalizer_version
ir_schema_version
emitter_version
settings_fingerprint
asset_manifest_fingerprint
upstream_fingerprints
producer_complete
```

Timestamps и absolute paths не входят в deterministic fingerprint.

### P1

| ID | Задача | DoD |
|----|--------|-----|
| **10-P1-1** | Cached IR enforce per artifact kind | separate decision record |
| **10-P1-2** | Planner stage budgets | typed timeout + duration artifact |
| **10-P1-3** | Stale artifact UX | explicit reason and regeneration action |
| **10-P1-4** | Provenance/upstream linking | artifact → producer inputs trace |

### P2

- Content-addressed artifact store.
- Cross-run deduplication.
- Remote artifact cache.

### Program 10 acceptance

- Cached IR не используется молча при incompatible identity.
- Same path with changed dump content не reuse prefetch.
- Parser/settings/assets drift покрыты tests.
- Incomplete artifact не проходит reuse gate.
- Canonical pre-emit determinism проверяется в CI.

---

## 10. Verification

### Program 07 baseline

```powershell
poetry run pytest tests/test_home_bottom_navigation_emit_laws.py tests/test_gist_add_expenses_emit_laws.py tests/test_transaction_income_emit_laws.py tests/test_structural_image_assets.py tests/test_svg_filter_raster_fallback.py tests/test_fidelity_regressions.py -q
```

### Program 08 baseline

```powershell
poetry run pytest tests/test_conservation_harness.py tests/test_layout_combinatorics.py tests/test_geometry_constraint_algebra.py tests/test_cluster_bijection_plan.py -q
```

### Program 10 baseline

```powershell
poetry run pytest tests/test_ir_load.py tests/test_pipeline_incremental.py tests/test_sync_regions.py -q
```

### M4 bundle

```powershell
poetry run ruff check .
poetry run mypy src
poetry run pytest -q
poetry run figma-flutter defects validate
```

Absolute runtime threshold не является единственным performance verdict на shared CI. Для stage budgets отдельно хранить complexity/input metrics и environment metadata.

---

## 11. PR discipline

Запрещено смешивать в одном PR:

- decorative facts и production emit migration;
- synthetic framework и unrelated law fixes;
- artifact schema и cached IR enforce;
- несколько decorative consumer families;
- stage timeout и performance optimization;
- Program 09 или visual refine.

Каждый PR содержит:

- один increment ID;
- changed routes/artifact kinds;
- tests;
- output/behavior change statement;
- fallback/rollback для authority change;
- generated evidence path, если increment shadow/enforce.

---

## 12. Milestone 4 Definition of Done

Milestone 4 считается завершённым, когда:

1. Program 07 имеет общий decorative contract, shadow inventory и минимум две migrated consumer families.
2. Program 08 имеет replayable synthetic framework и минимум три blocking metamorphic tests.
3. Program 10 имеет typed artifact identity, cached IR compatibility gate и pre-emit determinism test.
4. Все enforce routes включены только отдельными decision records.
5. Нет новых screen/figmaId-specific patches.
6. Program 09 и visual refine не были включены в scope.
7. Full CI и defect corpus validation зелёные.

M4 signoff не означает автоматический enforce всех decorative/cache routes.
