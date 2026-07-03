# ТЗ: Program 01 — IR contract refactor (Cursor workflow)

**Программа:** [01_compiler-semantics-ir-contract.md](01_compiler-semantics-ir-contract.md)  
**Контракт-матрица:** [contracts/PIPELINE_ARROWS.md](contracts/PIPELINE_ARROWS.md)  
**Статус:** ready for execution  
**Аудитория:** агент / инженер в Cursor, владелец продукта (обзор инкрементов)

---

## 1. Цель

Закрыть **information loss** на стрелках `parse → clean tree → screen IR → merge/normalize → emit` через:

1. явную матрицу полей по стрелкам (уже в `PIPELINE_ARROWS.md`);
2. enforcement в коде (laws + pytest), а не compensator-слой без provenance;
3. связку с практическим потоком `/diagnose` → `/repair` и corpus (program 00).

**Не цель:** переписать emitter под один экран, formal proof всего IR, обязательный golden refresh.

---

## 2. Scope

### In scope

| Стрелка | ID | Код |
|---------|-----|-----|
| clean tree + IR → merged clean tree | **A1** | `generator/ir/tree.py` |
| IR reconcile (compensator) | **A1b** | `generator/ir/validate/graph.py` |
| clean tree → normalized clean tree | **A2** | `generator/normalize.py` |
| merged tree + IR → Dart (read contract) | **A3** | `generator/ir/expression.py` |
| IR passes (dual-graph) | **CP2** | `generator/ir/passes/` |

### Out of scope (отдельные программы RAR)

- Полная матрица **A4** (parse field-level) → program 02
- Classification theory → program 03
- Visual oracle / golden policy → program 09
- Control panel / infra → `/debug` → `/fix`, не этот ТЗ

---

## 3. Что уже сделано (baseline)

Перед первым инкрементом в Cursor — не дублировать:

| Артефакт | Путь | Статус |
|----------|------|--------|
| Матрица стрелок A1–A3 | `refactor/contracts/PIPELINE_ARROWS.md` | draft v1 |
| LAW-PASS-CONTRACT gate | `tests/test_ir_pass_contract.py` | **merged** |
| A1 merge preservation tests | `tests/test_ir_merge_preserve.py` | **merged** |
| Conservation codes | `tests/test_conservation_invariants.py` | **merged** |
| Pass `mutates` / `preserves` | `generator/ir/passes/registry.py` | wave-1 + semantic |
| Provenance API | `debug/provenance.py::DeviationRecord` | есть, не везде wired |

---

## 4. Воркфлоу в Cursor

### 4.1 Два потока — не смешивать

```text
Compiler / screen          Control plane
/diagnose → /repair        /debug → /fix
.debug/screen/...          Discord, worker, imports
```

Program 01 — **только compiler flow**.

### 4.2 Старт сессии (обязательный контекст)

В чате Cursor прикрепить:

```text
@refactor/AGENT_SYSTEM_PROMPT.md
@refactor/PROJECT_MAP.md
@refactor/contracts/PIPELINE_ARROWS.md
@refactor/01_refactoring-spec-cursor.md
```

Для конкретного бага добавить:

```text
.debug/screen/<project>/<feature>/last.log
.debug/screen/<project>/<feature>/llm_parsed.json
.debug/screen/<project>/<feature>/llm_validated.json
.debug/screen/<project>/<feature>/pre_emit.json
.debug/screen/<project>/<feature>/processed.json
.debug/screen/<project>/<feature>/provenance.json
```

**Triage order:** `last.log` → `dart-errors.json` → `processed.json` → `llm_*` → `pre_emit.json` → `provenance.json`.

### 4.3 Как вести задачу по инкременту

| Шаг | Действие | Skill / команда |
|-----|----------|-----------------|
| 1 | Воспроизвести family на fixture или `.debug` | `/diagnose` или ручной `generate` |
| 2 | Классифицировать **стрелку** (A1/A1b/A2/A3), не «emitter» по умолчанию | см. §6 |
| 3 | Проверить строку в `PIPELINE_ARROWS.md` — gap или illegal cell | read matrix |
| 4 | Минимальный diff в **owning layer** | `/repair` |
| 5 | Тест + строка в matrix + corpus tag (program 00) | pytest |
| 6 | Локальный gate | `ruff`, `mypy`, targeted pytest |
| 7 | Полный gate (по запросу / перед merge) | `.\scripts\signoff.ps1` |

