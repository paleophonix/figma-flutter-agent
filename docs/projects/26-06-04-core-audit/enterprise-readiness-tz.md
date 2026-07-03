# ТЗ: Enterprise-readiness (две мины перед подписанием контракта)

> **Ось:** НЕ геометрия-калибровка (та закрыта — см. `systemic-core-audit.md` + `planner-rollout-tz.md`).
> Здесь — **семантическая полнота и масштаб**: процедурная декомпозиция oversized-деревьев и слепота IR
> к Figma Variables / Conditional Action Logic. Плюс сквозная риск-матрица по формальному 4-векторному аудиту.
> Статус: **диагноз верифицирован по живому коду 2026-06-06**, исполнение не начато.
> Диагноз-SSOT — [systemic-core-audit.md](../../systemic-core-audit.md).

---

## 1. Матрица системных рисков (формальный аудит, 4 вектора)

| # | Вектор | Риск | Sev | Evidence (verified) | Покрытие |
|---|--------|------|-----|---------------------|----------|
| V2 | Вычислит. сложность / перф | Sweep-line / z-DAG / аффинный каскад — чистый Python, **никогда не профилировались** на enterprise-деревьях глубины >10. Для заявки «10k экранов» это **главный неизмеренный риск**. | **HIGH** | бенчмарка нет ни в `tests/`, ни в CI; `overlap_sweep.py`, `z_dag.py` без big-O гарантий | Не покрыто — нужен perf-gate |
| V3 | Sidecar / Size-Gate | 80KB → AST codegen **silent skip**; `dart format` **скип** на больших файлах; распиловщик `split_oversized_layout_dart` **wired-but-broken** (см. MINE-1) | **HIGH** | `validation.py:540-556`, `planned_dart.py:2310-2325,565-601`, ROB-06/SYS-CORE-016 | **MINE-1** снимает |
| — | Семантическая полнота | Variables + Conditional Action Logic = «мёртвая графика» в IR | **HIGH (страт.)** | `schemas.py` 0 полей под bindings/events; `prototype.py` nav-only | **MINE-2** (Phase 0) снимает |
| V1 | Границы пайплайна | In-place мутация дерева (`mark_degraded_nodes`, `reconcile_stack_placements_in_tree`), не все схемы `frozen`; иммутабельность `PipelineContext` не форсится | MEDIUM | известно по памяти core-audit; `Parse→Plan→Emit` в целом разделены, Dart-эмит читает IR, не raw Figma | Частично — hardening §4 |
| V4 | Тесты / воспроизв. | Нет perf-фикстуры (V2), нет Variables/conditional-фикстуры (MINE-2); fig-leaf-тест распиловщика; golden не изолирован от системных шрифтов | MEDIUM | `test_oversized_layout_chunked.py` (счётчик, не компиляция); corpus-gate = только геометрия | §4 + MINE-1/2 тесты |

**Вывод аудита:** ядро (геометрия + robustness) — бетон. Реальные открытые фронтиры ровно два — **MINE-1** (масштаб
файла) и **MINE-2** (семантика логики), плюс один **неизмеренный** перф-риск (V2). Остальное — MEDIUM-долг.

---

## 2. MINE-1 — Процедурная декомпозиция (Widget Chunking)

### 2.1. Verified state (что есть сейчас — и почему это не решение)

Три механизма, ни один не делает настоящую IR-декомпозицию:

1. **Делегат экрана** — `force_oversized_feature_screens_to_layout` (`planned_dart.py:517`): `*_screen.dart` > 80KB
   → `GeneratedScreenShell(child: const XLayout())`. Снимает размер **со screen**, но `*_layout.dart`
   (реальное дерево) **не трогает**.
2. **Скип форматирования** — `_filter_dart_format_targets_by_size` / `_skip_dart_format_on_large_layout`
   (`validation.py:540-556`): большие layout-файлы **пропускают `dart format`** (только delimiter-валидация).
   Плюс AST codegen **silent skip** на 80KB (ROB-06). → **самые сложные экраны получают меньше всего обработки.**
