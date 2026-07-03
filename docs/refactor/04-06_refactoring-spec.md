# Техническое задание: рефакторинг программ 04–06

## 1. Назначение

Настоящее техническое задание определяет целевую архитектуру и порядок рефакторинга следующих областей компилятора:

- **Program 04** — extraction и dedup как стабильное взаимно-однозначное отображение между call sites и generated definitions;
- **Program 05** — visual ownership и выбор layout-гипотез;
- **Program 06** — алгебра geometry constraints и единый commit point для `LayoutSlotIr`.

Документ объединяет программы 04–06 в один исполняемый план. Исследовательские документы остаются источниками наблюдений и гипотез, а это ТЗ является нормативным документом для реализации, тестирования и приёмки.

## 2. Исходная проблема

Текущий pipeline уже содержит существенную часть необходимых механизмов: structural clustering, annotation extraction, component-backed extraction, dual-graph IR passes, geometry planner, conservation laws и planned Dart graph validation.

Однако ответственность между этапами распределена неоднозначно:

1. Cluster identity может зависеть от порядка обхода дерева.
2. Extraction correctness частично восстанавливается после генерации Dart.
3. Visual ownership реконструируется несколькими несогласованными эвристиками.
4. Layout выбирается преимущественно как цепочка predicate/veto, а не как сравнение альтернативных гипотез.
5. Figma constraints частично сводятся к статическим offsets.
6. Geometry planning может выполняться до поздних структурных или placement-мутаций.
7. Emitter и reconcile-слои сохраняют возможность повторно интерпретировать layout intent.

Следствием являются нестабильные widget identities, stale delegates, post-hoc repair, wrong merge/split, wrong pin/center, phantom gaps, поздняя перепланировка geometry и рост screen/archetype-specific компенсаторов.

## 3. Целевая модель pipeline

```text
CleanDesignTree facts
    ↓
Canonical extraction identity
    ↓
ExtractionPlan (definitions + call sites + dependency DAG)
    ↓
VisualOwnershipOverlay
    ↓
Layout candidate generation
    ↓
Constraint compilation and residual evaluation
    ↓
Candidate score + deterministic choice or abstain
    ↓
Geometry commit → LayoutSlotIr
    ↓
Emit without layout guessing
    ↓
PlannedDartGraph validation
```

Ключевой принцип:

> Каждый этап либо сохраняет факты, либо выполняет именованное преобразование с typed reason, provenance и исполняемым законом. После geometry commit структурные и placement-мутации запрещены.

## 4. Границы работ

### 4.1. В scope

- стабильная canonical identity extracted definitions;
- формальная модель `ExtractionPlan`;
- проверка bijection, closure и acyclicity до Dart emit;
- формальная классификация полей signature;
- visual ownership как overlay над clean tree;
- candidate-based layout inference для неоднозначных subtree;
- scorecard, hard veto и abstain policy;
- сохранение семантики Figma constraints (`CENTER`, `BOTTOM`, `LEFT_RIGHT`, `TOP_BOTTOM`, `SCALE`);
- единый geometry commit point;
- freshness validation для `LayoutSlotIr`;
- удаление layout guessing из emitter;
- перевод post-hoc repairs в diagnostic/degraded fallback;
- corpus, regression и performance gates.

### 4.2. Не в scope

- полный CSS constraint solver;
- глобальный combinatorial search по всему экрану;
- автоматическое проектирование responsive breakpoints без явных фактов;
- расширение native semantic emit;
- массовая замена golden baselines для получения зелёной приёмки;
- дизайн-системный catalog generation;
- LLM как источник geometry, ownership или extraction authority;
- screen-specific coordinate patches.

## 5. Обязательные предварительные условия

До включения новых преобразований в enforce-режим должны быть выполнены следующие условия:

