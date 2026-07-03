# ТЗ: Закалка геометрического ядра (post-implementation, исполняемое)

> **Superseded by [geometry-remainder-tz.md](geometry-remainder-tz.md)** for execution (2026-06-05). Retained for history.
> Состояние на 2026-06-05: аудит реализован на ~80%. Провал сместился из «не сделано» в три режима:
> **(1) баги второго порядка в свежем коде, (2) валидаторы-декорации, (3) утилиты не подключены к pipeline.**
> Это ТЗ — про закалку уже построенного, не про новый дизайн. Заменяет [geometry-refactor-tz.md](geometry-refactor-tz.md)
> для **исполнения** (тот писался под «не реализовано»). Диагноз-SSOT — [systemic-core-audit.md](../../systemic-core-audit.md).
> Сведено с двумя параллельными ревью (code-grounded + стратегическое) и реконсиляцией статусов.
> Номера строк — на 2026-06-05; сверять по именам функций.

## 0. Что уже починено (НЕ переделывать)

| Было | Статус | Где |
|------|--------|-----|
| MTX-01 rotation degrees→rad | ✅ done | `layout_widget.py:512` (`rotation_rad` + fallback) |
| FLX-01 Expanded-ось | ✅ done | `geometry_flex.py:35` (main Expanded vs cross stretch) |
| Matrix4 сырой линейный блок, без translate | ✅ done | `geometry_affine.matrix4_linear_expr:97-111` (pivot `Alignment.topLeft`) |
| Новые модули | ✅ существуют | `z_bands.py`, `z_dag.py`, `cascade_context.py`, `geometry_baseline.py`, `variant_topology.py`, `geometry_emit_invariants.py` |
| Новые инварианты | ✅ объявлены | `inv_unit`, `inv_flex_axis`, `inv_reproject`, `inv_ast_coverage` |

