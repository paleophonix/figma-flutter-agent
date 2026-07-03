# ТЗ по остатку: геометрическое ядро (после ~90% внедрения)

> Состояние 2026-06-05, **verified по живому коду** (не по снапшот-ревью). Почти весь аудит реализован
> и **уже починены в реальном времени**: MTX-01 (rotation_rad), FLX-01 (axis), double-wrap
> (`_wrap_sizing:1249`), z_dag cycle+current-order ghost, `sidecar_skipped` threading,
> cascade_context/variant_topology wiring, det-loss (affine2 на сырой матрице, `geometry_frames:59`),
> baseline font_family wiring.
> **Этот документ — финальный остаток (3 пункта).** Заменяет [geometry-hardening-tz.md](geometry-hardening-tz.md)
> (тот протух — ~90% его WP уже сделаны). Диагноз-SSOT — [systemic-core-audit.md](../../systemic-core-audit.md).

## Остаток = 3 пункта

| WP | Тип | Статус | Приоритет |
|----|-----|--------|-----------|
| WP-R1 | код-фикс | открыт (verified) | **P0** |
| WP-R2 | флаг + гейт | открыт (главное — оживляет всё внедрённое) | **P0** |
| WP-R3 | парк/опц. | accepted-approximate | P3 |

---

## WP-R1 — `intrinsic_size` = локальный размер, не AABB (закрыть хвост SYS-CORE-017)

**Verified:** `hydrate_geometry_frame` (`parser/geometry_frames.py:101-107`):
```
layout_w/h = absoluteBoundingBox.width/height      # AABB
intrinsic  = GeomRect(width=layout_w, height=layout_h)
transformed: layout_rect = GeomRect(x=local.tx, y=local.ty, width=layout_w, height=layout_h)
```
`raw.get("size")` не используется нигде (grep=0). Для **повёрнутой** ноды `absoluteBoundingBox` —
осевой (раздутый) бокс, а не локальный `w×h`. Origin уже local (tx,ty) ✓, но **размер = AABB** ✗ →
`expand_aabb(local, AABB_w, AABB_h)` «расширяет уже расширенное» → второго-порядка дрейф повёрнутых
нод. (Грубый дрейф снят прошлыми фиксами; это тонкий остаток.)

**Фикс (хирургический, только transformed-ветка):**
- [ ] В `hydrate_geometry_frame`: для `transformed = has_non_trivial_linear(linear) or not is_axis_aligned(local)`
  брать локальный размер из Figma `raw["size"]` (`{x,y}` — собственный бокс ноды до трансформации):
  `local_w, local_h = size.x, size.y`.
- [ ] **Fallback** (если `size` отсутствует): восстановить из AABB и линейной части —
  решить `[ |a| |c| ; |b| |d| ] · (w,h)ᵀ = (AABB_w, AABB_h)ᵀ` (2×2 для rotation+scale; при det≈0 → текущий AABB-fallback + warning).
- [ ] `intrinsic = GeomRect(width=local_w, height=local_h)`; `layout_rect` (transformed) =
  `(local.tx, local.ty, local_w, local_h)`; `world_aabb` оставить `parsed_aabb` (= Figma AABB).
- [ ] **Axis-aligned ветку НЕ трогать** (там `absoluteBoundingBox == local size`, риск нулевой).

**Инвариант (уже есть, должен теперь сходиться точно):** `inv_reproject` —
`‖expand_aabb(local, intrinsic) − parsed_aabb‖ ≤ ε` для transformed-нод.

**Тесты:**
- `test_intrinsic_is_local_size_for_rotated` — нода 45°, `size=(100,40)`, AABB≈(99,99): intrinsic=(100,40), reproject≈AABB.
- `test_intrinsic_unchanged_for_axis_aligned` — без поворота: поведение идентично (анти-регрессия).
- `test_intrinsic_fallback_when_size_absent` — нет `size`: восстановление из AABB+linear, не падение.

**Acceptance:** на `nested_affine_cascade.json` `inv_reproject` зелёный для всех повёрнутых нод; axis-aligned вывод бит-в-бит прежний.
**Effort:** S (несколько строк + fallback).

---

## WP-R2 — Поднять `use_geometry_planner` в default-on (оживить всё внедрённое)