1. Закрыт `LAW-A1-DROP-VISIBLE`: clean node не может исчезнуть без explicit omission permit или typed deviation.
2. GitHub Actions выполняет remote lint/signoff на pull request и push в default branch.
3. Pass contracts расширены минимум полями `phase`, `reads` и `writes`.
4. Поздние layout/geometry mutators инвентаризированы и привязаны к фазам.
5. Любой новый механизм сначала доступен в `report_only` или `shadow` режиме.

Невыполнение этих условий не блокирует подготовку моделей и тестов, но блокирует изменение production output.

---

# 6. Program 04 — canonical extraction identity и bijection

## 6.1. Цель

Сделать extraction отдельным проверяемым compiler plan, в котором:

- каждая generated definition имеет стабильный identity;
- каждый extracted call site указывает ровно на одну definition;
- каждая definition имеет минимум один call site;
- dependency graph definitions является DAG;
- source subtree и assets входят в проверяемую closure;
- Dart emit не используется для восстановления extraction decisions.

## 6.2. Новые модели

Рекомендуемое размещение: `generator/widget_extraction/`.

```python
@dataclass(frozen=True)
class ExtractionDefinition:
    definition_id: str
    class_name: str
    file_path: str
    source_node_id: str
    source_kind: str
    signature_version: str
    dependencies: frozenset[str]


@dataclass(frozen=True)
class ExtractionCallSite:
    node_id: str
    definition_id: str
    parameter_values: Mapping[str, object]


@dataclass(frozen=True)
class ExtractionPlan:
    definitions: Mapping[str, ExtractionDefinition]
    call_sites: Mapping[str, ExtractionCallSite]
    source_subtree_ids: frozenset[str]
    asset_keys: frozenset[str]
```

Pydantic-модели допустимы вместо dataclass, если требуется сериализация snapshots. Смысл и инварианты обязательны независимо от реализации.

## 6.3. Canonical definition ID

Numeric IDs вида `cluster_0`, `cluster_1` не должны быть authoritative identity.

Definition ID должен быть content-addressed или source-addressed:

```text
struct_<signature-version>_<signature-prefix>
component_<component-id>_<topology-or-variant-signature>
annotation_<canonical-widget-name>_<source-node-id>
semantic_<source-node-id>_<classifier-version>
```

Требования:

- добавление несвязанного sibling subtree не меняет ID существующих definitions;
- изменение параметризуемого текста не меняет shape definition ID;
- изменение identity-bearing geometry/style поля меняет exact definition ID;
- разные extraction sources не создают две definitions для одного claimed node;
- collision обнаруживается до emit и завершается typed error.

## 6.4. Signature specification

Должен быть создан документ `docs/refactor/contracts/cluster_signature.md`.

Для каждого поля `CleanDesignTreeNode` должна быть указана роль:

| Роль | Значение |
|---|---|
| `identity` | различие требует split definitions |
| `parameter` | различие допустимо в одной definition через parameter |
| `ignored` | различие не влияет на extraction identity |
| `forbidden_to_collapse` | nodes запрещено объединять независимо от общей shape |

Минимально должны быть определены три signatures:

1. `exact_signature` — фактическая эквивалентность subtree;
2. `shape_signature` — структура с параметризуемыми значениями;
3. `component_identity` — Figma component/instance authority.

В specification обязательно рассматриваются:

- node type;
- child topology и order;
- sizing и constraints;
- stack placement semantics;
- style shell;
- text literals;
- image/vector asset identity;
- interaction role;
- component/variant metadata;
- extraction boundary;
- viewport/chrome ownership role.

## 6.5. Extraction laws

### `LAW-EXTRACT-ID-STABLE`

Canonical definition ID не зависит от порядка обхода или наличия несвязанных subtree.

### `LAW-EXTRACT-BIJECTION`

Каждый call site с `extracted_widget_ref` разрешается ровно в одну definition. Каждая definition имеет минимум один call site.

### `LAW-EXTRACT-DAG`

