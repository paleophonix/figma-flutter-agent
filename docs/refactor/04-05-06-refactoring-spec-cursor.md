# ТЗ: Milestone 3 — Programs 04 + 05 + 06

**Тема:** extraction bijection, geometry algebra, visual ownership  
**Программы:** [04_extraction-dedup-bijection.md](04_extraction-dedup-bijection.md), [05_visual-ownership-layout-inference.md](05_visual-ownership-layout-inference.md), [06_geometry-constraint-algebra.md](06_geometry-constraint-algebra.md)  
**Стыковка:** [00-01-cursor-alignment.md](00-01-cursor-alignment.md) · [02-03-refactoring-spec-cursor.md](02-03-refactoring-spec-cursor.md)  
**Контракт стрелок:** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md) · `.cursor/rules/pipeline-contracts.mdc`  
**Architecture RFC:** [04-06-architecture-spec.md](04-06-architecture-spec.md)  
**Статус:** normative execution plan, consilium v2.1  
**Аудитория:** разработчик/агент в Cursor, reviewer, владелец продукта

---

## 1. Цель

Закрыть три класса silent wrong behavior:

| Program | Вопрос | Blast |
|---|---|---|
| **04** | Каждый cluster call-site разрешается ровно в одно определение? | wrong `Cluster*Widget`, empty body, plan hang |
| **06** | Constraint facts и emit slots используют одну алгебру? | wrong pin/center, slot loss, replan masking |
| **05** | Кто визуально владеет surface/content/chrome до emit? | layout компенсируется reconcile/flex branches |

Совместный тезис:

```text
Figma parent tree ≠ cluster equivalence ≠ visual ownership ≠ constraint algebra
```

Каждый граф получает typed contract, stable law IDs, corpus families и проверяемую границу. Решение принимается до emitter; emitter исполняет принятое решение и не реконструирует intent.

Основная формула M3:

```text
type constraints
→ prove cluster mapping
→ observe ownership
→ score only evaluable candidates
→ emit only committed decisions
```

### Не цель M3

- CSS/Cassowary-level solver.
- Full-tree beam/MDL search.
- Переписывание всего `flex_policy`.
- Удаление full replan до доказанной equivalence.
- Fleet golden regeneration.
- Screen/feature/`figmaId`/path-specific patches.
- Full bijection proof для всех типов extracted widgets.

---

## 2. Prerequisites и разрешённый старт

| Prerequisite | Статус / правило |
|---|---|
| Program 00 corpus CLI | готово |
| Program 01 pass contract | готово |
| Programs 02/03 P0 | functionally accepted |
| M2 final stamp | pending remote CI publication и debug hygiene |

Разрешено до M2 final stamp:

- Commit 0;
- contract/inventory work;
- report-only passes;
- tests, corpus cases и additive models без production-output change.

Запрещено до M2 final stamp:

- enforce rollout;
- изменение production output через новый ownership/chooser path;
- M3 final signoff.

---

## 3. Scope

### In scope

| Track | Стрелки | Основные артефакты |
|---|---|---|
| **06** Constraint vocabulary + consumer ratchet | parse → plan → emit | `geometry_algebra.md`, inventory JSON, `AxisConstraint` |
| **06** Three geometry laws | CP1, plan, emit | pin/center, absolute→flow, viewport partition |
| **04** Signature/discriminator contract | parse → dedup | `cluster_signature.md`, `ClusterDiscriminator` |
| **04** Definition identity + early bijection | plan before render | `DefinitionKey`, `ClusterExtractionPlan` |
| **04** Cycle-safe walks + asset index | dedup/plan/assets | common traversal and index reuse |
| **05** Ownership observation | parse/normalize | immutable overlay + diagnostics |
| **05** Reconcile conflict inventory | normalize | pass metadata and runner order |
| **05** Candidate scorer | IR ambiguous only | score breakdown, hard veto, abstain |
| **00** Corpus linkage | all tracks | mechanism families + FIXED cases |