### 4.4 Промпт-шаблон для агента (копипаст)

```text
Инкремент: Program 01 / <P0|P1|P2> / <LAW-id>
Стрелка: A1 | A1b | A2 | A3
Family: <из diagnose или corpus>
Сделай: <одна law из PIPELINE_ARROWS §5>
Ограничения: anti-patching, минимальный diff, тест обязателен
Не трогай: golden PNG, screen-specific ветки, промпты LLM (если не в scope)
Verify: poetry run pytest tests/test_ir_pass_contract.py tests/test_ir_merge_preserve.py -q
```

### 4.5 Правила репозитория (жёстко)

- `.cursor/rules/project-bible-lite.mdc` — Master Invariant
- Новый IR pass **без** `mutates`/`preserves` → CI fail (`test_ir_pass_contract.py`)
- Новая строка в `PIPELINE_ARROWS.md` **до** merge pass-изменения
- `load_settings()` не тащить внутрь `parser/` / `generator/`

---

## 5. Инкременты

### P0 — закрыть gaps без смены визуала emit

**Цель:** named deviation там, где сейчас silent mutate; CI guard уже на passes.

| ID | Задача | Файлы | Тест | DoD |
|----|--------|-------|------|-----|
| **P0-1** | `LAW-A1-OVERRIDE-PROV`: `_apply_ir_overrides` пишет `DeviationRecord` при смене fact | `generator/ir/tree.py`, `debug/provenance.py` | `tests/test_ir_merge_override_provenance.py` (новый) | override color/text → запись в provenance; без override — no record |
| **P0-2** | Документировать A1b reconcile drops в matrix §3 | `PIPELINE_ARROWS.md` | — | строка illegal/lossy согласована с кодом |
| **P0-3** | Lens: CLI или pytest helper diff `processed` vs `llm_validated` child sets | `fixtures/` или `debug/` (тонкий модуль) | 1 test на synthetic tree | выводит `inv_graph_sync`-подобный diff по node id |

**Verify P0:**

```powershell
poetry run pytest tests/test_ir_pass_contract.py tests/test_ir_merge_preserve.py tests/test_conservation_invariants.py -q
poetry run ruff check src/figma_flutter_agent/generator/ir/tree.py
```

---

### P1 — merge law enforcement

| ID | Задача | Файлы | Тест | DoD |
|----|--------|-------|------|-----|
| **P1-1** | `LAW-A1-DROP-VISIBLE`: drop без preserve predicate → deviation или `GenerationError` | `merge_ir_node` | extend `test_ir_merge_preserve.py` + negative case | decorative CONTAINER drop не silent |
| **P1-2** | Normalize sub-transform registry (A2): таблица в `PIPELINE_ARROWS.md` §A2.1 | `normalize.py`, matrix | — | каждый sub-step: mutates/preserves |
| **P1-3** | Corpus: ≥2 `.debug` counterexample на A1 illegal в `corpus/` (program 00) | `corpus/families.yaml` | — | family `ir_override_leak` с screen slugs |

**Verify P1:**

```powershell
poetry run pytest tests/test_ir_merge_preserve.py tests/test_ir_sanitize.py -q
```

---

### P2 — contract completeness

| ID | Задача | Файлы | Тест | DoD |
|----|--------|-------|------|-----|
| **P2-1** | `validate_pass_mutates` для `screen_ir.*` tokens | `passes/contract.py` | `test_ir_pass_contract.py` | semantic pass не может менять undeclared IR field |
| **P2-2** | `reads` на `Pass` protocol (optional third dimension) | `passes/protocol.py`, registry | contract test | wave-1 passes declare reads |
| **P2-3** | `LAW-A1b-DROP-PROV`: reconcile drop → `DeviationRecord`, не только `logger.warning` | `validate/graph.py` | `test_ir_layout_passes.py` или новый | provenance.json содержит transform |
| **P2-4** | Свести heal root kind к policy: heal **с** provenance vs reject | `validate/root_kind.py` | `test_screen_root_nav_kind_laws.py` | поведение задокументировано в matrix |

---

## 6. Routing: симптом → стрелка → слой

Использовать в `/diagnose` перед `/repair`:

| Симптом в `.debug` | Стрелка | Первый файл |
|--------------------|---------|-------------|
| `llm_parsed` missing children, `llm_validated` has stubs | A1b | `validate/graph.py` |
| Wrong text/color при верной Figma geometry | A1 | `tree.py::_apply_ir_overrides` |
| Missing decorative layer, multiset ok in clean | A1 lossy | `merge_ir_node` preserve predicates |
| `inv_graph_sync` / CP2 fail | A1b → CP2 | `sync_screen_ir_graph_to_clean_tree` |
| `layout_slot` missing / geometry violation | A2 | `normalize.py`, `geometry/planner.py` |
| Wrong widget class, bounds ok | A3 + classify | `expression.py`, `semantic_emit.py` |
| Wrong bounds in `processed.json` | A4 (out of scope P01) | `parser/tree.py` → program 02 |

**Правило:** если факт верный в `processed.json` и сломан в `screen.dart` — не чинить parser; найти первую стрелку, где поле исчезло (diff JSON).

---

## 7. Критерии готовности Program 01 (из RAR §3)

- [ ] Стрелки **A1, A1b, A2, A3** описаны в `PIPELINE_ARROWS.md` с ≥1 counterexample каждая (тест или corpus)
- [ ] ≥3 regression tests формата «поле X не исчезает / deviation записан после arrow Y»  
  *(частично: `test_ir_pass_contract`, `test_ir_merge_preserve`, `test_conservation_invariants`)*
- [ ] `LAW-A1-OVERRIDE-PROV` реализован (P0-1)
- [ ] Новый IR pass без matrix row → reject (CI: `test_ir_pass_contract.py`)
- [ ] Program 00: family `ir_override_leak` / `ir_merge_drop` в corpus (P1-3)

---

## 8. Gates

| Уровень | Команда | Когда |
|---------|---------|-------|
| Быстрый | `poetry run pytest tests/test_ir_pass_contract.py tests/test_ir_merge_preserve.py tests/test_conservation_invariants.py -q` | каждый инкремент |
| Средний | `poetry run pytest -q -m "not live_figma"` (если трогали соседние модули) | перед PR |
| Полный | `.\scripts\signoff.ps1` | merge в `main` |

Не обновлять golden PNG для «закрытия» contract gap.

---

## 9. Запреты (compiler oath)

- Ветки по `figmaId`, screen name, customer path
- Silent heal без `DeviationRecord` (после P0 — особенно overrides)
- Новый compensator вместо строки в `PIPELINE_ARROWS.md`
- Ослабление `test_ir_pass_contract.py` под один fixture
- LLM prompt magic вместо validate/merge law

---

## 10. Связь с Program 00 (corpus)

Каждый `/repair`, закрывающий gap из §5, добавляет case в corpus. **Согласование с GPT ТЗ:** [00-01-cursor-alignment.md](00-01-cursor-alignment.md).

| Program 01 | Program 00 |
|------------|------------|
| P0-1 `LAW-A1-OVERRIDE-PROV` | family `ir_override_without_provenance` (seed после P0-1) |
| P1-1 merge drop | `node_multiset_loss` / `ir_merge_silent_drop` |
| A1b graph sync | `graph_sync_violation` + `pipeline_arrow: A1b` |

**Порядок:** P0-1 можно делать **до** `defects` CLI (Batch 4). Case YAML — после **Batch 1** (models + `families.yaml`).

```yaml
# corpus/cases/<id>.yaml — после Batch 1
occurrences:
  - family_id: ir_override_without_provenance
    pipeline_arrow: A1
    law_ids: [inv_style_truth]
    stage: ir_validation
    origin: COMPILER
```

Без family tag repair считается незавершённым (см. `00_defect-taxonomy-corpus.md` + GPT repair DoD).

---

## 11. Порядок работы для Коли в Cursor

1. **Сейчас:** P0-1 (`LAW-A1-OVERRIDE-PROV`) — один PR, видимый прогресс, emit не меняется.
2. **Потом:** P1-1 (merge drop law) — закрывает реальные «пропавшие» слои.
3. **Параллельно продукту:** P1-3 corpus — не блокирует код, но нужен для приоритизации 02–10.

Чат-запуск:

```text
@refactor/01_refactoring-spec-cursor.md — делай P0-1
```

---

## 12. История документа

| Дата | Изменение |
|------|-----------|
| 2026-07-03 | Первая версия: исследование + анализ program 01, приземление в Cursor workflow |
