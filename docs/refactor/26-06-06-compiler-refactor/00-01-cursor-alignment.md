# Согласование Program 00 (corpus) и Program 01 (IR contract)

**Для:** Коля, Cursor-сессии, два коллеги-агента (GPT analysis + Program 01 track).  
**Статус:** рабочая карта; не заменяет детальные ТЗ.

| Документ | Роль |
|----------|------|
| [00_defect-taxonomy-corpus.md](00_defect-taxonomy-corpus.md) | RAR program 00 — исследование/анализ |
| GPT Phase 2 analysis + Batch 0–7 ТЗ | Рефакторинг corpus (модели, CLI, Cursor hooks) |
| [01_compiler-semantics-ir-contract.md](01_compiler-semantics-ir-contract.md) | RAR program 01 — исследование/анализ |
| [01_refactoring-spec-cursor.md](01_refactoring-spec-cursor.md) | Рефакторинг IR contract (P0–P2 инкременты) |
| [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md) | Матрица стрелок и named laws |

---

## 1. Главное: не конкурируют, а стыкуются

| Вопрос | Program 00 (GPT) | Program 01 (наш track) |
|--------|------------------|------------------------|
| **Что измеряем** | *Какие families* жрут `/repair` (frequency × blast) | *На какой стрелке* теряется факт (A1–A3) |
| **Артефакт** | `corpus/`, `figma-flutter defects` | `PIPELINE_ARROWS.md`, laws в коде |
| **Выход для продукта** | Ranked backlog из доказанных cases | Меньше compensator, больше `GenerationError` / `DeviationRecord` |
| **Cursor hook** | diagnose classifies → repair records case YAML | repair фиксит **owning layer** по arrow routing |

**Совместный тезис (оба согласны):**

- Emitter «виноват» редко сам по себе — чаще **information loss** раньше по pipeline.
- **Symptom ≠ family** (`hang`, `overflow`, `wrong_checkbox` — распадаются).
- **Named laws уже в коде**, но **не проиндексированы** в едином corpus.
- **80% `/repair` time** без occurrence journal **утверждать нельзя** — только стартовый рейтинг.

---

## 2. Согласованный стартовый рейтинг (GPT) ↔ наши стрелки

| GPT P0 family (ожидание) | Стрелка Program 01 | Уже есть law / gate | Corpus family id (00) |
|--------------------------|--------------------|---------------------|------------------------|
| Layout / Flutter constraints | A2, A3, static_gate | planned Dart laws, geometry invariants | `nested_flex_parent_data`, `loose_flex_infinite_width` |
| Semantic FP upgrade | A3 read + classify | `inv_classification_scope`, semantics corpus | `semantic_false_positive`, `classification_scope_violation` |
| Graph conservation desync | **A1, A1b**, CP2 | `inv_graph_sync`, `inv_node_multiset` | `graph_sync_violation`, `node_multiset_loss` |
| Planned Dart graph break | planned_reconcile | `PlannedDartGraphError` laws | `missing_widget_definition`, `planned_widget_graph_cycle`, … |
| Asset identity | parse/dedup/assets | asset index, prune binding | `asset_*` families |

**Где расходимся по emphasis (не по сути):**

- GPT ставит **layout/constraints №1** по repair burden.
- Program 01 ставит **A1/A1b merge+reconcile** как корень «emitter bugs» (information loss до emit).

**Синтез:** layout падает в runtime/analyze (**B3**) — заметно сразу. Graph desync и semantic FP (**B2**) — **silent wrong behavior**, дольше охотятся. Оба top-tier; разный **blast shape**, не взаимоисключение.

---

## 3. Families 00, которые кормят Program 01 напрямую

При закрытии P0–P2 в [01_refactoring-spec-cursor.md](01_refactoring-spec-cursor.md) **обязательно** заводить/обновлять cases:

| Program 01 law / gap | Corpus `family_id` | `law_ids` | `owning_stage` |
|----------------------|-------------------|-----------|----------------|
| LAW-A1-OVERRIDE-PROV | новый: `ir_override_without_provenance` | — (пока) + link `inv_style_truth` | `ir_validation` / merge |
| LAW-A1-DROP-VISIBLE | `node_multiset_loss` или новый: `ir_merge_silent_drop` | `inv_node_multiset` | `ir_pass` |
| A1b compensator drops | `graph_sync_violation` | `inv_graph_sync` | `ir_validation` |
| LAW-PASS-CONTRACT | `pass_over_mutation` | `pass_over_mutation` | `ir_pass` |
| stackChildOrder | `stack_paint_order_drift` | `inv_stack_paint_order` | `ir_pass` |

До **Batch 1 Program 00** cases пишутся вручную в `corpus/cases/` по шаблону коллеги; после Batch 1 — через `defects validate`.

---

## 4. Origin tags — согласны