### Out of scope

| Тема | После M3 |
|---|---|
| Full extractor bijection | 04-P2 |
| Full replan removal | 06-P2 |
| Ownership-driven production emit for all families | 05-P2+ |
| Full `flex_policy` replacement | 05-P2+ |
| Automatic breakpoint topology rewrites | later responsive program |
| Formal CP3 post-emit runner | M3.1 only if coverage audit finds escape |

---

## 4. Stable law vocabulary

`law_id` стабилен и не равен `violation_code`.

### Geometry

- `LAW-GEOM-CONSTRAINT-SEMANTICS`
- `LAW-GEOM-ABSOLUTE-FLOW-SLOT`
- `LAW-GEOM-VIEWPORT-REGION`
- `LAW-GEOM-SLOT-FRESH` — P1/RFC target

### Cluster extraction

- `LAW-CLUSTER-DEFINITION-KEY`
- `LAW-CLUSTER-BIJECTION`
- `LAW-CLUSTER-DISCRIMINATOR`
- `LAW-CLUSTER-WALK-ACYCLIC`
- `LAW-CLUSTER-ASSET-INDEX`
- `LAW-CLUSTER-PLANNED-PROJECTION`

### Ownership/layout

- `LAW-OWNERSHIP-UNIQUE`
- `LAW-OWNERSHIP-ACYCLIC`
- `LAW-OWNERSHIP-BOUNDARY`
- `LAW-OWNERSHIP-PAINT-ORDER`
- `LAW-OWNERSHIP-NO-REPARENT`
- `LAW-LAYOUT-CANDIDATE-EXPLAINED`
- `LAW-LAYOUT-ABSTAIN-LOW-CONFIDENCE`
- `LAW-RECONCILE-CONFLICT-DECLARED`

Commit 0 создаёт contract stubs с этим vocabulary. Реализация и registration происходят в соответствующих increments.

---

## 5. Жёсткие правила разработки

- Никаких screen/customer/`figmaId`/golden-specific branches.
- Raw constraint strings после ratchet не получают новых consumers.
- Cluster topology variants не индексируются только по `cluster_id`.
- Planned Dart graph не доказывает корректность extraction plan; это отдельный projection gate.
- Ownership P0 — immutable sidecar/report-only: не мутирует clean tree/IR, не меняет ranking, emit или Dart.
- Numeric chooser merge запрещён до authoritative geometry resolver.
- Новый reconcile pass без `phase`, `reads`, `writes`, `conflicts_with`, `priority` — не merge после 05-P0-2.
- Absolute→flow без named transform и provenance — не merge после 06-P0-2.
- Full replan остаётся safety oracle до proven scoped-replan equivalence.
- Settings читаются на pipeline boundary, не внутри compiler functions.
- Обновление ratchet baseline — отдельный explicit remediation commit.

---

## 6. Обязательный merge order

```text
Commit 0: execution spec + architecture RFC + contract stubs

Track A — 06                         Track B — 04
06-P0-0a inventory + ratchet         04-P0-0 contract
06-P0-0b geometry contract           04-P0-1 cycle-safe critical walks
06-P0-1 AxisConstraint + resolver    04-P0-2 DefinitionKey topology split
06-P0-2 absolute→flow law            04-P0-3 early bijection
06-P0-3 viewport-region law          04-P0-4 discriminator
                                      04-P0-5 asset index/budget
              \                     /
               \---- parallel -----/

After 06-P0-0b:
  05-P0-0 contract
  05-P0-1 ownership report-only
  05-P0-2 reconcile inventory/conflicts
  05-P0-3 ownership laws in report-only mode

After 06-P0-1 resolver API:
  05-P0-4 numeric candidate scorer

Then:
  M3 signoff
```

Ни один numeric chooser change не входит в `main` до 06-P0-1.

---