Dependency graph definitions не содержит self-reference и циклов.

### `LAW-EXTRACT-SOURCE-CLOSURE`

Каждый `source_node_id` существует в canonical clean-tree index либо имеет compiler-synthesized provenance permit.

### `LAW-EXTRACT-ASSET-CLOSURE`

Каждый asset, необходимый definition, присутствует в plan asset set или передан как typed parameter.

### `LAW-EXTRACT-CLAIM-UNIQUE`

Один clean node не может одновременно принадлежать нескольким authoritative extraction sources.

### `LAW-EXTRACT-NO-POSTHOC-REPAIR`

Production path не создаёт недостающие definitions на основании regex-анализа generated Dart. Existing repair разрешён только в `diagnostic`/`degraded` режиме и обязан выдавать typed deviation.

## 6.6. Cycle-safe traversal

Все обходы, участвующие в signatures, extraction, assets и dependency analysis, должны использовать единый cycle-safe traversal или предварительно validated immutable index.

Запрещено добавлять новую рекурсивную walk-функцию без одного из условий:

- используется общий `walk_clean_tree`;
- передаётся explicit visited/path set;
- функция работает по уже проверенному acyclic snapshot.

## 6.7. Приёмка Program 04

- cluster/definition IDs стабильны при insertion независимого sibling;
- regression закрывает empty body, self-recursion и two-definition split;
- missing definition ловится до `render_widget_file`;
- regex materialization не вызывается в normal production path;
- каждый plan проходит bijection/DAG/source/asset closure;
- `food_add_new_items` и `9_a_home_bottom_navigation` проходят plan stage менее чем за 30 секунд каждый на reference CI runner;
- приёмка не требует обновления golden baselines.

---

# 7. Program 05 — visual ownership и layout hypothesis selection

## 7.1. Цель

Отделить визуальную принадлежность от Figma parenthood и заменить cascade специальных layout decisions на ограниченный выбор объяснимых кандидатов.

## 7.2. Visual ownership overlay

Visual ownership не создаёт третье mutable дерево. Он хранится как derived overlay:

```python
@dataclass(frozen=True)
class VisualOwnershipEdge:
    owner_id: str
    owned_id: str
    relation: str
    evidence: Mapping[str, object]
    confidence: float
    source: str
```

Минимальные relations:

- `surface_of`;
- `content_of`;
- `label_of`;
- `value_of`;
- `glyph_of`;
- `decoration_of`;
- `chrome_of`;
- `viewport_overlay_of`.

Ownership inference использует только compiler-observable facts. LLM может предложить annotation, но не является authority.

## 7.3. Ownership laws

### `LAW-OWNERSHIP-UNIQUE`

У owned node может быть не более одного structural owner для одной relation family.

### `LAW-OWNERSHIP-DAG`

Ownership graph ацикличен.

### `LAW-OWNERSHIP-BOUNDARY`

Ownership edge не пересекает extraction/render boundary без typed permit.

### `LAW-OWNERSHIP-PAINT-ORDER`

Paint order внутри ownership island сохраняет canonical stack order, если named transform явно не задаёт иной порядок.

### `LAW-OWNERSHIP-NO-REPARENT`

Построение overlay не меняет Figma parent facts. Reparenting допустим только на layout commit как named transform с provenance.

Минимальный набор ownership regressions:

- card surface ↔ content;
- icon plate ↔ glyph;
- bottom navigation substrate ↔ destinations;
- field shell ↔ value/label;
- scroll body ↔ viewport chrome.

## 7.4. Layout candidates

Для неоднозначного subtree создаётся несколько кандидатов:

```python
@dataclass(frozen=True)
class LayoutCandidate:
    candidate_id: str
    root_node_id: str
    target_layout: str
    ownership_edges: tuple[VisualOwnershipEdge, ...]
    constraint_plan: object
    score: object
    evidence: Mapping[str, object]
    rejection_reasons: tuple[str, ...]
```