**Verified:** `config.py:273` `use_geometry_planner: default=False`; ни один профиль не включает
(grep `=True` только в тестах). Значит весь починенный геометрический подслой (matrix4 raw-блок,
T1-T5 инварианты, cascade_context, z_dag, эластичность) **спит**; по умолчанию работает legacy-путь.
**Это — главный пункт остатка: без флипа вся проделанная работа в проде не исполняется.**

**Риск:** `normalize_clean_tree` при planner=on зовёт
`validate_geometry_invariants(require_layout_slots=True)` и **бросает `GenerationError`** на любом
нарушении (`normalize.py:77-82`, fail-closed). Наивный флип уронит генерацию на первом же дереве с невязкой.

**Процедура (staged, не флипать вслепую):**
- [ ] **R2.1 — гейт на фикстурах:** прогнать planner=on на всех `tests/fixtures/layouts/*.json`
  + новые `nested_affine_cascade.json`, `elastic_form_a11y.json`; `validate_geometry_invariants` = 0 нарушений.
  Чинить выявленные невязки (ожидаемо — добьёт WP-R1 + точечные).
- [ ] **R2.2 — CI-стадия:** включить planner=on в `demo-signoff`/fixture-прогоне (default остаётся off)
  → зелёный geometry-tier (IoU) без регрессий N сборок.
- [ ] **R2.3 — флип:** `config.py:273` `default=False → True`. Legacy-путь — deprecated-adapter (оставить
  как fallback до удаления).
- [ ] **R2.4 — обновить устаревшие тесты:** `test_affine_calibration.py` (2 падения — ждут `Alignment.center`/
  старые коды инвариантов; привести к `Alignment.topLeft` + новым кодам). Сделать **до** R2.2, иначе CI красный.

**Acceptance:** `use_geometry_planner: true` по умолчанию; `demo-signoff --signoff-gates` зелёный;
повёрнутые/flex/INPUT фикстуры рендерятся через planner без `GenerationError`.
**Effort:** M (в основном — догнать невязки инвариантов на реальных деревьях).
**Зависимость:** после WP-R1 (он закрывает значимую долю reproject-невязок).

---

## WP-R3 — Baseline oracle (park, accepted-approximate)

**Verified:** `geometry_baseline.flutter_baseline_offset` уже принимает `font_family`, имеет таблицу
ключей (`roboto/inter/sf pro`), warning на miss; `geometry_flex:83-84` font_family **передаёт**;
`baseline_verifiable=False` (`geometry_flex:96`). То есть это **не баг**, а сознательная аппроксимация
коэффициентом (нет реального font-metric измерения).

- [ ] **Парковать** как `approximate`. Текст не пиннится бит-в-бит без растеризации глифов (известный
  потолок; golden-петля вне скоупа) → ROI низкий.
- [ ] (Опц., будущее) расширить таблицу под используемые семейства (Golos Text и т.п.) либо подключить
  реальный font-metric источник; держать `baseline_verifiable=False`, пока нет измерения.

**Acceptance:** зафиксировано как known-approximate в `systemic-core-audit` (INV-BASELINE = partial, не gap).
**Effort:** S (документация) / L (если реальный oracle — не сейчас).

---

## Порядок

```
WP-R2.4 (тесты зелёные) → WP-R1 (intrinsic=local) → WP-R2.1/2.2 (гейт на фикстурах) → WP-R2.3 (флип)
WP-R3 — параллельно, парк.
```
**Критический путь: WP-R1 → WP-R2.** Всё остальное из прошлых ТЗ — уже сделано (см. шапку); не переоткрывать.

## Принцип

> Остаток мал: **один код-фикс (intrinsic=local) + один флип флага (с прогоном инвариантов на
> фикстурах).** После флипа весь внедрённый геометрический слой становится живым в проде; до флипа —
> спит. Анализ закрыт; это финальная сборка, не новый дизайн.

## Заметка о санитарии доков

`geometry-hardening-tz.md`, `geometry-refactor-tz.md`, `geometry-calibration*.md`, `translation-theory.md`,
`reviewer-backlog.md` и пр. — **исторические/диагностические**; для исполнения актуальны только этот файл
(остаток) + `systemic-core-audit.md` (SSOT диагноза). Рекомендуется пометить остальные `superseded` во избежание двойной работы.
