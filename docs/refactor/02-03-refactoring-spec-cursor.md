# ТЗ: Program 02 + 03 — Conservation registry & classification gates (Cursor workflow)

**Программы:** [02_conservation-framework.md](02_conservation-framework.md), [03_classification-theory.md](03_classification-theory.md)  
**Стыковка с 00/01:** [00-01-cursor-alignment.md](00-01-cursor-alignment.md)  
**Контракт стрелок:** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md) · Cursor: `.cursor/rules/pipeline-contracts.mdc`  
**Статус:** executing Milestone 2 (Program 02 + 03)  
**Аудитория:** агент / инженер в Cursor, владелец продукта (обзор инкрементов)

---

## 1. Цель

Закрыть **silent information loss** (02) и **silent wrong semantic emit** (03) через:

1. единый **executable registry** conservation laws на границах стадий (`law_id` отдельно от `violation_codes`);
2. явный **omission contract** для легитимных потерь (prune, sectionize, cluster);
3. **classification playbook** (evidence + veto + gate) и corpus mechanism families;
4. единый **`PolicyDecision`** wrapper на границе classify → stamp → emit (основной semantic IR route в P0).

**Не цель:** переписать 44 detectors с нуля, formal proof, golden refresh, additive scoring (P2 hypothesis), Program 04 в том же PR.

### Разграничение taxonomy

```text
Family   — механизм поломки
Case     — конкретное воспроизведение механизма
Evidence spec — контракт, предотвращающий механизм
```

### Совместный тезис 02 + 03

| | Program 02 | Program 03 |
|---|------------|------------|
| Вопрос | Что потеряли по pipeline? | Кому разрешили kind и native emit? |
| Стрелки | A1, CP2, parse→normalize | **A3**, CP2 post-classify |
| Blast | B3 (multiset) / B2 (graph desync) | B2 (wrong widget class) |
| Сегодня | ~10 `check_*`, checkpoints CP2 | arbiter + abstain, triple gate emit |

Emitter редко «виноват сам» — чаще **ранняя потеря факта** или **преждевременный semantic upgrade**.

---

## 2. Scope

### In scope

| Track | Стрелки | Код |
|-------|---------|-----|
| **02** Conservation registry | parse, CP2, post-classify | `generator/geometry/invariants/` |
| **02** Pass contract (расширение) | CP2 | `generator/ir/passes/contract.py` |
| **02** Omission provenance | A1, parse, plan | `omit_figma_ids`, `DeviationRecord` |
| **03** Shadow inventory | A3 audit | `audit/shadow_classifier.py` |
| **03** Classification gates | A3, CP2 | `parser/semantics/`, `generator/ir/passes/semantic.py` |
| **03** Emit policy surface | A3 → emit | `expression.py`, `policy.py`, fidelity router |
| **00** Corpus | — | `corpus/families.yaml`, `corpus/cases/` |

### Out of scope (Milestone 2)

| Тема | Когда |
|------|-------|
| `semantic_conflict_without_arbiter_rule` family | **03-P1** (после inventory + detector trace) |
| Formal `CP3_post_emit` runner | **M2.1** unless audit proves escaping B2/B3 defect |
| Additive scoring changes | **03-P2** hypothesis |
| Widget extraction bijection | **04** |
| `LAYOUT_LAWS` / contract emit recipes (report-only) | не смешивать с conservation registry |

### Зависимости

- **Program 00** Batch 1–4 — **готово** (Milestone 1).
- **Program 01** P0 — **готово**.

---

## 3. Baseline (после Milestone 1)

| Артефакт | Путь | Статус |
|----------|------|--------|
| Conservation checks | `geometry/invariants/conservation.py` (~10 `check_*`) | есть, не в реестре |
| CP2 runner | `geometry/invariants/checkpoints.py` | CP2 + post-classify |
| Emit invariants | `geometry/emit_invariants.py` via `validate_geometry_invariants(layout_source=…)` | не orphaned |
| Classifier | `parser/semantics/` (~44 RuleDetectors) | merged |
| Corpus seed (02) | `node_multiset_loss`, `graph_sync_violation`, `pass_over_mutation` | families ✅ |
| Corpus seed (03) | mechanism families | **P0** |
| Shadow inventory | `audit/shadow_classifier.py` | **P0** |

---

## 4. Воркфлоу в Cursor

### 4.1 Поток

```text
/diagnose → /repair     compiler only
/debug → /fix           infra — не этот ТЗ
```

### 4.2 Старт сессии

```text
.cursor/rules/project-bible.mdc
.cursor/rules/pipeline-contracts.mdc
corpus/families.yaml
docs/refactor/02-03-refactoring-spec-cursor.md
AGENTS.md
```

### 4.3 Жёсткие правила

- Не смешивать `LAYOUT_LAWS` с `ConservationLaw` registry.
- `law_id` ≠ `violation_code` (registry хранит оба).
- Легитимная потеря узла **только** с `OmissionReason` + provenance (после 02-P0-2).
- Native semantic emit на основном route **только** через `PolicyDecision` wrapper (после 03-P0-3).
- Symptom families (`semantic_false_positive/negative`) **запрещены** — только mechanism families.
- Новый conservation check **без** `law_id` в registry — не merge.