3. **Распиловщик — wired, но сломан** — `_apply_oversized_layout_splits` (`planned_dart.py:2310`, вызывается
   в `reconcile_planned_dart_files:2365`) → `split_oversized_layout_dart` (`:565`):
   - работает на **тексте уже сэмиченного Dart** через `extract_widget_by_figma_id` (не на IR);
   - shell = `class _LayoutShell { const _LayoutShell(); }` — **заглушка без `build`, без композиции**;
   - bodies = `// figma chunk {id}\n{snippet}` — **разрозненные, никто их не собирает обратно**;
   - **удаляет оригинальный класс** (`updated.pop(path)`) → ссылающийся `GeneratedScreenShell(child: const XLayout())`
     указывает на несуществующий класс → **не компилируется, если ветка сработает**;
   - плоская итерация по найденным figma id → вложенные id перекрываются (родитель содержит детей) → дубли.
   - **Тест `test_oversized_layout_chunked.py` — фиговый листок:** проверяет `len(chunks) > 1` + наличие путей +
     размер; **не компилирует результат, не проверяет выживание класса и связность.**

**Диагноз:** настоящего Widget Chunking нет. Есть костыль (делегат + скип) и сломанный текстовый распил.

### 2.2. Целевой алгоритм (универсальный, IR-уровень)

Декомпозиция должна происходить **на IR/planner до эмита**, как cost-based рекурсивный разрез дерева —
без привязки к именам экранов/id/контенту (anti-patching).

1. **Cost-модель (bottom-up):** для каждого узла `cost(n) = own_emit_cost(n) + Σ cost(child)`; прокси —
   `node_count` × калиброванный `BYTES_PER_NODE`, либо двухпроходный реальный замер. Детерминирован.
2. **Бюджет чанка:** `CHUNK_TARGET_BYTES` ≈ 32-40KB — с запасом под 80KB-гейт, чтобы AST sidecar **и**
   `dart format` всегда применялись к каждому чанку.
3. **Выбор разреза (greedy, универсальный):** post-order DFS; накопитель cost текущего чанка; когда поддерево
   перельёт родительский чанк за бюджет **и** само ≥ `MIN_CHUNK` (не резать тривиальное) — **вырезать** на
   **наибольшем** узле, чьё поддерево ∈ [MIN_CHUNK, budget]. Точки разреза — только «естественные швы»: прямые
   дети layout-контейнеров (Column/Row/Stack/list-элементы), никогда не середина декорации/одного виджета.
4. **Эмит чанка:** вырезанное поддерево → `class _Chunk_<stableId> extends StatelessWidget` в **отдельном файле**
   `lib/generated/chunks/<screen>_chunk_<n>.dart`; родитель эмитит `const _Chunk_<stableId>()` на месте.
   `stableId` = хэш node id → детерминированно, **идемпотентно**.
5. **Проброс контекста:** чанки stateless, тему берут через `Theme.of(context)` (уже правило проекта); локальных
   замыканий статический путь не создаёт. Если чанк ссылается на параметр — пробросить через `const`-конструктор.
6. **Инвариант `INV-AST-COVERAGE` (ужесточить):** после chunking **каждый** сгенерённый `.dart` < `CHUNK_TARGET_BYTES`
   < 80KB → ветка size-skip (AST + `dart format`) становится **недостижимой** в норме. `force_oversized_*` +
   `_filter_dart_format_targets_by_size` понижаются из «основного механизма» в «не должно срабатывать» страховку.

### 2.3. Работы

- [ ] **WP-M1.1 (P0):** `generator/chunking.py` — `chunk_tree(root, budget) -> (root', chunks: list[ChunkUnit])`.
      Чистая функция над IR (`CleanDesignTreeNode`), cost-модель + greedy-разрез. Без эмита.
- [ ] **WP-M1.2 (P0):** интеграция в planner/emit: вырезанные поддеревья эмитятся как отдельные `*_chunk_*.dart`,
      родитель ссылается `const _Chunk_*()`. Удалить/обойти текстовый `split_oversized_layout_dart`.
- [ ] **WP-M1.3 (P1):** понизить `_apply_oversized_layout_splits` до dead-safe (или удалить) — IR-chunking делает
      его ненужным. `force_oversized_*` оставить только как screen-vs-layout дедуп (не как size-fix).