# 7. Track 06 — Geometry constraint algebra

## 06-P0-0a — Raw consumer inventory + ratchet

**Цель:** получить machine-readable baseline всех прямых чтений raw constraint strings.

**Артефакты:**

- `docs/refactor/generated/constraint-consumers.json` — canonical generated inventory;
- `tests/test_constraint_consumer_ratchet.py` — baseline-only ratchet;
- generator/audit command или importable collector.

**Правила ratchet:**

| Изменение | CI |
|---|---|
| новый direct raw-string consumer | FAIL |
| удаление consumer | ALLOW |
| миграция на typed API | ALLOW |
| existing baseline entry | временно ALLOW |
| baseline update без remediation diff | FAIL/review block |

Число consumers не фиксируется в Markdown: source of truth — canonical JSON. Пустой baseline в Commit 0 не создаётся.

**DoD:** inventory детерминирован; повторный запуск даёт byte-stable JSON; новые reads ловятся тестом.

## 06-P0-0b — Geometry algebra contract

Заполнить `contracts/geometry_algebra.md`:

- raw facts vs typed facts vs resolved slot;
- per-axis operators;
- viewport ownership;
- legal transforms;
- replan как временный compensator;
- stable law IDs и violation codes.

## 06-P0-1 — Typed AxisConstraint + authoritative resolver

Additive model; raw fields остаются для compatibility/audit.

```python
@dataclass(frozen=True)
class AxisConstraint:
    op: ConstraintOp
    start_offset: float | None = None
    end_offset: float | None = None
    size: float | None = None
    center_delta: float | None = None
    scale_offset_ratio: float | None = None
    scale_size_ratio: float | None = None
```

Минимальные `ConstraintOp`:

```text
PIN_START
PIN_END
PIN_BOTH
CENTER
SCALE
INTRINSIC
FLOW
VIEWPORT_PIN
```

Authoritative API:

```python
resolve_constraint_axis(
    constraint: AxisConstraint,
    parent_extent: float,
    child_extent: float | None,
) -> ResolvedAxisSlot
```

P0 migrations:

- parser/placement creation path;
- geometry planner/slots;
- bounded-axis validation;
- positioned emit.

Остальные consumers остаются под ratchet.

**Law:** `LAW-GEOM-CONSTRAINT-SEMANTICS`  
**Corpus family:** `wrong_pin_center`

**DoD:**

- additive commit не меняет current output;
- raw↔typed round-trip/audit test;
- CENTER сохраняет центр при ≥3 parent extents;
- PIN_END сохраняет inset;
- PIN_BOTH сохраняет оба inset;
- SCALE изменяет offset и size пропорционально parent span;
- inventory count не растёт.

## 06-P0-2 — Absolute→flow named transform

Все flatten/unpin/sectionize transformations, теряющие absolute slot, должны иметь:

- transform name;
- before/after constraint snapshots;
- affected IDs;
- `DeviationRecord`/pass provenance;
- residual or explicit degraded reason.

**Law:** `LAW-GEOM-ABSOLUTE-FLOW-SLOT`  
**Corpus family:** `absolute_slot_loss`

**DoD:** FID-26-like fixture не теряет slot молча; violation блокирует CP2/enforce path.

## 06-P0-3 — Viewport/chrome region owner

Ввести typed region ownership (`layout_region` или equivalent), различающий:

- scroll body;
- viewport top chrome;
- viewport bottom chrome;
- overlay;
- normal parent-relative content.

**Law:** `LAW-GEOM-VIEWPORT-REGION`  
**Corpus family:** `viewport_partition_drift`

**DoD:** bottom navigation сохраняет viewport ownership при tall scroll body; inset не присваивается повторно flow parent.

## 06-P1 — Scoped replan

Dirty IDs недостаточно. Scope вычисляется так:

```text
dirty IDs
→ nearest geometry planning roots
→ ancestor/descendant dependency closure
→ scoped replan
→ equivalence comparison with full replan
```