---

## 5. Инкременты

Два параллельных трека. **Стык:** `check_ir_classification_scope` → registry 02 + family 03.

### Merge order (после Commit 0)

```text
spec-sync
  ↓
02-P0-1  (LAW-CP2-CLASSIFY-SCOPE в registry)
  ↓
03-P0-0  (можно разрабатывать параллельно; merge после 02-P0-1)
  ↓
02-P0-2 … 02-P0-4  ||  03-P0-1 … 03-P0-4
```

---

### Track 02 — Conservation registry

#### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **02-P0-1** | `ConservationLaw`: `law_id`, `violation_codes`, `check_fn`, `stage`, `severity`, `owner` | `geometry/invariants/registry.py` | ≥10 laws, behavior unchanged |
| **02-P0-2** | `OmissionReason` enum; wire sectionize, prune, cluster omit | `provenance.py`, `checkpoints.py`, `sectionize.py`, `prune.py` | omit без reason → BLOCK at CP2 |
| **02-P0-3** | `run_conservation_laws(stage, …)` facade | `checkpoints.py` | CP2 + post-classify через registry |
| **02-P0-4** | **4** FIXED corpus cases (02) | `corpus/cases/` | multiset, graph_sync, pass_over_mutation, + fourth |

**Verify 02-P0:**

```powershell
poetry run pytest tests/test_conservation_registry.py tests/test_conservation_invariants.py tests/test_cp_post_classify.py tests/test_ir_layout_passes.py tests/test_pass_contract.py -q
poetry run figma-flutter defects validate
```

#### P1 — widen + post-emit audit

| ID | Задача | DoD |
|----|--------|-----|
| **02-P1-1** | `stack_paint_order_drift` family + case | FIXED |
| **02-P1-2** | Runner hook после normalize | documented |
| **02-P1-3** | `@pytest.mark.conservation` | marker in signoff optional |
| **02-P1-4** | `ir_merge_visible_child_drop` case | FIXED |
| **02-P1-5** | Post-emit coverage audit | `docs/refactor/generated/post-emit-coverage.md` — routes table + 5 tests |

**Post-emit / CP3 boundary:**

```text
M2:     coverage audit + route-classification tests + explicit decision
M2.1:   formal CP3_post_emit only if audit finds uncovered route with escaping defect
```

`validate_emit_geometry_invariants` уже вызывается через `validate_geometry_invariants` когда передан `layout_source`.

---

### Track 03 — Classification gates

#### P0

| ID | Задача | Файлы | DoD |
|----|--------|-------|-----|
| **03-P0-0** | Machine-readable shadow inventory + baseline-only ratchet | `audit/shadow_classifier.py` | JSON canonical, MD derived |
| **03-P0-1** | **5** mechanism families | `corpus/families.yaml` | see list below |
| **03-P0-2** | **pilot-5** evidence specs | `tests/fixtures/layouts/semantics/evidence/` | chip, button, nav, checkbox, input |
| **03-P0-3** | `PolicyDecision` wrapper | `generator/ir/policy.py` | main semantic IR route only; unmigrated routes listed |
| **03-P0-4** | **3** FIXED corpus cases (03) | `corpus/cases/` | veto, candidate, root scope |

**03-P0-0 artifacts:**

| Artifact | Path | Role |
|----------|------|------|
| Canonical | `docs/refactor/generated/shadow-classifier-inventory.json` | CI parses |
| Derived | `docs/refactor/03-shadow-classifier-inventory.md` | review only |

**Categories:** `fact_reader` | `layout_policy` | `kind_decider` | `emit_archetype_decider` | `unknown`

**Baseline-only ratchet (P0):**

| Condition | CI |
|-----------|-----|
| New `kind_decider` vs baseline | FAIL |
| New `emit_archetype_decider` vs baseline | FAIL |
| New `unknown` vs baseline | FAIL |
| Record removed without baseline update | FAIL |
| Existing baseline entries | ALLOW |
| Baseline shrink (remediation) | ALLOW |

**03-P0-1 mechanism families (P0 minimum — 5):**

```text
semantic_upgrade_without_required_evidence
semantic_veto_not_applied
semantic_candidate_not_generated
classification_scope_violation
screen_root_scope_veto_missing
```

**Deferred to 03-P1:** `semantic_conflict_without_arbiter_rule`

**FIXED cases at P0 (3):** `semantic_veto_not_applied`, `semantic_candidate_not_generated`, `screen_root_scope_veto_missing`

**Family seeds (confirmed by end of M2):** `semantic_upgrade_without_required_evidence` (pilot evidence + test), `classification_scope_violation` (`check_ir_classification_scope` + post-classify tests)

**03-P0-3 PolicyDecision** — wrapper над цепочкой:

```text
report_only + classification status + fidelity tier + EmitPath
```

Не переделывать все emit call sites в P0.

**Verify 03-P0:**

```powershell
poetry run pytest tests/test_shadow_classifier_inventory.py tests/test_semantics_corpus.py tests/test_fidelity_authority.py tests/test_screen_root_nav_kind_laws.py tests/test_cp_post_classify.py -q
poetry run figma-flutter defects validate
```