| GPT | Program 01 / bible | Решение |
|-----|-------------------|---------|
| Убрать `FIDELITY_DEFERRED` из origin | fidelity = tier downgrade, не origin | **Принять** → `DEFERRED_BY_POLICY` в status |
| `COMPILER` требует loss_boundary | Master Invariant: fact / deviation / downgrade | **Принять** — совпадает с `loss_boundary` в case YAML |
| `AMBIGUOUS` при нехватке evidence | diagnose не додумывает | **Принять** |

---

## 5. Порядок работ в Cursor (не один ведро)

```text
Параллельно (можно разными чатами):
  Program 00 Batch 0–1     → defects models + families.yaml
  Program 01 P0-1          → LAW-A1-OVERRIDE-PROV (provenance на merge)

После Batch 1 (00):
  Program 01 P1-3          → case YAML для ir_override / merge_drop
  Program 00 Batch 2–4     → validate + CLI

После Batch 4 (00):
  Program 00 Batch 5       → diagnose/repair skills + corpus record
  Program 01 P1–P2         → merge drop law, IR-side pass contract

Backfill (00 Batch 6):
  Приоритет families с пересечением 01: graph_sync, node_multiset, semantic_fp, static flex
```

**Program 01 P0-1 не блокируется Program 00** — только ручной case YAML откладывается до Batch 1.

---

## 6. Единый Cursor workflow (после Batch 5)

### `/diagnose` (read-only)

Обязательный блок **DEFECT CORPUS CLASSIFICATION** (GPT) **+** **PIPELINE ARROW** (01):

```text
occurrence:
  family_id: graph_sync_violation
  stage: ir_validation
  origin: COMPILER
  blast_radius: B3_BLOCKING
  confidence: high
  pipeline_arrow: A1b          # ← добавка Program 01
  law_id: inv_graph_sync
  loss_boundary: ...
corpus_status: ready_for_record | needs_evidence | unclassified
```

### `/repair` (mutate compiler + corpus)

Definition of done = **объединение** обоих ТЗ:

```text
generic fix в owning layer (01 routing table)
AND regression test (01)
AND case YAML + defects validate (00)
AND при COMPILER — loss_boundary или named law (00)
AND при fact override — DeviationRecord (01 P0)
```

---

## 7. Что дополнить в ТЗ коллеги (Program 00)

Рекомендуемые дополнения к Batch 1–5 (не ломая scope):

1. **Поле `pipeline_arrow`** в occurrence: `A1` | `A1b` | `A2` | `A3` | `A4` | `static_gate` | …
2. **Ссылка на `law_ids` из** [PIPELINE_ARROWS.md §5](contracts/PIPELINE_ARROWS.md) при seed `ir_*` families.
3. **Seed family** `ir_override_without_provenance` (после P0-1).
4. В diagnose skill: `@refactor/contracts/PIPELINE_ARROWS.md` рядом с families.yaml.
5. **Не дублировать** `inv_graph_sync` и `graph_sync_violation` — family ссылается на law code.

---

## 8. Что дополнить в Program 01 ТЗ

Уже в [01_refactoring-spec-cursor.md](01_refactoring-spec-cursor.md); усилить:

1. P1-3 corpus — **ждать** `corpus/families.yaml` из Batch 1, не ad-hoc JSON.
2. Diagnose routing table — добавить колонку **`family_id` (00)** рядом со стрелкой.
3. Критерий готовности 01: cases с `pipeline_arrow` и `law_id`, не только pytest.

---

## 9. Риски расхождения (честно)

| Риск | Как не разъехаться |
|------|-------------------|
| Два parallel skill набора | Batch 0: `git ls-files .cursor` + `.claude/skills/` — один canonical path |
| Family по symptom | GPT запрет + 01 anti-patching — reject в review |
| 01 чинит без corpus | repair DoD без `defects validate` = незакрыт (00) |
| 00 пишет cases без compiler fix | FIXED без regression = invalid (00 validation) |
| GPT top-2 ≠ 01 P0 | backlog из **report** пересматривает приоритет P0/P1, не наоборот |

---

## 10. Рекомендация Коле (следующий ход)

**Сейчас в Cursor:**

```text
Чат A: @refactor/00-01-cursor-alignment.md + GPT Batch 0 prompt → разведка .cursor paths
Чат B: @refactor/01_refactoring-spec-cursor.md → P0-1 LAW-A1-OVERRIDE-PROV
```

После Batch 0+1 (00): один чат **Batch 5 + Program 01 P1-3** — skills и первые cases на graph/override.

**Не делать:** скармливать агенту оба полных ТЗ одним сообщением без alignment-файла.

---

## 11. Статус согласования

| Тема | Вердикт |
|------|---------|
| GPT Phase 2 analysis | **Принят** как стартовый рейтинг + taxonomy rules |
| GPT Batch 0–7 ТЗ | **Принят** как исполняемый Program 00 refactor |
| Program 01 analysis + PIPELINE_ARROWS | **Принят** как механизм layer/arrow |
| Конфликт приоритетов layout vs graph | **Снят** — разные оси (burden vs root cause) |
| `FIDELITY_DEFERRED` | **Снят** — origin vs status |
| Единый repair DoD | **Сформулирован** в §6 |