Full replan остаётся CP2 safety oracle до доказанной equivalence на fixture/corpus set.

Дополнительно:

- `preserve_placement` получает named downgrade stamp;
- slot source fingerprint готовит `LAW-GEOM-SLOT-FRESH`;
- автоматическое breakpoint topology rewrite остаётся out of scope.

### Responsive MVP

```text
stable topology
+ per-axis parent-relative constraints
+ explicit adaptive rules only
```

Uniform whole-screen scaling не считается responsive constraints.

---

# 8. Track 04 — Extraction/dedup bijection

## 04-P0-0 — Cluster contract

Заполнить `contracts/cluster_signature.md`:

- structural signature fields;
- fields outside signature;
- parameter vs identity vs discriminator;
- component-backed vs structural cluster;
- prune/hydrate asset ownership;
- `DefinitionKey` and plan-level bijection.

## 04-P0-1 — Cycle-safe critical walks

Перевести critical dedup/prune/hydrate/asset walks на:

- `walk_clean_tree`; или
- equivalent traversal с path/visited и `CleanTreeCycleError`; или
- prevalidated immutable acyclic index.

**Law:** `LAW-CLUSTER-WALK-ACYCLIC`

**DoD:** malformed cyclic fixture завершается typed error, не hang; complexity/budget test присутствует.

## 04-P0-2 — DefinitionKey for topology variants

`cluster_id` не является достаточным ключом split family.

```python
@dataclass(frozen=True)
class DefinitionKey:
    cluster_id: str
    topology_variant: str
    source_kind: str
```

DefinitionKey обязан использоваться в:

- class mapping;
- representative mapping;
- vector/asset variants;
- call-site resolution;
- materialization lookup.

**Law:** `LAW-CLUSTER-DEFINITION-KEY`

**DoD:** два topology groups исходного cluster имеют distinct keys; нет last-wins ни в main widget renderer, ни в subtree renderer; каждый call-site указывает конкретный variant.

## 04-P0-3 — Early extraction bijection

Ввести узкий pre-render plan:

```python
@dataclass(frozen=True)
class ClusterExtractionPlan:
    definitions: Mapping[DefinitionKey, ClusterWidgetSpec]
    call_sites: Mapping[str, DefinitionKey]
```

Validation выполняется до `render_widget_file` и до scan generated Dart.

Проверки:

- call-site key существует;
- definition имеет ≥1 call-site;
- duplicate authoritative definition запрещён;
- representative не empty/pruned terminal без explicit permit;
- delegate dependency graph не содержит cycle/self-reference.

Ошибка: typed `ExtractionBijectionError` с involved IDs/keys.

**Law:** `LAW-CLUSTER-BIJECTION`

`PlannedDartGraph` остаётся отдельным финальным projection gate:

- imports;
- classes;
- files;
- duplicate/missing Dart bodies.

**Law:** `LAW-CLUSTER-PLANNED-PROJECTION`

## 04-P0-4 — Pre-cluster discriminator

Structural hash не поглощает UI role. Перед bucket/partition вводится typed discriminator, например:

```python
ClusterDiscriminator(
    viewport_region,
    anchor_role,
    interaction_role,
    ownership_role,
)
```

Discriminator не должен включать arbitrary absolute coordinates или screen names.

**Law:** `LAW-CLUSTER-DISCRIMINATOR`

**DoD:** status bar и tab bar с одинаковой shape разделяются; одинаковые повторяющиеся элементы одной role family продолжают merge.

## 04-P0-5 — Asset index + budget

Переиспользовать canonical asset node index в cluster variant/finalize/representative paths. Запретить per-node filesystem glob в normal plan path.

**Law:** `LAW-CLUSTER-ASSET-INDEX`

**DoD:**