#### P1 — deferred items

| ID | Задача |
|----|--------|
| **03-P1-0** | `semantic_conflict_without_arbiter_rule` (only after reproducible conflict in inventory) |
| **03-P1-1** | `evidence.node_ids` standard key in detectors |
| **03-P1-2** | Detector overlap CI |
| **03-P1-3** | Playbook generator roundtrip |

#### P2

- Additive scoring — **hypothesis only**, not M2
- FP/FN pairs per SEMANTIC_MVP kind (stretch)

---

## 6. Routing

| Симптом | Track | Первый файл |
|---------|-------|-------------|
| Child id пропал после pass | 02 | `check_node_multiset_preserved` |
| IR figmaId ∉ clean tree | 02 | `check_graph_sync` |
| Pass меняет undeclared field | 02 | `passes/contract.py` |
| Classify изменил clean tree | 02+03 | `check_clean_tree_unchanged` |
| Wrong chip / nav class | 03 | `parser/semantics/detectors/` |
| Screen root nav mislabel | 03 | `validate/root_kind.py` |
| Shadow decider in emit | 03 | `audit/shadow_classifier.py` |

---

## 7. Критерии готовности Milestone 2

M2 закрывается **только вместе**:

- [ ] ≥10 registered conservation laws (`law_id` + `violation_codes`)
- [ ] Typed omission coverage (sectionize, prune, cluster)
- [ ] CP2 + post-classify через `run_conservation_laws`
- [ ] **4** FIXED cases Program 02
- [ ] **3** FIXED cases Program 03
- [ ] Machine-readable shadow inventory JSON + generated MD
- [ ] Baseline-only ratchet (new deciders/unknown only)
- [ ] **5** active mechanism families
- [ ] **pilot-5** evidence specs under `tests/fixtures/layouts/semantics/evidence/`
- [ ] `PolicyDecision` на основном semantic emit route + unmigrated routes documented
- [ ] `defects validate` green
- [ ] Targeted pytest bundles (§8); full signoff before `main`

**Не в M2:** formal `CP3_post_emit` (unless escaping defect), `semantic_conflict_without_arbiter_rule`, additive scoring.

---

## 8. Gates

| Уровень | Команда |
|---------|---------|
| 02 fast | `pytest tests/test_conservation_registry.py tests/test_conservation_invariants.py tests/test_cp_post_classify.py tests/test_pass_contract.py -q` |
| 03 fast | `pytest tests/test_shadow_classifier_inventory.py tests/test_semantics_corpus.py tests/test_screen_root_nav_kind_laws.py tests/test_cp_post_classify.py -q` |
| Corpus | `figma-flutter defects validate` |
| Full | `.\scripts\signoff.ps1` |

---

## 9. Запреты

- Symptom families (`semantic_false_positive`, `semantic_false_negative`)
- Blind `CP3_post_emit` без coverage audit
- Additive scoring в P0/P1
- Screen/`figmaId`/path-specific patches
- Смешение `LAYOUT_LAWS` с blocking conservation

---

## 10. Corpus linkage

| Инкремент | `family_id` | `law_ids` |
|-----------|-------------|-----------|
| 02-P0-4 | `node_multiset_loss` | `LAW-CONSERVE-MULTISET` → `inv_node_multiset` |
| 02-P0-4 | `graph_sync_violation` | `LAW-CP2-GRAPH-SYNC` → `inv_graph_sync` |
| 02-P0-4 | `pass_over_mutation` | `LAW-PASS-CONTRACT` |
| 02-P0-4 | `extracted_widget_subtree_conservation_gap` | `LAW-WIDGETIR-CONSERVE` |
| 03-P0-1 | `semantic_upgrade_without_required_evidence` | `LAW-A3-CLASSIFY` |
| 03-P0-1 | `semantic_veto_not_applied` | `LAW-A3-CLASSIFY` |
| 03-P0-1 | `semantic_candidate_not_generated` | `LAW-A3-CLASSIFY` |
| 03-P0-1 | `classification_scope_violation` | `LAW-CP2-CLASSIFY-SCOPE` → `inv_classification_scope` |
| 03-P0-1 | `screen_root_scope_veto_missing` | `LAW-A3-ROOT-KIND` |

---

## 11. Порядок работ

### Commit 0 (docs-only)

```text
02-03-refactoring-spec-cursor.md + .gitignore docs/* exception
```

### Параллельный старт (два чата)

```text
Чат A: 02-P0-1 → 02-P0-2 → 02-P0-3 → 02-P0-4
Чат B: 03-P0-0 → 03-P0-1 → 03-P0-2 → 03-P0-3 → 03-P0-4
```

**Не смешивать** 02-P0 и 03-P0 в один PR без явной связи.

---

## 12. История документа

| Дата | Изменение |
|------|-----------|
| 2026-07-03 | Initial Milestone 2 plan |
| 2026-07-03 | Spec sync: mechanism families, 03-P0-0, pilot-5, M2 DoD, merge order, baseline ratchet, PolicyDecision scope |