Минимальные candidate families:

- preserve stack;
- row;
- column;
- wrap/grid-like grouping;
- scroll body + fixed overlay;
- ownership-grouped stack/flex hybrid.

Candidate generation выполняется только для ambiguous subtree. Однозначные canonical layouts не должны проходить global search.

## 7.5. Hard veto

Кандидат отклоняется до scoring, если он:

- теряет clean nodes без omission permit;
- нарушает paint order;
- создаёт ownership cycle;
- нарушает extraction boundary;
- создаёт недопустимый Flutter parent-data relation;
- требует отрицательных/неограниченных размеров без explicit degraded policy;
- уничтожает viewport pin;
- изменяет semantic/control kind вне разрешённого scope.

## 7.6. Scorecard

Score обязан хранить компоненты, а не только итоговое число:

```text
hard_fact_loss
geometry_residual
ownership_violations
exceptional_offset_count
flutter_invalidity
wrapper_complexity
responsive_instability
paint_order_deviation
```

Правила:

- `hard_fact_loss` и `flutter_invalidity` фактически являются veto;
- geometry residual вычисляется через constraint kernel Program 06;
- semantic/archetype similarity может быть supporting evidence, но не компенсирует потерю фактов;
- итоговый winner сопровождается score breakdown и margin относительно второго кандидата.

## 7.7. Abstain policy

Если:

- ни один кандидат не проходит hard veto;
- winner margin меньше установленного порога;
- geometry residual превышает допустимый budget;
- required ownership остаётся неоднозначным;

компилятор выбирает deterministic structural fallback и записывает typed `layout_abstain` diagnostic. Молчаливый выбор heuristic candidate запрещён.

## 7.8. Reconcile registry

Существующий registry должен быть переведён на единый pass contract. Каждый transform объявляет:

```text
name
phase
reads
writes
mutates
preserves
requires
conflicts_with
priority
activation
```

Требования:

- registry является единственным источником orchestration order;
- зарегистрированный pass не может вызываться отдельно вне registry без explicit exception;
- duplicate invocation и registry drift ловятся тестом;
- product hero, bottom nav, grid и field transforms переводятся в общую фазовую модель;
- новые screen-specific pass names запрещены.

## 7.9. Search budget

Полный combinatorial search запрещён.

Default limits:

- не более 4 candidates на subtree;
- beam width не более 3;
- hard veto до expensive scoring;
- memoization ownership islands и geometry residual;
- общий candidate-search budget фиксируется в diagnostics.

Изменение лимитов требует benchmark evidence.

## 7.10. Приёмка Program 05

- пять ownership law families покрыты unit/regression tests;
- ambiguity fixture создаёт минимум два валидных кандидата;
- winner содержит score breakdown и margin;
- low-margin fixture приводит к abstain, а не к heuristic commit;
- reconcile registry и фактическая orchestration совпадают;
- exceptional offset count на corpus sample уменьшается без golden update;
- ни один новый screen-specific reconcile не добавлен.

---

# 8. Program 06 — constraint algebra и geometry commit

## 8.1. Цель

Сохранить resize intent Figma до emit и установить один момент, после которого layout/geometry считается committed и больше не переинтерпретируется.

## 8.2. Axis constraint model

Минимальная алгебра на каждой оси:

```text
FixedStart(offset, size)
FixedEnd(offset, size)
Stretch(start, end)
Center(delta, size)
Scale(start_ratio, size_ratio)
Intrinsic
Fill
FlowSlot
ViewportPin(edge, inset, size)
```

Требования:

- `CENTER` не сводится к статическому `left + width`;
- `SCALE` не сводится к статическому `left + width/height`;
- `BOTTOM` сохраняет bottom-relative semantics;
- `LEFT_RIGHT`/`TOP_BOTTOM` компилируются в stretch constraints;
- static position хранится отдельно от resize operator;
- viewport-owned pins явно отличаются от parent-owned offsets.