**Корректировки реконсиляции (не повторять ошибочные claim'ы):**
- `variant_topology._topology_signature` использует `frozenset`, но **кратность НЕ теряется** — index-токены
  `{depth}->{index}:type` её сохраняют. Реальная проблема — утилита **не подключена**, не «теряет кратность».
- `Alignment.topLeft` — **условно** верен: только при placement по local-origin `(tx,ty)`. С AABB-placement даёт дрейф (см. WP-A).

---

## WP-A — Один канал геометрии (P0, keystone)
*Поглощает находки #1, #2, #2b → SYS-CORE-003/004/007/017, RC-4, WP-1.3/1.4/2.2.*
**Проблема:** два независимых дефекта складываются в кашу на повёрнутых/flex-нодах:
- двойной flex-wrap: `_wrap_sizing` зовёт `apply_flex_wrap_to_widget` (`layout_widget.py:1249`) И
  `_apply_layout_slot_wraps` применяет `slot.wraps` (`:3177`);
- pivot `topLeft`, но placement из AABB (`extract_stack_placement`) и intrinsic из AABB
  (`geometry_frames.py:95`) → для повёрнутой ноды origin не совпадает.

- [ ] **A.1 — LayoutSlot единственный источник flex.** В `_wrap_sizing` (`layout_widget.py:1238-1249`):
  если `node.layout_slot is not None` → **не** вызывать `apply_flex_wrap_to_widget`; авторитет —
  `slot.wraps` через `_apply_layout_slot_wraps`. Legacy-обёртка только когда `layout_slot is None`.
- [ ] **A.2 — Placement = local-origin при нетривиальной линейной части.** В `geometry_planner`/
  `_stack_pins_from_placement` и `_ensure_positioned_stack_bounds`: если `residual_matrix` нетривиальна
  (есть поворот/scale/shear) → `Positioned(left=tx, top=ty)` из `local_transform`, `child=SizedBox(localW,localH)`;
  intrinsic = **local size**, не AABB. Если линейная часть = identity → AABB-путь оставить (общий случай, низкий риск).
- [ ] **A.3 — `hydrate_geometry_frame` (SYS-CORE-017):** `layout_rect`/intrinsic = local unrotated size;
  `world_aabb = expand_aabb(world, localRect)` как производная (не из `absoluteBoundingBox` напрямую для transformed).
- **Инвариант:** `inv_reproject` (эмит) — `‖expand(Positioned.origin ⊕ linear) − figma_aabb‖ ≤ ε`; `inv_emit_no_translate`.
- **Тест:** `test_rotated_node_local_origin_placement` — повёрнутый VECTOR: `Positioned` = (tx,ty), pivot topLeft,
  reproject ≈ figma_aabb; `test_no_double_flex_wrap` — нода с `layout_slot` не получает legacy+slot wrap одновременно.
- **Acceptance:** на `nested_affine_cascade.json` (depth≥3, rotate+scale+mirror) нет двойных обёрток и дрейфа origin.
- **Effort:** M. **Это узел всего — делать первым.**

## WP-B — Оживить валидаторы-декорации (P0)
*Поглощает #4, #5 → INV-Z, INV-AST-COVERAGE, WP-5.*
**Проблема:** гейты есть, но ничего не ловят.
- [ ] **B.1 — ghost проверяет ТЕКУЩИЙ порядок (#4).** `z_dag.ghost_occlusion_violations` (`:92`) сейчас делает
  `ordered = z_dag_sort(children)` и проверяет уже-исправленный порядок → всегда «ок». Сравнивать **текущий**
  `children` с required DAG; нарушение = текущий порядок ≠ топологически-допустимому (decor над interactive).
- [ ] **B.2 — протащить `sidecar_skipped` (#5).** `validate_ast_coverage(..., sidecar_skipped=…)`
  (`geometry_emit_invariants.py:188`) принимает флаг, но `planner.py:336` и `ir_validate.py:1330` его не
  передают (всегда False) → oversized-skip проходит молча. Прокинуть фактический статус из AST-reconcile.
- **Инвариант:** `inv_ast_coverage` реально падает при oversized-skip; `INV-Z` ловит текущий неверный порядок.
- **Тест:** `test_ghost_detects_current_unsorted_order`, `test_ast_coverage_fails_on_oversized_skip`.
- **Acceptance:** оба гейта дают нарушение на заведомо-битой фикстуре (анти-регрессия декоративности).
- **Effort:** S. **Дёшево, но критично — без этого WP-A/C недоказуемы.**

## WP-C — Закалка Z-DAG (P1)
*Поглощает #3 → Z-01.*
**Проблема:** `_topo_sort_with_edges` (`z_dag.py:57`) без cycle detection; `_is_presentational`
(`z_bands.py:24`) считает `render_boundary` presentational без исключения interactive → нода
presentational∧interactive даёт рёбра A→B и B→A → цикл/зависание.
- [ ] **C.1 — взаимоисключающие классы.** `_is_presentational`: `render_boundary ∧ interactive → INTERACTIVE`
  (интерактив побеждает); один класс на ноду.
- [ ] **C.2 — cycle detection** в `_topo_sort_with_edges`: при цикле — детерминированный фолбэк
  (стабильный порядок по figma-index) + warning, не зависание.
- **Инвариант:** граф ацикличен; `INV-Z` тотальный порядок согласован с overlap + классом.
- **Тест:** `test_z_dag_no_cycle_on_presentational_interactive_overlap`.
- **Effort:** S.

## WP-D — Подключить утилиты к pipeline (P1→P2, ПОСЛЕ WP-A)
*Поглощает #6, #7, #8 → SYS-CORE-001/010, TXT-01, WP-1.1/2.5/3.1.*
> Подключать только после WP-A — иначе цепляешь к рассинхрону координат.
- [ ] **D.1 cascade_context (#6):** интегрировать в Parse→Plan как единый источник `world/local/pivot`;
  устранить space-split (`cascade_context.py:19` считает world, но pivot/AABB из local).
- [ ] **D.2 baseline (#7):** передавать font family из `geometry_flex` (`:77` не шлёт) в
  `geometry_baseline`; пометить как `approximate` (фикс-коэффициенты), не `verifiable`, пока нет
  font-metric oracle.
- [ ] **D.3 variant_topology (#8):** подключить к `cluster_variants`/`widget_extractor`; при
  `jaccard < 0.85` — отдельная ветка/slot, не merged subtree. (frozenset+index — ок, не трогать.)
- **Тест:** `test_cascade_context_wired_single_space`, `test_variant_topology_splits_divergent_subtree`.
- **Effort:** D.1 M, D.2 S, D.3 M.

## WP-E — Стабилизировать контракт тестов (P0, до правок)
- [ ] Обновить `test_affine_calibration.py`: ожидания `Alignment.topLeft` (не center), новые коды
  инвариантов (`inv_emit_no_translate` вместо `t1_emit_no_translate`). 2 падения — устаревшие ожидания, не регрессия.
- **Acceptance:** `pytest tests/test_affine_calibration.py … test_z_bands.py` — 0 failed.

## WP-F — Планировщик в default-on (P2, финал арки, ПОСЛЕ A-E зелёных)
- [ ] После A-E: `validate_geometry_invariants(require_layout_slots=True)` зелёный на 4 фикстурах →
  staged flip `use_geometry_planner: false→true` (CI-фикстуры → default). Иначе fail-closed уронит генерацию.
- **Acceptance:** `demo-signoff` + geometry-tier без регрессии IoU при planner=on.

---

## Матрица инвариантов: декоративные → рабочие

| Инвариант | Сейчас | Должно (WP) |
|-----------|--------|-------------|
| `inv_reproject` | объявлен, проверяет план | проверять ЭМИТ: placement ⊕ linear ≈ figma_aabb (WP-A) |
| `inv_emit_no_translate` | частично | `Transform` без translate при заданном Positioned (WP-A) |
| `inv_ast_coverage` | **инертен** (sidecar_skipped=False) | прокинуть фактический skip (WP-B.2) |
| `INV-Z` (ghost) | **декоративен** (проверяет сорт.порядок) | сравнивать текущий vs required (WP-B.1) |
| `inv_unit`, `inv_flex_axis` | ✅ работают | — |

## Порядок и зависимости

```
WP-E (тесты зелёные)  ─► WP-A (один канал)  ─┬─► WP-D (подключить утилиты)
                         WP-B (оживить гейты)─┤
                         WP-C (z-dag)        ─┴─► WP-F (planner default-on)
```
Критический путь: **WP-E → WP-A → WP-B → WP-F.** WP-A без WP-B недоказуем (гейты врут);
WP-D без WP-A цепляется к рассинхрону; WP-F только после зелёных A-E.

## Протокол приёмки

1. `poetry run pytest -q -m "not live_figma"` + новые тесты каждого WP зелёные.
2. После правок `tools/dart_ast_sidecar/`: `.\tools\build_sidecars.ps1`.
3. Фикстуры (без screen-имён): `nested_affine_cascade.json`, `elastic_form_a11y.json`,
   `variant_topology.json`, `oversized_layout.json`.
4. Перед merge в `main`: `.\scripts\signoff.ps1`.

## Единый принцип

> **Один канал координат (slot владеет позицией=local-origin, Transform — линейной частью вокруг topLeft),
> один источник flex (slot.wraps), валидаторы проверяют ЭМИТ/ТЕКУЩЕЕ состояние (не план/отсортированное),
> утилиты подключены к Parse→Plan→Emit (не живут отдельно).** Только после этого — planner в дефолт.
> Аудит закрыт; работа = закалка + подключение уже построенного.