- index reuse test;
- synthetic N=500/M=200 budget;
- `food_add_new_items` и `9_a_home_bottom_navigation` plan stage <30s на reference runner или documented environment classification.

## 04-P1/P2

P1:

- post-hoc materialization только diagnostic/degraded;
- terminal representative invariant;
- corpus cases `cluster_wrong_merge`, `cluster_empty_body`, `cluster_delegate_cycle`.

P2:

- full extractor bijection beyond cluster delegate path;
- extracted source/asset closure through conservation registry.

---

# 9. Track 05 — Visual ownership and layout chooser

## Gates

After **06-P0-0b**:

- contract;
- report-only ownership overlay;
- reconcile inventory/conflict metadata;
- ownership diagnostic laws.

After **06-P0-1**:

- numeric candidate scoring/selection.

## 05-P0-0 — Layout hypothesis contract

Заполнить `contracts/layout_hypothesis.md`:

- ownership edge types;
- ambiguous subtree definition;
- hard vetoes;
- score dimensions;
- candidate budget;
- confidence margin and abstain;
- explicit dependency on geometry algebra.

## 05-P0-1 — Ownership overlay, report-only

Output — immutable sidecar/debug artifact, keyed by stable node IDs.

```python
@dataclass(frozen=True)
class VisualOwnershipEdge:
    owner_id: str
    owned_id: str
    relation: OwnershipRelation
    evidence: Mapping[str, object]
    confidence: float
    source: str
```

P0 relations:

- surface/content;
- plate/glyph;
- navbar/destination;
- field host/parts;
- scroll body/viewport chrome.

P0 MUST NOT:

- mutate CleanDesignTree or ScreenIr;
- reparent nodes;
- affect candidate ranking;
- affect emit or Dart output;
- remove existing reconcile/flex behavior.

**DoD:** edges + evidence visible in audit artifact; same input with ownership enabled/disabled generates identical Dart.

## 05-P0-2 — Reconcile inventory and conflict declaration

Каждый pass получает минимум:

```text
name
phase
reads
writes
requires
conflicts_with
priority
activation
```

Registry является источником orchestration order. Отдельный late invocation допускается только как explicit registered phase.

**Law:** `LAW-RECONCILE-CONFLICT-DECLARED`

**DoD:** hero, bottom-nav и grid collision surfaces отражены в report; registry drift/duplicate invocation test.

## 05-P0-3 — Ownership diagnostic laws

P0 laws работают на sidecar и не меняют output:

- `LAW-OWNERSHIP-UNIQUE`;
- `LAW-OWNERSHIP-ACYCLIC`;
- `LAW-OWNERSHIP-BOUNDARY`;
- `LAW-OWNERSHIP-PAINT-ORDER`;
- `LAW-OWNERSHIP-NO-REPARENT`.

Fixtures:

- card surface/content;
- icon plate/glyph;
- navbar chrome/destinations;
- field host/value/label;
- scroll body/viewport chrome.

**DoD:** expected edges detected; diagnostics green; generated Dart unchanged; existing hero/index patch ещё не удаляется.

## 05-P0-4 — Tier-0 candidate scorer

Merge blocked until 06-P0-1 resolver API.

P0 candidate families:

- preserve stack;
- existing row;
- existing column;
- existing wrap.

Ownership-derived row-of-groups и scroll+overlay — P1 only.

```python
@dataclass(frozen=True)
class LayoutCandidateScore:
    geometry_residual: float
    exceptional_offsets: int
    paint_order_penalty: float
    ownership_violations: int
    flutter_invalidity: int
    complexity_cost: float
    total: float
```

В P0 `ownership_violations` остаётся нулём/diagnostic-only и не влияет на winner до P1.

Hard veto до scoring:

- node loss without permit;
- invalid Flutter parent-data relation;
- paint-order violation;
- extraction boundary violation;
- viewport pin loss;
- impossible/unbounded geometry.

Budget:

```text
generated candidates ≤ 4
scored finalists ≤ 3
committed result = 1 winner or abstain
```

Abstain обязателен, если:

- нет feasible candidates;
- residual превышает budget;
- margin winner/runner-up ниже threshold;
- required evidence отсутствует.

**Laws:**

- `LAW-LAYOUT-CANDIDATE-EXPLAINED`;
- `LAW-LAYOUT-ABSTAIN-LOW-CONFIDENCE`.

**DoD:** score breakdown + rejected reasons + margin в provenance; ambiguous-only test доказывает отсутствие full-tree search; low-confidence fixture даёт abstain.

## 05-P1/P2

P1:

- chooser consumes validated ownership overlay;
- row-of-groups and scroll+overlay candidates;
- migrate hero/bottom-nav/grid ordering into registry;
- exceptional-offset benchmark.

P2:

- corpus-derived/MDL calibration of score weights;
- measured flex-policy branch burn-down;
- ownership-driven emit family rollout behind explicit policy.

---

## 10. Corpus linkage

| Increment | `family_id` | `law_id` |
|---|---|---|
| 06-P0-1 | `wrong_pin_center` | `LAW-GEOM-CONSTRAINT-SEMANTICS` |
| 06-P0-2 | `absolute_slot_loss` | `LAW-GEOM-ABSOLUTE-FLOW-SLOT` |
| 06-P0-3 | `viewport_partition_drift` | `LAW-GEOM-VIEWPORT-REGION` |
| 04-P0-1 | `cluster_delegate_cycle` | `LAW-CLUSTER-WALK-ACYCLIC` |
| 04-P0-2 | `cluster_topology_last_wins` | `LAW-CLUSTER-DEFINITION-KEY` |
| 04-P0-3 | `cluster_empty_body` | `LAW-CLUSTER-BIJECTION` |
| 04-P0-4 | `cluster_wrong_merge` | `LAW-CLUSTER-DISCRIMINATOR` |
| 04-P0-5 | `cluster_asset_scan_blowup` | `LAW-CLUSTER-ASSET-INDEX` |
| 05-P0-2 | `reconcile_pass_conflict` | `LAW-RECONCILE-CONFLICT-DECLARED` |
| 05-P0-3 | `ownership_surface_content_sibling` | `LAW-OWNERSHIP-BOUNDARY` |
| 05-P0-3 | `ownership_navbar_chrome` | `LAW-OWNERSHIP-PAINT-ORDER` |
| 05-P0-4 | `layout_low_confidence_forced_choice` | `LAW-LAYOUT-ABSTAIN-LOW-CONFIDENCE` |

---

## 11. Verification gates

Тесты, ещё не существующие на момент Commit 0, помечены **[introduced]**.

| Level | Command / requirement |
|---|---|
| 06 current + introduced | `poetry run pytest tests/test_geometry_invariants.py tests/test_placement_conservation.py tests/test_sectionize_root_pass.py tests/test_planner_corpus_gate.py tests/test_layout_constraints.py tests/test_constraint_consumer_ratchet.py -q` |
| 04 current + introduced | `poetry run pytest tests/test_cluster_dedup_ref.py tests/test_pruned_cluster_assets.py tests/test_plan_asset_resolution.py tests/test_cluster_delegate_cycles.py tests/test_cluster_bijection_plan.py -q` |
| 05 current + introduced | `poetry run pytest tests/test_sectionize_root_pass.py tests/test_layout_criteria.py tests/test_ir_layout_passes.py tests/test_ownership_laws.py -q` |
| M2 regression | `poetry run pytest tests/test_conservation_registry.py tests/test_conservation_invariants.py tests/test_policy_decision.py tests/test_semantics_evidence_specs.py tests/test_shadow_classifier_inventory.py tests/test_cp_post_classify.py tests/test_pass_contract.py -q` |
| Corpus | `poetry run figma-flutter defects validate` |
| Strict demo | `poetry run figma-flutter demo-signoff --strict --signoff-gates` or repository-equivalent command |
| Full | `.\scripts\signoff.ps1` with environment blockers classified, not silently ignored |