## 8.3. Размещение моделей

Рекомендуемая структура:

```text
schemas/constraints.py
generator/geometry/constraints.py
generator/geometry/solver.py
generator/geometry/commit.py
generator/geometry/residual.py
```

Допускается иное разбиение, если сохраняются boundaries:

1. parse facts;
2. compile constraints;
3. solve/evaluate;
4. commit slots;
5. emit mapping.

## 8.4. Geometry candidate evaluation

Constraint kernel обязан уметь оценить layout candidate без изменения canonical tree:

```python
GeometryEvaluation(
    feasible: bool,
    residual_max_px: float,
    exceptional_offsets: int,
    overflow_px: float,
    invalid_relations: tuple[str, ...],
)
```

Evaluation используется Program 05 scorecard.

## 8.5. Geometry commit

После выбора layout candidate выполняется единственный `geometry_commit`:

```text
selected layout structure
+ ownership overlay
+ axis constraints
→ LayoutSlotIr on every consumable node
→ commit fingerprint
```

`LayoutSlotIr` или связанный plan stamp должен содержать `source_fingerprint`, рассчитанный минимум из:

- node ID;
- parent ID;
- node type/layout backend;
- sizing;
- stack placement/constraints;
- geometry frame inputs;
- ownership/layout role;
- ordered child IDs.

## 8.6. Geometry laws

### `LAW-CONSTRAINT-SEMANTICS`

Compiler mapping сохраняет meaning исходного constraint operator при изменении parent size.

### `LAW-GEOMETRY-SLOT-COMPLETE`

Каждый consumable node после commit имеет валидный `LayoutSlotIr` либо explicit boundary/degraded permit.

### `LAW-GEOMETRY-SLOT-FRESH`

`source_fingerprint` slot совпадает с текущими structural/geometry facts.

### `LAW-GEOMETRY-COMMIT-BARRIER`

После commit запрещены изменения parenthood, child order, type, sizing, placement, constraints и ownership/layout role.

### `LAW-ABSOLUTE-TO-FLOW-NAMED`

Absolute→flow выполняется только named transform с provenance, before/after snapshots и residual check.

### `LAW-VIEWPORT-OWNERSHIP`

Viewport chrome и viewport inset не могут быть повторно присвоены flow parent.

### `LAW-EMIT-NO-GEOMETRY-GUESS`

Emitter не рассчитывает новый pin, center, gap, scroll ownership или backend, если это не выражено в committed slot.

## 8.7. Late mutation policy

Existing late mutators должны быть классифицированы:

1. перенесён до candidate selection;
2. включён как candidate transform;
3. перенесён до geometry commit;
4. удалён как redundant;
5. временно инвалидирует slots и централизованно вызывает replan с typed deviation.

Локальный silent replan запрещён.

`replan_geometry_after_layout_passes` допускается только как временная migration boundary. Конечное состояние — один commit после всех structural transforms.

## 8.8. `preserve_placement`

Многозначный boolean должен быть заменён или обёрнут typed policy:

```python
@dataclass(frozen=True)
class GeometryPolicy:
    fact_mode: str
    allowed_transforms: frozenset[str]
    placement_clamp: str
    responsive_mode: str
```

До полной миграции старый флаг может поддерживаться на boundary, но compiler internals должны получать resolved policy object.

## 8.9. Responsive MVP

В рамках Program 06 поддерживается:

- один structural topology;
- resize через preserved constraints;
- explicit adaptive rules;
- explicit Figma variants/breakpoints.

Автоматическое изменение topology по произвольным ширинам не входит в MVP.

## 8.10. Приёмка Program 06