- [ ] **WP-M1.4 (тест, заменить фиговый листок):** `test_chunking_output_compiles` — синтетическое дерево
      > 80KB → chunk → **каждый чанк < budget** + **сборка проекта `flutter analyze` зелёная** (класс выжил,
      ссылки связны). `test_chunking_idempotent` (повторный прогон = тот же результат).

**Acceptance:** любой экран любого размера → набор файлов, **каждый** < budget, проект компилируется, AST sidecar
и `dart format` отрабатывают на всех. Size-skip-ветки не срабатывают на нормальном входе.

**Effort:** M (cost-модель + разрез — компактный универсальный алгоритм; основной риск — проброс контекста, но в
статическом пути его почти нет).

---

## 3. MINE-2 — Figma Variables + Conditional Action Logic → reactive

### 3.1. Verified state (слепота IR)

- **IR — чистое render-дерево:** `schemas.py` — **0 полей** под `reaction/binding/variable/event/interaction`.
- **`parser/prototype.py` — только навигация:** `NavigationKind = navigate|overlay|swap|scroll`,
  `_SUPPORTED_NAVIGATION = {NAVIGATE, NAVIGATE_TO, OVERLAY, SWAP, SCROLL_TO}`. Edges живут в **side-channel**
  `PrototypeNavigationPlan` (routes+links), **не прикреплены к узлам IR**.
- **`parser/components.py`** — статический `componentProperties` (варианты). Это структура, не рантайм.
- **Variables + Conditional Action Logic — 0 парсинга:** grep `boundVariables|setVariable|CONDITIONAL|variableModes`
  по всему `src/` → только `llm/prompts.py` (текст промпта, не парсер).

**Диагноз:** кликабельная кнопка со `SET_VARIABLE` / условным переходом транслируется как мёртвый прямоугольник.
Для enterprise-макетов (наборы Variables + modes + conditional-логика) это потеря половины смысла.

### 3.2. Модель данных Figma (что надо захватить)

- `boundVariables` на узле → привязка свойства (fill/text/visible/...) к алиасу `{type:"VARIABLE_ALIAS", id:"VariableID:.."}`.
- Variable collections + **modes** (light/dark, locale) → переменная резолвится в разное значение по режиму.
- Reactions с actions: `SET_VARIABLE`, `SET_VARIABLE_MODE`, `CONDITIONAL` (if/else с `conditions`-выражениями) —
  плюс навигационные (уже есть).

### 3.3. Фазовый план (честный scope)

**Phase 0 — Non-lossy IR-capture (PRE-contract, дёшево, корректно):**

- [ ] **WP-M2.1:** `parser/variables.py` — `VariableRegistry` (id → {name, type, valuesByMode}) + `Binding(node_id, property, variable_id)`.
- [ ] **WP-M2.2:** `parser/actions.py` (или расширить `prototype.py`) — `SET_VARIABLE`/`SET_VARIABLE_MODE`/`CONDITIONAL`
      → `StateAction` / `ConditionalEdge`.
- [ ] **WP-M2.3:** side-channel `InteractionGraph` (по образцу `PrototypeNavigationPlan`, **прикреплён к экрану,
      не к каждому узлу** — render-IR остаётся чистым). Captured, validated, **не эмитится**.
- [ ] **WP-M2.4 — Coverage-телеметрия (трастовый win):** отчёт «N узлов имеют boundVariables, M reactions —
      SET_VARIABLE/CONDITIONAL, которые мы пока не транслируем». Явный сигнал «вот логика, которую мы видим, но
      ещё не переносим» вместо тихого уплощения.

**Acceptance Phase 0:** Variables/conditional **захвачены и провалидированы** (не теряются), детектор отмечает
непокрытую логику в build-отчёте. Codegen не меняется. Фикстура `variables_conditional.json` → registry непустой,
coverage-репорт корректен.

**Phase 1+ — Reactive lowering (POST-contract эпик, НЕ pre-contract):**

