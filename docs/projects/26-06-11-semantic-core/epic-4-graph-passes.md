# EPIC 4 — Middle-end graph passes

**Source:** [semantic-core.md](semantic-core.md) (EPIC 4, lines 170–184)  
**Prerequisite:** [EPIC 1 Pass Manager](semantic-core.md) (E1 DoD); EPIC 3 accepted (emit path stable under default gates)

---

## S1 — Goal (locked)

### Зачем (WHY)

Сейчас значимая доля корпуса уходит в **абсолютный `Stack` + `Positioned`**, хотя геометрия Figma уже описывает **одноосевые ряды/колонки** и **растяжимую высоту**. Это:

- раздувает сниффинг-Dart в `layout/widgets/` (E3.4 burn-down);
- мешает semantic/flex emit (E3/E5) выражать структуру декларативно;
- ломает адаптивность (фиксированные высоты, ложный/отсутствующий scroll).

**EPIC 4** — middle-end слой: **два универсальных графовых оптимизатора**, оформленных как **pass-ы E1**, которые *до эмита* переписывают clean-tree + IR там, где это **формально доказуемо безопасно**, с provenance и conservation-инвариантами.

Мета-рамка программы (не нарушать):

1. Сохранить факт Figma, **или**
2. Создать **именованное отклонение** с provenance, **или**
3. Перевести subtree в более безопасный fidelity-tier.

Pass, который не укладывается в одно из трёх — **баг**.

### Что (WHAT)