- CENTER остаётся центрированным при минимум трёх parent widths;
- BOTTOM сохраняет inset при изменении parent height;
- STRETCH сохраняет оба inset;
- SCALE изменяет offset и size пропорционально parent span;
- late structural mutation после commit вызывает typed violation;
- emitter tests подтверждают отсутствие fallback к raw `StackPlacement` при наличии committed slot;
- top-3 geometry failure families закрыты law + regression;
- transaction, home и food testbeds проходят geometry invariants без новых magic coordinates.

---

# 9. Milestones и порядок реализации

## M0 — Prerequisite hardening

- remote CI;
- `LAW-A1-DROP-VISIBLE`;
- pass phases/reads/writes;
- late-mutator inventory;
- shadow/report-only infrastructure.

## M1 — Canonical identity

- signature contract;
- stable IDs;
- compatibility mapping старых cluster IDs;
- stability tests.

## M2 — ExtractionPlan

- models;
- bijection/DAG/closure validators;
- normal path до Dart emit;
- diagnostic-only post-hoc repair.

## M3 — Ownership overlay

- edge model;
- five ownership families;
- ownership laws;
- diagnostics and snapshots.

## M4 — Constraint kernel

- axis operators;
- compile from existing facts;
- residual evaluator;
- CENTER/SCALE/BOTTOM/STRETCH regressions.

## M5 — Layout candidates

- candidate generation;
- hard veto;
- scorecard;
- winner margin;
- abstain policy.

## M6 — Geometry commit

- selected candidate → slot plan;
- source fingerprints;
- commit barrier;
- late-mutator migration.

## M7 — Emitter and repair burn-down

- emitter consumes committed slot only;
- registry drift removed;
- screen/archetype patches migrated or deleted;
- repair fallbacks downgraded to diagnostics.

## M8 — Corpus acceptance

- corpus comparison;
- performance budgets;
- no unauthorized golden updates;
- enforce-mode rollout.

---

# 10. Rollout strategy

Каждый новый механизм проходит стадии:

```text
off → report_only → shadow → enforce
```

### `report_only`

Строит plans/edges/candidates и diagnostics, не меняя output.

### `shadow`

Сравнивает новый результат с production path, считает residual, node/asset closure, paint order и corpus impact.

### `enforce`

Новый путь становится authority. Старый путь остаётся только как named degraded fallback на ограниченный срок.

Silent fallback запрещён. Каждый fallback содержит:

- reason code;
- affected node IDs;
- failed law;
- selected fallback path;
- provenance record.

---

# 11. Тестовая стратегия

## 11.1. Unit tests

- signature partition;
- stable IDs;
- DAG/bijection validators;
- ownership laws;
- candidate veto/score/abstain;
- axis constraint operators;
- slot freshness.

## 11.2. Metamorphic tests

- insertion независимого sibling не меняет existing IDs;
- text parameter variation не меняет shape identity;
- изменение parent size сохраняет constraint semantics;
- permutation unrelated subtree не меняет selected candidate;
- repeated planning является idempotent.

## 11.3. Regression tests

Минимальные failure families:

- empty extracted body;
- self-recursive delegate;
- wrong split/merge;
- card surface/content siblings;
- icon plate/glyph ownership;
- bottom nav inside scroll body;
- centered glyph/button drift;
- bottom-pinned bar drift;
- absolute→flow phantom gap;
- stale `LayoutSlotIr` после позднего reconcile.

## 11.4. Corpus gates

Для каждого milestone сохраняются:

- node multiset;
- paint order;
- omission permits;
- extraction closure;
- ownership violations;
- geometry residual;
- exceptional offset count;
- output file graph;
- runtime budget.

Golden updates не являются способом закрытия regression. Любое обновление baseline рассматривается отдельно и требует объяснения изменения design truth.

## 11.5. Performance gates

Измеряются отдельно:

- signature/index build;
- extraction validation;
- ownership inference;
- candidate generation;
- constraint evaluation;
- geometry commit;
- Dart emit.

Минимальные требования:

- отсутствие сверхлинейного full-tree × asset scan в normal path;
- candidate count bounded;
- plan stage для указанных smoke fixtures < 30 секунд;
- performance regression > 20% блокирует enforce rollout без отдельного решения.

---

# 12. Диагностика и observability

Для каждого экрана должен формироваться machine-readable audit snapshot:

```text
extraction_plan.json
ownership_overlay.json
layout_candidates.json
geometry_evaluation.json
geometry_commit.json
```

Snapshots должны включать:

- schema/version;
- source clean-tree fingerprint;
- selected decision;
- rejected alternatives;
- score breakdown;
- law violations;
- fallback/degraded reasons;
- elapsed time по фазам.

Запрещено использовать snapshots как новый source of truth для следующей генерации без отдельного cache contract.

---

# 13. Миграция существующего кода

## 13.1. Сохраняемые механизмы

- current annotation extraction;
- component-backed extraction;
- shape parameterization;
- conservation law registry;
- pass mutation contracts;
- geometry frames и affine planner;
- planned Dart graph validation.

## 13.2. Механизмы на миграцию

- numeric cluster IDs;
- recursive ad-hoc walks;
- `materialize_missing_cluster_delegate_files` как normal repair;
- manual reconcile order;
- independently invoked registered passes;
- predicate-first layout selection;
- CENTER/SCALE flattening;
- late geometry mutation;
- direct emitter interpretation of placement facts;
- multi-purpose `preserve_placement` boolean.

## 13.3. Механизмы на удаление после burn-down

Удаление выполняется только после corpus evidence:

- screen-specific coordinate maps;
- hardcoded asset-pair exceptions;
- duplicate ownership heuristics;
- dead emit branches, недостижимые из schema;
- silent geometry replanning;
- post-Dart extraction materialization.

---

# 14. Deliverables

1. `docs/refactor/contracts/cluster_signature.md`.
2. `docs/refactor/contracts/visual_ownership.md`.
3. `docs/refactor/contracts/layout_hypothesis.md`.
4. `docs/refactor/contracts/geometry_algebra.md`.
5. `ExtractionPlan` models и validators.
6. Ownership overlay models и laws.
7. Layout candidate/score/abstain models.
8. Axis constraint kernel и residual evaluator.
9. Geometry commit/freshness implementation.
10. Pass registry migration.
11. Emitter no-guess gates.
12. Audit snapshots.
13. Unit, metamorphic, regression, corpus и performance tests.
14. Migration report со списком удалённых/оставшихся compensators.

---

# 15. Definition of Done для эпика 04–06

Эпик считается завершённым, когда одновременно выполняются условия:

- extraction identity стабильна и versioned;
- extraction graph проходит bijection, DAG и closure до emit;
- normal production path не восстанавливает definitions из generated Dart;
- ownership является typed overlay и проходит пять базовых law families;
- ambiguous subtree сравнивает не менее двух кандидатов либо документированно не является ambiguous;
- layout winner имеет score breakdown и confidence margin;
- low-confidence decision приводит к abstain;
- CENTER, BOTTOM, STRETCH и SCALE сохраняют resize semantics;
- geometry имеет один commit point;
- slot freshness проверяется перед emit;
- после commit отсутствуют structural/placement mutations;
- emitter не принимает layout decisions;
- remote CI и corpus gates воспроизводимы;
- required fixtures проходят performance budgets;
- acceptance не основана на массовом обновлении golden;
- новые screen-specific patches отсутствуют;
- оставшиеся degraded fallbacks перечислены, типизированы и имеют срок burn-down.

## Итоговый архитектурный принцип

```text
Identity определяет, что переиспользуется.
Ownership определяет, что визуально принадлежит друг другу.
Layout hypotheses определяют возможную структуру.
Constraint algebra определяет поведение при размере.
Geometry commit фиксирует единственный emit plan.
Emitter исполняет plan и не гадает.
```