Каждый implementation PR запускает минимальный targeted bundle + corpus validation. M3 signoff запускает все bundles и публикует acceptance report.

---

## 12. Definition of Done — Milestone 3

### Contracts

- [ ] Три contracts заполнены и linked from `PIPELINE_ARROWS.md`.
- [ ] Stable law IDs зарегистрированы или явно отмечены report-only.
- [ ] Architecture RFC не используется как sprint scope.

### Track 06

- [ ] Raw consumer inventory + ratchet green.
- [ ] Authoritative consumers используют typed resolver.
- [ ] Three geometry families имеют law + FIXED case.
- [ ] CENTER/PIN_END/PIN_BOTH/SCALE metamorphic tests green.
- [ ] Нет новых coordinate patches по этим families.

### Track 04

- [ ] Critical walks cycle-safe.
- [ ] DefinitionKey исключает last-wins на всех authoritative mappings.
- [ ] Early bijection работает до Dart render.
- [ ] PlannedDartGraph остаётся projection gate.
- [ ] Discriminator закрывает status/tab false merge без screen-specific fields.
- [ ] Asset index/budget evidence опубликован.

### Track 05

- [ ] Ownership overlay создаёт пять fixture families в report-only mode.
- [ ] Ownership on/off даёт идентичный Dart в P0.
- [ ] Reconcile registry содержит ≥3 declared conflict surfaces.
- [ ] Chooser работает только на ambiguous subtrees.
- [ ] Score breakdown и abstain проверены tests.
- [ ] Numeric chooser merge произошёл после 06-P0-1.

### Global gates

- [ ] `defects validate` green.
- [ ] Targeted bundles green.
- [ ] M2 regressions green.
- [ ] M2 final stamp закрыт до M3 enforce/signoff.
- [ ] Full signoff выполнен либо blockers явно classified в acceptance report.
- [ ] Golden refresh не использовался для маскировки regression.
- [ ] Новых screen-specific patches нет.

---

## 13. Implementation checklist

1. [ ] Commit 0: execution spec + RFC + contract stubs.
2. [ ] 06-P0-0a: consumer inventory + ratchet.
3. [ ] 06-P0-0b: geometry contract.
4. [ ] 04-P0-0: cluster contract (parallel).
5. [ ] 04-P0-1: cycle-safe critical walks.
6. [ ] 04-P0-2: DefinitionKey topology split.
7. [ ] 04-P0-3: ClusterExtractionPlan + early bijection.
8. [ ] 04-P0-4: discriminator.
9. [ ] 04-P0-5: asset index + budget.
10. [ ] 06-P0-1: AxisConstraint + resolver + law/case.
11. [ ] 06-P0-2: absolute→flow provenance + law/case.
12. [ ] 06-P0-3: viewport region owner + law/case.
13. [ ] 05-P0-0: layout hypothesis contract.
14. [ ] 05-P0-1: ownership sidecar report-only.
15. [ ] 05-P0-2: reconcile inventory/conflicts.
16. [ ] 05-P0-3: five ownership diagnostic laws.
17. [ ] 05-P0-4: scorer after resolver gate.
18. [ ] M3 acceptance report + signoff.

---

## 14. История

| Date | Change |
|---|---|
| 2026-07-03 | Initial M3 draft after Programs 04–06 investigation |
| 2026-07-03 | Consilium v2: early bijection, DefinitionKey, consumer ratchet, parameterized constraints, score breakdown, ownership/replan sequencing |
| 2026-07-03 | Final v2.1: M2 conditional prerequisite, stable law IDs, ownership strict report-only, split 05 gates, explicit plan model, reordered 04, generated/scored candidate budgets, abstain DoD, real M2 regression bundle |