| ID | Deliverable | Суть |
| --- | --- | --- |
| **E4.1** | **Unstacking pass** | Кандидатные `STACK` → `ROW` / `COLUMN` / `WRAP` при формальных критериях (непересекающиеся AABB, монотонность, зазоры ≤ ε, painter's order сохранён) |
| **E4.2** | **Height unpinning pass** | Каскадные `FIXED` высоты → `minHeight` / `Flexible`; scroll-host при content extent > artboard (не магическая константа) |
| **E4.3** | **Регистрация в E1** | Оба pass-а в реестре Pass Manager: инварианты, флаги политики, provenance на каждое срабатывание |

### SMART (кратко)

| | |
| --- | --- |
| **S** | Ровно два pass-а: unstack + unpin height; только dual-graph (clean + IR) через E1 |
| **M** | Corpus без hard-нарушений; метрика overlapped `Positioned` на de-stacked одноосевых рядах = **0**; property-тесты + универсальные фикстуры (без node-id) |
| **A** | Опирается на существующий Pass Manager (E1); не требует flip `report_only` |
| **R** | Снижает Positioned-долг → ускоряет E3/E5 и lint burn-down |
| **T** | Старт после E1 DoD; приёмка EPIC 4 — до массового E5 rollout (ворота W3+) |

### In scope

- Формальные **критерии активации** pass-ов (из таблицы semantic-core) — единственный способ включить трансформацию
- Dual-graph синхронизация (как E1 layout passes)
- Provenance + conservation checkpoints после pass-ов
- Универсальные тесты: property-generated layouts + фикстуры **класса** («ряд однородных чипов»), не customer screen names

### Out of scope

- Новые semantic kinds / детекторы (E2, E5)
- Jinja emit / `fidelity_tier` (E3) — pass-ы готовят граф, не шаблоны
- Viewport-магия и приёмка по **одному** макету / figmaId
- Screen-specific условия и локальные патчи (anti-patching law)
- Полное обнуление Dart-сниффинга (E5/E3.4 burn-down — отдельный трек)
- Pixel oracle / CI golden promotion (E6) — **не блокер старта**, но **блокер финальной приёмки** EPIC 4 вместе с corpus hard-gates

### Definition of Done (EPIC 4)

Эпик считается закрытым, когда:

1. **E4.1** — unstack pass в реестре; property-тесты зелёные; фикстура класса «однородный ряд чипов» без node-id; для узлов, прошедших критерий unstack, **0** overlapped `Positioned` на корпусе
2. **E4.2** — unpin pass в реестре; фикстуры: длинный текст без overflow; экран выше artboard скроллится; ниже artboard — без лишнего scroll
3. **E4.3** — provenance фиксирует каждое срабатывание; conservation-валидаторы зелёные после pass-ов
4. **Corpus** — прогон корпуса (E6) без **новых** hard-нарушений относительно baseline
5. **Метрика** — «наложенные Positioned одноосевых рядов» на корпусе = **0** для subgraph, помеченных pass-ом как de-stacked

### Release posture

- Pass-ы **включены политикой** (флаги E1), default может оставаться conservative до corpus green
- Трансформация **не меняет** semantic `kind` и **не обходит** E3 gates (`report_only` + `fidelity_tier`)
- Любой pass, не прошедший формальный критерий активации, **no-op** (граф не трогаем)

### Open questions (закрыты в S2)

- **Путь модулей:** фактический реестр — `src/figma_flutter_agent/generator/ir/passes/` (не `generator/passes/`).
- **Scroll-host:** отдельный третий pass `scroll_host` в `WAVE_1_IR_PASSES`, композиция после `unpin`; не merge в один модуль.

---

## S2 — Codebase map

### Карта пайплайна (где живут pass-ы)

```text
parse → clean_tree + (optional) LLM screen_ir
  → materialize_screen_code_from_ir
       ├─ validate_screen_ir / apply_ir_guards
       ├─ apply_ir_layout_passes          ← WAVE_1: unstack → unpin → scroll_host
       ├─ apply_ir_classification_passes
       ├─ stamp_fidelity_tiers
       └─ emit (IR-primary / layout shell)
  → plan_generation_files
       └─ apply_layout_passes_to_context  ← те же pass-ы, inject_root_scroll_host=True
```

Два входа в layout pass-ы с **разным флагом scroll**:

| Точка входа | Файл | `inject_root_scroll_host` |
| --- | --- | --- |
| IR materialize (screen codegen) | `generator/ir/materialize.py` | **False** (default) |
| Planner / deterministic layout | `generator/ir/passes/planner.py` → `_run_passes_for_tree` | **True** |

Порог scroll: `settings.agent.responsive.macro_height_threshold_px` (default **900**) в planner;
в materialize — аргумент `macro_height_threshold_px` (default **900**), **не** высота artboard из clean-tree.

---

### E1 — инфраструктура (уже есть, EPIC 4 опирается)

| Модуль | Роль для E4 |
| --- | --- |
| `generator/ir/passes/protocol.py` | `Pass`, `PassContext`, `pass_from_callable`, `ProvenanceSink` |
| `generator/ir/passes/manager.py` | `PassManager.run`, CP2 после всех pass-ов, coarse provenance (`children_count`) |
| `generator/ir/passes/registry.py` | `WAVE_1_IR_PASSES` = `unstack` → `unpin` → `scroll_host` |
| `generator/ir/passes/sync.py` | `update_clean_subtree`, `update_ir_subtree`, `index_ir_nodes`, `ir_kind_for_node_type` |
| `generator/ir/passes/geometry.py` | AABB helpers, `compute_flex_spacing`, `root_vertical_extent`, ε = **0.5px** overlap |
| `generator/geometry/invariants/checkpoints.py` | `run_cp2_ir_passes`: multiset + paint order + graph_sync |
| `generator/geometry/invariants/conservation.py` | `check_node_multiset_preserved`, `check_stack_paint_order_preserved`, `check_graph_sync` |
| `debug/provenance.py` | `ProvenanceRecorder.record_mutation`, checkpoint notes |
| `config/models.py` | `ResponsiveConfig.macro_height_threshold_px` |

Отдельный трек (не E4, но соседний): `generator/ir/passes/semantic.py` + `SEMANTIC_PASSES` — classification после layout.

---

### E4.1 — Unstacking (`generator/ir/passes/unstack.py`)

**Что уже реализовано**

- Dual-graph: `STACK` → `ROW` или `WRAP` на clean-tree + IR `kind` + `layout_hints.flex_spacing`
- Критерии (частично): ≥2 детей, horizontal coords, non-overlap on X (ε 0.5px), vertical spread ≤ 1px, monotonic X
- Защита interaction chrome: `looks_like_back_nav_stack`, `skip_control`, `stack_interaction_kind`
- Очистка `stack_placement` у детей после de-stack
- WRAP при overflow ширины родителя

**Разрыв vs semantic-core / S1 DoD**

| Критерий spec | Статус в коде |
| --- | --- |
| STACK → **COLUMN** (вертикальные одноосевые) | **Нет** — только horizontal ROW/WRAP |
| Дисперсия зазоров ≤ ε (0.5px); иначе ROW/COLUMN с явными `SizedBox`-гэпами | **Нет** — средний gap (`compute_flex_spacing`), без variance gate и без SizedBox fallback |
| WRAP только при ≥2 рядах с равным зазором | **Нет** — WRAP по overflow ширины |
| Painter's order (E1.2-б / E0.3) | **Precondition есть** — `test_z_order_unstack_precondition.py`; pass не пересортировывает children |
| Property-тесты на сгенерированных раскладках | **Нет** |
| Метрика overlapped `Positioned` на de-stacked корпусе = 0 | **Нет** — нет emit-level oracle / lint метрики |
| Provenance на срабатывание (`type`, `spacing`, node_id) | **Частично** — manager пишет только `children_count` deltas |

**Downstream emit:** после unstack `NodeType.ROW` → `render_row` в `layout/widgets/emit/shell.py` (flex, не `Positioned`); до pass — `NodeType.STACK` → `render_stack`.

---

### E4.2 — Height unpinning (`generator/ir/passes/unpin.py`)

**Что уже реализовано**

- Clean-tree: `COLUMN` + `height_mode=FIXED` + дети только text/input subtree → `HUG` + `min_height` = бывший fixed height
- `layout_slot`: `backend=FLEX`, `height_fit=MIN`
- Не трогает root column

**Разрыв vs spec**

| Критерий spec | Статус в коде |
| --- | --- |
| IR sync (`minHeight` / `Flexible` hints на IR) | **Слабо** — `_unpin_ir_column` no-op по сути (`kind` не меняется, hints не проставляются) |
| `Flexible` для адаптивных узлов в COLUMN | **Нет** |
| Фикстура: длинный текст растягивает карточку без overflow | **Нет** dedicated test |
| Scroll-host (E4.2b) | **Отдельный pass** `scroll_host.py` (см. ниже) |

---

### E4.2b — Scroll host (`generator/ir/passes/scroll_host.py`)

**Что уже реализовано**

- Root `COLUMN` или `STACK` → `scroll_axis=vertical`, `height_mode=HUG`, IR `NAV_SCROLL_HOST`
- Порог: `root_vertical_extent(node) > macro_height_threshold_px`
- Gated: `inject_at_root=True` (planner); materialize path **не включает**

**Разрыв vs spec**

| Критерий spec | Статус в коде |
| --- | --- |
| content extent > **высоты artboard из clean-tree** | **Нет** — сравнение с config threshold 900, не с frame artboard |
| «не константа 800» | Формально ок (900 configurable), но **не привязано к artboard** |
| Экран ниже artboard — нет scroll | Тест `test_scroll_host_not_injected_for_896px_root` при threshold 900 |
| E3 `nav_scroll_host` template emit | Есть в `semantic_emit.py`; pass ставит `WidgetIrKind.NAV_SCROLL_HOST` |

---

### E4.3 — Регистрация / provenance / policy

| Требование | Статус |
| --- | --- |
| Оба pass-а в реестре E1 | **Да** (+ `scroll_host` как третий wave-1 pass) |
| Декларация `mutates` / `preserves` на pass | **Дефолт** `pass_from_callable` — без кастомных инвариантов per pass |
| Provenance каждое срабатывание | **Частично** — только coarse `children_count`; нет `(field, old, new)` на `type`/`sizing`/`kind` |
| Флаги политики per pass | **Нет** — только `inject_root_scroll_host` + `macro_height_threshold_px` на контексте |
| Conservation после pass-ов | **Да** — `run_cp2_ir_passes` в `PassManager` (multiset, paint order, graph_sync) |

---

### Тесты (существующие)

| Файл | Покрытие |
| --- | --- |
| `tests/test_ir_layout_passes.py` | unstack row/wrap, scroll threshold, idempotency, planner context |
| `tests/test_pass_manager.py` | registry order, idempotency, callable wiring |
| `tests/test_z_order_unstack_precondition.py` | E0.3 / E4 precondition paint order |
| `tests/support/conservation.py` | helpers для multiset / z-order |

**Отсутствует для E4 DoD:** `test_unpin_*`, property-based unstack, emit Positioned metric, corpus regression hook для layout passes, фикстуры класса в `tests/fixtures/layouts/` (не semantics/).

---

### Модули, которые затронет доведение EPIC 4 до DoD

*(карта затронутых файлов — без решений)*

| Зона | Файлы |
| --- | --- |
| Pass logic | `generator/ir/passes/unstack.py`, `unpin.py`, `scroll_host.py`, `geometry.py` |
| Registry / policy | `generator/ir/passes/registry.py`, `protocol.py`, `manager.py`, `config/models.py` |
| Pipeline wiring | `generator/ir/materialize.py`, `generator/ir/passes/planner.py` |
| IR schema / hints | `schemas/ir.py` (`WidgetIrLayoutHints`, `LayoutSlotIr`) |
| Conservation / provenance | `generator/geometry/invariants/*`, `debug/provenance.py` |
| Emit verification | `generator/layout/widgets/emit/shell.py`, `generator/ir/expression.py`, возможно `generator/layout/widgets/position.py` |
| E3 scroll template | `generator/ir/semantic_emit.py`, `generator/templates/widgets/nav_scroll_host.dart.j2` |
| Tests / fixtures | `tests/test_ir_layout_passes.py`, новые property + layout fixtures |
| Corpus (E6) | `parser/semantics/corpus.py`, `audit/corpus.py` — hard-gate на финальной приёмке |

---

### Зависимости и ворота

| Зависимость | Статус |
| --- | --- |
| E1 Pass Manager | **Реализован** — EPIC 4 = hardening критериев + тесты + provenance, не greenfield |
| E0.3 z-order | **Precondition тесты есть** |
| E3 emit | **Принят** — ROW/COLUMN/NAV_SCROLL_HOST emit paths существуют |
| E6 corpus | **Параллельно** — блокер **финальной** приёмки E4, не старта работ |

---

### Итог S2 (одной строкой)

**Скелет EPIC 4 уже в репо (wave-1 registry + три pass-а + CP2 + базовые тесты unstack/scroll), но формальные критерии semantic-core закрыты лишь частично: нет vertical unstack, gap variance, IR-unpin sync, artboard-aware scroll, field-level provenance, property-тестов и метрики Positioned.**

---

## S3 — Research (skipped)

Внешний ресёрч не проводился: S2 зафиксировал конкретные разрывы, паттерны уже в репо
(`geometry.py`, CP2, z-order precondition). Достаточно для выбора концепции.

---

## S4 — Solution concept (locked)

### Варианты

#### Вариант A — «Допилить как есть»

Расширить `unstack.py` / `unpin.py` / `scroll_host.py` и `PassManager` без новых слоёв;
критерии активации — приватные функции внутри каждого pass-а.

| | |
| --- | --- |
| **Плюсы** | Минимальный diff, быстрый старт, существующие тесты не ломаются |
| **Минусы** | Критерии размазаны по файлам; сложно property-тестировать; риск дубля horizontal/vertical логики; provenance останется куцым |

#### Вариант B — «Критерии отдельно, pass-ы тонкие» *(выбран)*

Вынести **чистые** функции классификации/активации в `generator/ir/passes/layout_criteria.py`
(или пакет `layout_criteria/` при росте >300 строк). Pass-ы только:

1. обходят dual-graph;
2. вызывают `evaluate_*` → `LayoutActivationDecision`;
3. при `activated=True` мутируют clean + IR синхронно;
4. пишут provenance через общий `record_layout_activation`.

| | |
| --- | --- |
| **Плюсы** | Формальные критерии semantic-core тестируются без PassManager; один алгоритм на ось; соответствует anti-patching; property-тесты бьют в criteria, не в emit |
| **Минусы** | Чуть больше файлов; рефактор существующего `unstack.py` |

#### Вариант C — «Сдвинуть unstack на emit / AST»

Определять ROW/COLUMN в `expression.py` или AST sidecar по координатам при генерации Dart.

| | |
| --- | --- |
| **Плюсы** | Не трогать clean-tree |
| **Минусы** | **Отвергнут:** нарушает контракт middle-end (граф должен быть правдой до emit); classification/conservation не видят структуру; дублирование геометрии в Dart-слое |

**Выбор: Вариант B** — hardening поверх E1, не новая архитектура.

---

### Архитектурная схема (Вариант B)

```text
CleanDesignTreeNode + ScreenIr
        │
        ▼
┌───────────────────────────────────────┐
│  PassManager (WAVE_1, порядок сохранён) │
│  unstack → unpin → scroll_host        │
└───────────────────────────────────────┘
        │ each pass
        ▼
 layout_criteria.evaluate_*  ──► LayoutActivationDecision
        │                              (axis, target_type, spacing,
        │                               gap_mode, evidence, reject_reason)
        ▼
 dual-graph mutate (sync.py)  +  ProvenanceSink.record per field
        │
        ▼
 run_cp2_ir_passes (unchanged hard gate)
        │
        ▼
 emit (ROW/COLUMN/NAV_SCROLL_HOST — уже E3)
```

---

### Заблокированные решения

#### D1 — E4.1 Unstack: ось и target type

- **Один алгоритм, две оси:** `evaluate_stack_flex_candidate(children)` пробует horizontal, затем vertical (симметричные AABB/monotonic/overlap на X или Y).
- **Активация** только если выполнены (а)(б)(г) из semantic-core; **(в) gap uniformity:**
  - `variance(gaps) ≤ ε` (0.5px) → `gap_mode=uniform`, spacing = median gap;
  - иначе → `gap_mode=explicit`, spacing = 0, gaps[] сохраняются в `layout_hints.explicit_gaps` (порядок = paint order, без reorder).
- **WRAP:** только если horizontal кандидат + **≥2 ряда** по Y-кластеризации с равномерным межрядным зазором (не overflow-width heuristic). Overflow-width WRAP **удаляется** как критерий активации.
- **Painter's order:** children **никогда** не пересортировываются; монотонность проверяется на копии sorted-by-axis только для валидации, не для мутации.
- **Protected stacks** (interaction chrome) — сохраняем существующие guards из `unstack.py`.

#### D2 — Explicit gaps на emit (не regex, не screen-specific)

- `gap_mode=explicit` → `render_row` / `render_column` (и IR-primary shell) вставляют `SizedBox` **между** соседними children по сохранённым gap values.
- Это изменение **универсального** row/column renderer, driven by `layout_hints`, не ветка по figmaId.

#### D3 — E4.2 Unpin: dual-graph parity

- Clean-tree: текущая логика `FIXED → HUG + min_height` **сохраняется**.
- IR: `_unpin_ir_column` **обязан** зеркалить `WidgetIrLayoutHints.min_height` + `height_fit=MIN` (и `layout_slot` при наличии).
- `Flexible`: для детей text/input внутри unpin-хоста — `layout_slot.height_fit=MIN` на child IR nodes (не менять semantic `kind`).
- Root column по-прежнему **не** unpin (как сейчас).

#### D4 — E4.2b Scroll-host: artboard-first

- **Порог:** `content_extent > artboard_height`, где `artboard_height` =
  `root.geometry_frame.world_aabb.height` **или** `root.sizing.height` при FIXED/HUG с известным height.
- `macro_height_threshold_px` — **fallback** только когда artboard height неизвестна (0 / missing), не primary gate.
- **Унификация pipeline:** оба входа (`materialize.py`, `planner.py`) читают одну политику из config `LayoutPassesSettings` (новая секция в `config/models.py`):
  - `inject_root_scroll_host: bool` (default `true` после artboard rule);
  - `scroll_extent_fallback_threshold_px` (бывший macro threshold, fallback only).
- `scroll_host` pass **остаётся отдельным** третьим в `WAVE_1_IR_PASSES` (после unpin).

#### D5 — E4.3 Provenance и policy

- Каждая активация pass-а пишет **структурированную** запись:
  `(checkpoint, transform, node_id, field, old, new, policy?)` для полей `type`, `kind`, `spacing`, `sizing.height_mode`, `scroll_axis`, `layout_hints.*`.
- `PassManager._record_pass_mutations` (children_count) **остаётся** как coarse safety net; field-level — в pass runners через `ProvenanceSink`.
- Per-pass `mutates` / `preserves` в `registry.py`:
  - `unstack`: mutates `type`, `spacing`, `stack_placement`, `kind`, `layout_hints`; preserves `node_multiset`, `stack_paint_order`
  - `unpin`: mutates `sizing`, `layout_slot`, `layout_hints`; preserves multiset, paint order, `kind` (semantic)
  - `scroll_host`: mutates root `scroll_axis`, `sizing`, `kind`; preserves multiset, child paint order

#### D6 — Метрика Positioned (приёмка E4.1)

- **Не** pixel-diff. **Emit audit** на универсальных фикстурах:
  - после pass + minimal emit для subtree → **0** вхождений `Positioned(` в теле контейнера, помеченного provenance `transform=unstack`.
- Реализация: `tests/support/layout_emit_audit.py` + тесты класса «chip row» / «vertical list» без customer node-id.
- Дополнительно: graph invariant `check_flex_children_have_no_stack_placement` для de-stacked subtrees (до emit, быстрый gate).

#### D7 — Тестовая стратегия (три слоя)

| Слой | Что | Где |
| --- | --- | --- |
| L1 | Unit: criteria, gap variance, axis monotonicity, wrap rows | `tests/test_layout_criteria.py`, Hypothesis optional |
| L2 | Integration: pass + CP2 + idempotency | расширить `test_ir_layout_passes.py`, `test_pass_manager.py` |
| L3 | Emit audit: no Positioned on de-stacked hosts | `tests/test_layout_pass_emit_audit.py` + fixtures `tests/fixtures/layouts/pass/` |

Corpus regression (E6) — **финальный** gate, не часть каждого PR wave.

---

### Волны реализации (для S5)

| Wave | Scope | Выход |
| --- | --- | --- |
| **W1** | `layout_criteria` + horizontal unstack hardening + field provenance + IR unpin sync | L1/L2 green, существующие unstack тесты обновлены под новые WRAP rules |
| **W2** | Vertical unstack + explicit gap mode + row/column emit gaps | L3 emit audit green на chip-row + vertical list fixtures |
| **W3** | Scroll artboard-first + `LayoutPassesSettings` + unify materialize/planner | scroll fixtures (above/below artboard) |
| **W4** | Property tests + corpus baseline + provenance dump smoke | E4 DoD checklist closed |

---

### Явно не делаем в EPIC 4

- Новые semantic kinds / детекторы
- Flip `report_only`
- Screen-specific emit branches
- Обязательный pixel oracle (E6 отдельно)
- Merge `scroll_host` в `unpin`
- Overflow-width WRAP heuristic (заменяется row-cluster WRAP)

---

### Риски и смягчение

| Риск | Смягчение |
| --- | --- |
| Explicit gaps ломают существующие row renders | Feature driven by `layout_hints.gap_mode`; default `uniform` = текущее поведение |
| Artboard height отсутствует на части корпуса | Fallback threshold + provenance `policy=artboard_unknown` |
| WRAP row-cluster сложнее overflow heuristic | L1 property tests на synthetic multi-row chips |
| materialize scroll flip ломает responsive shells | `inject_root_scroll_host` config default conservative → `true` только после W3 fixtures green |

---

### Итог S4 (одной строкой)

**Вариант B: формальные критерии в `layout_criteria`, тонкие pass-ы, artboard-first scroll с единой config-политикой, IR-sync для unpin, explicit SizedBox gaps через hints, emit-audit метрика Positioned — без сдвига логики в emit/AST и без screen patches.**

---

## S5 — Implementation checklist (done)

| Wave | Item | Status |
| --- | --- | --- |
| W1 | `layout_criteria.py` + `provenance_record.py` | done |
| W1 | Refactor `unstack.py` / `unpin.py` / `registry.py` | done |
| W1 | `tests/test_layout_criteria.py`, unpin/wrap fixture updates | done |
| W2 | Schema `gap_mode` / `explicit_gaps` / `min_height`; `flex_children_body` emit | done |
| W2 | `check_flex_hosts_have_no_stack_placement` | done |
| W2 | `tests/support/layout_emit_audit.py` + emit audit tests | done |
| W3 | `resolve_artboard_height` + artboard-first scroll | done |
| W3 | `LayoutPassesSettings` + planner/materialize unify | done |
| W3 | Scroll fixtures (above/below artboard) | done |
| W4 | Property-style criteria loops + provenance smoke | done |
| W4 | Conservation flex-host test | done |
| W4 | README + this checklist | done |

**Verification:** `poetry run pytest tests/test_layout_criteria.py tests/test_ir_layout_passes.py tests/test_layout_pass_emit_audit.py tests/test_layout_pass_provenance.py tests/test_layout_pass_conservation.py tests/test_pass_manager.py tests/test_z_order_unstack_precondition.py -q`