- `VariableRegistry` → state-контейнер (Cubit/StateNotifier) на экран/коллекцию; modes → theme/locale-провайдер.
- `Binding` → обернуть связанный виджет в `BlocBuilder`/`Consumer`/`context.watch`.
- `StateAction` на триггере → диспатч события в `onTap`.
- `ConditionalEdge` → `if` в build / `buildWhen`.

### 3.4. Честный вердикт по scope (для продакта)

> MINE-2 в формулировке «трансляция в BLoC/Riverpod» — **это не hardening перед контрактом, это отдельный
> продукт на недели** (выбор BLoC vs Riverpod, нейминг, тест-харнесс state-машин). Это смена класса продукта:
> «Figma → статичный экран» → «Figma → работающее приложение с логикой».
>
> **Pre-contract правильно делать только Phase 0 (capture + detection):** дёшево, корректно, останавливает
> потерю информации **сейчас** (когда придёт v2 — не перепарсивать), и даёт трастовую фичу «мы показываем, что
> не умеем» вместо тихого уплощения стейт-машины. Phase 1 — в roadmap v2, не в этот контракт.

---

## 4. Hardening-спецификация (форсировать инварианты/ассерты)

- [ ] **INV-AST-COVERAGE (ужесточить):** после эмита **каждый** `.dart` ≤ `CHUNK_TARGET_BYTES`. Нарушение →
      HARD (в `--strict`) — size-skip перестаёт быть «легальным обходом».
- [ ] **INV-CHUNK-CLOSURE:** после chunking все ссылки `_Chunk_*` резолвятся (нет битых ссылок на удалённые классы).
- [ ] **INV-INTERACTION-CAPTURED:** если у узла есть `boundVariables`/non-nav reaction — он попал в `InteractionGraph`
      (не потерян молча). Детектор покрытия = ассерт, не лог.
- [ ] **V1:** заморозить мутируемые схемы (`frozen=True`) либо явный copy-on-write в `mark_degraded_nodes` /
      `reconcile_stack_placements_in_tree`; запретить in-place мутацию IR после `plan`.
- [ ] **V2:** perf-ассерт — бенчмарк-гейт (см. §5) с порогом времени/памяти, регресс → CI warning.

---

## 5. Технический долг (debt)

- **Fig-leaf тест распиловщика** (`test_oversized_layout_chunked.py`) — проверяет существование механизма, не
  корректность. Заменить на компиляционный (WP-M1.4).
- **Дублирование size-логики:** `_LARGE_PLANNED_DART_BYTES`, `_PROACTIVE_LAYOUT_DELEGATE_SCREEN_BYTES`,
  `_filter_dart_format_targets_by_size`, `split_oversized_layout_dart` — четыре места про «файл слишком большой»,
  ни одно не решает корень. После MINE-1 свести в один cost-budget.
- **V2 — нет перф-фикстуры:** добавить `deep_wide_10k_nodes.json` (глубина ≥10, ширина ≥сотни листьев);
  бенчмарк `pytest-benchmark` на sweep-line/z-DAG/affine → зафиксировать big-O эмпирически.
- **Regex-репэйры на пробое size-gate** (`dart_syntax_repairs.py`) — формально нарушают «no-regex-on-Dart»
  правило проекта; после IR-chunking (когда файлы малы и AST всегда отрабатывает) должны стать недостижимы.

---

## 6. Приоритет и вердикт

```
MINE-1 (Widget Chunking, IR-уровень) ─► снимает V3 + половину V4-долга. Tractable, must-fix. Effort M.
MINE-2 Phase 0 (capture+detection)   ─► снимает страт. слепоту non-lossy. Дёшево, корректно. Effort S-M.
V2 perf-gate                         ─► единственный неизмеренный риск под заявку «10k». Effort S (бенчмарк).
─────────────────────────────────────
MINE-2 Phase 1 (BLoC/Riverpod codegen) ─► v2-эпик, НЕ pre-contract.
```

**Честно для контракта:** ядро готово. До подписи закрыть **MINE-1 + MINE-2 Phase 0 + V2 perf-gate** — это
реальная enterprise-готовность без раздувания scope. **MINE-2 Phase 1 вынести в roadmap v2** и не обещать в
этом контракте.
