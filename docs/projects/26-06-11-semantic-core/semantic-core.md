Да, бро. Собрал **цельный markdown-документ целиком**, чтобы можно было просто заменить текущий файл без ручной сборки из кусочков. Основа — твой план E0–E7, плюс мои правки интегрированы начиная с E2.5 и дальше. 

````markdown
# ТЗ: Семантическое ядро IR — программа рефакторинга (эпики E0–E7)

> Версия: 1.1, 2026-06-11. Объединяет ТЗ «Расширение семантического ядра IR» с выводами
> аудита `docs/projects/core-audit/translation-root-causes.md` и ревью-дельтой по E2.5+.
>
> Инвариант всей программы:
> **семантический апгрейд — оптимизация; верность пикселей — закон.**
>
> Любой компонент, не воспроизводящий пиксели макета в допуске, автоматически деградирует до
> стилизованного примитива или baked-tier. Семантический kind сам по себе не даёт права менять
> Dart/Flutter output: право менять рендер появляется только после доказательства пиксельной
> эквивалентности.

---

## Карта зависимостей

```text
E0 Фундамент ──► E1 Pass Manager ──► E2 Классификатор ──► E3 Типизированный эмит ──► E5 Волны компонентов
   (P0 аудита)        │                                          ▲
                      └────────► E4 Графовые пассы ──────────────┘
E6 Корпус и пиксельный оракул — параллельно с E0/E1, обязателен до приёмки E2+
E7 Текстовая верность — отдельный трек, блокирует strict pixel для текстовых экранов
````

Правило ворот: эпик не стартует, пока DoD предыдущего по стрелке не закрыт. E6 ведётся
параллельно и является условием приёмки E2–E5.

---

## Мета-рамка всей программы

Каждый stage обязан сделать ровно одно из трёх:

1. **Сохранить факт Figma.**
2. **Создать именованное отклонение с provenance.**
3. **Перевести subtree в более безопасный fidelity-tier.**

Всё, что не одно из трёх, — баг.

---

## EPIC 0 — Фундамент достоверности (стоп-кровотечение)

**Цель:** устранить подтверждённые аудитом потери данных, которые семантический слой иначе
унаследует. Без этого эпика все последующие строятся на битом входе.

| #    | Задача                                                                                                                                                                                                | Файлы                                                           | Критерий приёмки                                                                                                                   |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| E0.1 | Дедуп уровня определений: повторный инстанс кластера → узел-ссылка (`kind=ref`, `cluster_id`, собственный placement); эмит N `Positioned` на один widget-класс                                        | `parser/dedup/prune.py`                                         | Фикстура с K инстансами компонента → ровно K размещений в Dart; инвариант мультимножества узлов (E1.2) зелёный                     |
| E0.2 | Слот ≠ paint-rect: `stack_placement` не перезаписывается; расширение тени/обводки хранится отдельным полем; компенсация на эмите `Padding(expand.left, expand.top)` + явные `SizedBox(width, height)` | `parser/render_bounds.py`, эмит обёрток слота                   | Layout-box узла с тенью в Dart == layout-box Figma по обеим осям; тень не клипается; фикстура «карточка с тенью и боковыми полями» |
| E0.3 | Z-порядок STACK всегда из clean-tree; `stackChildOrder` от LLM игнорируется или валидируется на эквивалентность с reject                                                                              | `generator/ir/tree.py` (`merge_partial_stack_child_order`)      | Перестановка порядка в LLM-фикстуре не меняет эмит; occlusion-инвариант зелёный                                                    |
| E0.4 | A11y-коррекции: бамп шрифтов <12px, перекраска контраста → именованная opt-in политика на эмите с provenance; в профиле pixel-perfect — OFF, только warnings                                          | `parser/accessibility.py`, `config/models.py`                   | Бейдж 9px эмитится 9px при выключенной политике; включённая политика логирует каждую мутацию                                       |
| E0.5 | Реплей-кэш: fallback `("llm_validated", "llm_parsed")`; `pre_emit` — только выход, никогда вход; маркер версии кода в дампе                                                                           | `debug/ir_load.py`, `debug/ir_dumps.py`                         | Повторный `generate --from-ir` детерминирован от LLM-снапшота; `pre_emit` бит-в-бит при неизменном коде                            |
| E0.6 | Гигиена: `load_fetch_result_from_dump` отвергает processed-дампы по маркеру `parserVersion`; pytest не пишет в продовый лог                                                                           | `pipeline/run/fetch.py`, `core/logging_setup.py`, `conftest.py` | `--from-dump` на processed падает с подсказкой; в прод-логе нет записей тестов                                                     |

**DoD эпика:** все шесть задач закрыты юнит-тестами на мок-фикстурах; контрольный экран
`task_management`: 6 иконок на месте, карточки 331×94 @ (22, y), карточка `101:307` не
перекрывает тексты, шрифты 9/11px сохранены.

---

## EPIC 1 — Pass Manager и законы сохранения

**Цель:** инфраструктура, делающая добавление новых проходов безопасным. Каждый transform —
именованный pass с декларированными инвариантами и автоматической пред/пост-проверкой.

| #    | Задача                                                                                                                                                                                                                                        | Файлы                                                   | Критерий приёмки                                                             |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------- |
| E1.1 | Каркас pass-ов: `Pass(name, mutates, preserves, run)`; реестр; PassManager исполняет 3 IR-пасса (`unstack`, `unpin`, `scroll_host`); dedup/render_bounds — checkpoint-validated parser transforms; lint на `node.children =` вне `ir/passes/` | `generator/ir/passes/`                                  | 3 IR-пасса через менеджер; grandfather lint зелёный                          |
| E1.2 | Валидаторы сохранения: (а) multiset node ids per checkpoint baseline; (б) `inv_stack_paint_order` (≠ `inv_z`); (в) `inv_style_truth` policy-aware; (г) emit geometry; (д) `inv_graph_sync`                                                    | `geometry/invariants/conservation.py`, `checkpoints.py` | Нарушение (а)–(д) hard fail; soft→hard через `partition_geometry_violations` |
| E1.3 | Provenance: каждая мутация узла пишет `(pass_name, field, old, new, policy?)`; дамп в `.debug/provenance/<feature>.json`                                                                                                                | pass manager                                            | Для контрольного экрана дамп объясняет 100% отличий `pre_emit` от clean-tree |
| E1.4 | Decision record классификации: на узел — `(kind, confidence, evidence, decision, reject_reason?)`; дамп рядом с provenance                                                                                                                    | совместно с E2                                          | Любая мисклассификация разбирается по дампу без отладчика                    |

**DoD эпика:** пайплайн падает hard на потере узла/порядка/стиля/графовой синхронизации; все
мутации дерева проходят через зарегистрированные pass-ы; provenance-дамп генерируется на каждом
прогоне.

---

## EPIC 2 — Классификатор семантических компонентов

**Артефакт:** `epic-2-classifier.md`
**Seam:** `apply_ir_classification_passes` в `generator/ir/materialize.py` после layout passes, до `pre_emit`.
**Pass contract:** mutates только `kind` + `payload` + classification metadata на IR; preserves multiset / paint order / graph sync; overlay kinds без T1/native proof → `auto` или annotation-only.

**Цель:** детерминированное назначение `WidgetKind` с измеримой уверенностью и законом отката.
Источники сигнала в порядке приоритета — без fuzzy matching по именам/лейблам.

**Важно:** E2 не является эпиком рендера. E2 назначает semantic annotation и пишет decision record.
До E3 semantic kind не имеет права менять Dart output. E2 считается успешным не когда “нашёл
больше кнопок”, а когда безопасно отказался от классификации во всех сомнительных случаях.

| #    | Задача                                                                                                                                                                                                                                                                                                                                                 | Файлы                                        | Критерий приёмки                                                                                                            |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| E2.1 | Расширение `WidgetKind` (5 доменов: INPUTS_DATA, ACTIONS_CONTROLS, NAVIGATION_LAYOUT, DATA_DISPLAY, OVERLAYS_FEEDBACK — состав по Приложению А) + типизированные payload-классы                                                                                                                                                                        | `schemas/ir.py`, `generator/ir/tree.py`      | mypy strict на новых схемах; payload обязателен для kinds с параметрами                                                     |
| E2.2 | Каркас детекторов: `Detector(kind) -> Classification(confidence, evidence)`. Приоритет сигналов: 1) controlled Figma component properties (`variant`/`type`/`role`/`control` из конечного словаря); 2) структурная анатомия; 3) геометрия. **Запрещено:** классификация по `node.name`, `component.name`, description, substring hints и тексту лейбла | новый `parser/semantics/`                    | Каждый detector — чистая функция с тестами; запрет на name/text matching проверяется lint’ом и ревью                        |
| E2.3 | Закон отката: `confidence < THRESHOLD` → узел остаётся геометрической правдой (`auto/container/stack/text`). Порог — конфиг, по умолчанию консервативный (`0.8`)                                                                                                                                                                                       | классификатор                                | Ни один узел ниже порога не получает final semantic kind; негативные фикстуры (E2.4) дают 0 ложных срабатываний             |
| E2.4 | Негативные фикстуры: на каждый kind минимум одна ловушка (`S/M/L ≠ weekday chips`; decorative pill ≠ button; square glyph ≠ avatar; card-like bg ≠ card; input-looking decoration ≠ text field)                                                                                                                                                        | `tests/fixtures/layouts/semantics/negative/` | Corpus-прогон: 0 false positives на ловушках                                                                                |
| E2.5 | LLM gray-zone annotations, gated. LLM может предлагать semantic annotations только при `semantics.llm_gray_zone_annotations=true`. По умолчанию OFF до зелёного deterministic corpus. LLM не назначает final kind; final decision всегда за deterministic validator                                                                                    | `llm/`, `generator/ir/validate/`, config     | При OFF LLM semantic annotations игнорируются. При ON rejected annotation не меняет IR и логируется в classification report |

**DoD эпика:** classification report по корпусу: precision на позитивных, 0 false positives на
негативных; decision record (E1.4) на каждый классифицированный/отклонённый узел; E2 в
report-only режиме не меняет Dart/golden.

---

## EPIC 2.5 — Догоны к фундаменту/законам/классификатору

> **Статус:** реализовано — см. [epic-2.5-safety.md](epic-2.5-safety.md).

> Эти задачи относятся к E0/E1/E2, но E2 уже в разработке, поэтому блок не переписывает
> in-flight E2 ретроактивно, а вводит safety-layer поверх него.
>
> Главная цель: **E2 сначала классифицирует и объясняет, но не имеет права менять пиксели/emit
> без E3-доказательства.**
>
> ID с буквами (E2.5-A…), чтобы не коллидировать с задачей-строкой E2.5 в таблице EPIC 2.

| #      | Задача                                                                                                                                                                                                                                                                                                                                                 | Файлы                                                                                               | Критерий приёмки                                                                                                                                                    |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E2.5-A | **`inv_type_truth` hard, policy-aware.** Расширить conservation E1 пятым/следующим инвариантом: `node.type` clean-tree не меняется между baseline и emit/checkpoint, кроме именованной policy-мутации с provenance. Семантика должна жить overlay’ем (`kind`) на IR-узле, а не подменять паспорт source node                                           | `geometry/invariants/{conservation,models}.py`, `parser/tree_node.py`, parser semantic legacy paths | Любое изменение `node.type` без provenance-policy = hard fail. Baseline снимается post-parse. Type-подмена ловится тестом                                           |
| E2.5-B | **Guard-мутации → provenance.** Все геометрические/структурные guard’ы, которые меняют clean-tree/IR, обязаны писать mutation record: min touch target, keyboard scroll, viewport clamp, nested scroll constraints, contrast/style guards и т.п.                                                                                                       | `generator/ir/validate/guards.py`, `validate/__init__.py`, pass/provenance layer                    | Все guard-мутации видны в `.debug/provenance/<feature>.json`; strict-fidelity профиль может их отключить; conservation консультируется с provenance           |
| E2.5-C | **Type immutability lint.** Запретить новые parser-stage semantic type mutations вне grandfather allowlist. Legacy `infer_leaf_type`/geometry enrichment остаются только как burn-down debt для W1/W3                                                                                                                                                  | lint script, `parser/tree_node.py`, `parser/interaction/*`                                          | Новая type-мутация в parser без allowlist = красный билд. W1/W3 обязаны сжигать соответствующие legacy entries                                                      |
| E2.5-D | **Safety-mode для летящего E2: classification-first, emit-later.** Первый стабилизирующий слой после E2 обязан поддерживать read-only/report-only режим: detectors считают candidates/confidence/evidence, но не меняют Dart output. `kind` может быть записан в IR только как annotation; renderer игнорирует semantic kind до E3/native verification | `generator/ir/materialize.py`, `parser/semantics/`, `debug/semantics.py`, config                    | `semantics.report_only: true` по умолчанию до E3. Golden/Dart output бит-в-бит совпадает с pre-classification pipeline                                              |
| E2.5-E | **Обязательный `classification_report.json`.** Отдельный отчёт рядом с provenance: `accepted`, `rejectedBelowThreshold`, `rejectedByInvariant`, `legacySemanticTypeDetected`, `nameSignalUsed`, `llmAnnotationUsed`, `evidence`                                                                                                                        | `.debug/semantics/<feature>.json`, `parser/semantics/report.py`, CI artifacts                 | Каждый E2-прогон пишет report. Любая мисклассификация разбирается по report без дебаггера. Формат покрыт snapshot-тестом                                            |
| E2.5-F | **LLM gray-zone за флагом, default OFF.** Пока deterministic-корпус не зелёный, LLM не участвует в назначении/аннотации kind. После включения LLM может только предложить annotation, которую deterministic validator принимает/отвергает                                                                                                              | `config/models.py`, `llm/`, `generator/ir/validate/`                                                | `semantics.llm_gray_zone_annotations=false` по умолчанию. При false LLM semantic fields игнорируются. При true rejected annotation не меняет IR и попадает в report |
| E2.5-G | **Controlled vocabulary вместо fuzzy name matching.** Новые semantic detectors могут читать component properties только как конечный словарь: `role/type/control/variant → allowed values`. `node.name`, `component.name`, description и arbitrary text не являются semantic evidence. Legacy fallback помечается отдельно                             | `parser/semantics/`, `parser/components.py`, lint                                                   | В `parser/semantics/` запрещены substring/name-hint matchers. Legacy name fallback помечается `legacySemanticTypeDetected` и не участвует в новых detectors         |
| E2.5-H | **Post-classification conservation checkpoint.** Seam E2 фиксируется строго: `normalize → validate/guards → layout_passes → classification_passes → conservation → pre_emit snapshot`. Classification mutates только `WidgetIrNode.kind/payload/classification metadata`; не children/order/clean-tree/geometry/style                                  | `generator/ir/materialize.py`, `geometry/invariants/checkpoints.py`                                 | Любая попытка классификатора изменить children, `stackChildOrder`, clean-tree, placement/style = hard fail до записи `pre_emit`                                     |
| E2.5-I | **Classification does not imply rendering.** Semantic kind не выбирает новый renderer до E3. На E2 kind — только metadata/annotation. Любой emit-path switch требует typed payload + template + fixture golden + `fidelityTier`                                                                                                                        | `generator/ir/emitter.py`, `generator/ir/screen.py`, semantic dispatch layer                        | На E2 включение semantic classifier не меняет generated Dart. Тест: same IR with/without classification → identical Dart until E3 flag enabled                      |
| E2.5-J | **Negative fixtures before positive confidence claims.** Для каждого нового kind сначала ловушки, потом позитивы. Ловушки обязательны: `S/M/L ≠ weekday chips`, декоративная pill ≠ button, card-like background ≠ card, square glyph ≠ avatar, input-looking decoration ≠ text field                                                                  | `tests/fixtures/layouts/semantics/negative/`                                                        | 0 false positives на negative corpus. Любой новый detector без negative fixture не проходит CI                                                                      |

### DoD E2.5

* `inv_type_truth` включён и ловит type-подмену.
* Все guard-мутации видны в provenance.
* Classification report генерируется на каждом E2-прогоне.
* `semantics.report_only=true` по умолчанию до E3.
* LLM gray-zone выключен по умолчанию.
* Semantic kind не влияет на Dart/Flutter emit до E3/native verification.
* Новые detectors не используют fuzzy `name/text` matching.
* Negative semantic corpus даёт 0 false positives.

---

## EPIC 3 — Типизированный эмит (Jinja2)

> **Статус:** S1–**S5 implemented** (MVP waves) — см. [epic-3-emit.md](epic-3-emit.md). IR walk в screen/extracted emit, `fidelity_tier` + inner router, `StyleContext`, lint в signoff. **`report_only: true`** до release gate.
> **`report_only`** (внешний kill-switch) и **E3.5 tier-router** (`fidelity_tier`, per-node) — **две ортогональные оси, AND**; схлопывать нельзя. Поле `fidelity_tier` на IR — E3.3 (пока нет в схеме).

**Цель:** весь Dart синтезируется из шаблонов с типизированными параметрами. Жёсткий кодинг
Dart-строк в Python запрещён и проверяется CI.

| #    | Задача                                                                                                                                                                                                                                                                           | Файлы                                                            | Критерий приёмки                                                                                                                                  |
| ---- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| E3.1 | Инфраструктура шаблонов: `templates/widgets/<kind>.dart.j2`, типизированный контекст из payload; по шаблону на kind из Приложения А                                                                                                                                              | `generator/templates/`                                           | Каждый kind эмитится только своим шаблоном                                                                                                        |
| E3.2 | Контракт стиля: семантический виджет получает полный стилевой payload Figma (цвета, радиусы, паддинги, шрифты) и подавляет Material-дефолты (`minimumSize`, тема, ink) до совпадения с макетом                                                                                   | шаблоны + `style` payload                                        | Golden-дифф семантического эмита vs геометрического ≤ ε на фикстурах kind-а                                                                       |
| E3.3 | Правило пиксельного даунгрейда + **`fidelityTier` enum** (`native_verified` / `native_unverified` / `svg_baked` / `png_baked` / `unsupported`): если golden-дифф kind-а > ε — узел эмитится стилизованным примитивом или baked-tier'ом, kind сохраняется в IR как аннотация      | эмиттер, новый `fidelity_tier` на узле                           | Дифф-бюджет соблюдён на 100% корпуса; каждый узел несёт tier; CI в strict-fidelity профиле отвергает `native_unverified`                          |
| E3.4 | CI-линт «нет Dart в Питоне»: запрет строковых литералов виджетов (`"Positioned("`, `"SizedBox("` и т.п.) вне `generator/templates/` и узкого whitelist-ядра; метрика сниффинг-решений (сейчас 144) — burn-down в CI-отчёте                                                       | CI, скрипт линта                                                 | Линт зелёный; счётчик сниффингов монотонно убывает по мере волн E5                                                                                |
| E3.5 | **Semantic emit gate (inner).** Внутри ветки, открытой внешним `report_only=false`, роутер по `fidelityTier`: native только при typed payload + template + fixture golden + `native_verified` или baked tier. `report_only=true` короткозамыкает весь роутер в геометрию (внешний AND) | `generator/ir/screen.py`, `generator/ir/expression.py`, `generator/templates/`, `validation/` | Композиция AND: `_semantic_mvp_emit_enabled` + tier. Ни один kind не меняет emit без tier. `native_unverified` запрещён в strict-fidelity. Fallback сохраняет пиксели и annotation |

**DoD эпика:** новый emit-путь полностью шаблонный; линт включён в CI как blocking; semantic kind
не влияет на Dart без `native_verified`/baked tier и fixture-golden доказательства.

---

## EPIC 4 — Middle-end пассы графа

> **Статус:** **реализовано (S5)** — см. [epic-4-graph-passes.md](epic-4-graph-passes.md).

**Цель:** два графовых оптимизатора из исходного ТЗ, оформленные как pass-ы E1 с
формализованными критериями: без viewport-магии и приёмки по одному макету.

| #    | Задача                                                                                                            | Критерий активации (формальный)                                                                                                                                                                                                                                                                        | Критерий приёмки                                                                                                                                                                         |
| ---- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.1 | **Unstacking Pass** (`generator/passes/unstack.py`): STACK → ROW/COLUMN/WRAP                                      | (а) попарные AABB детей не пересекаются; (б) координаты монотонны по одной оси; (в) дисперсия зазоров ≤ ε (0.5px) — иначе ROW/COLUMN с явными `SizedBox`-гэпами, WRAP только при ≥2 рядах с равным зазором; (г) painter's order детей при де-стеке не меняет видимый результат (предусловие от E1.2-б) | Property-тесты на сгенерированных раскладках; фикстура класса «ряд однородных чипов» без упоминания node-id в тестах; 0 наложенных `Positioned` на корпусе для узлов, прошедших критерий |
| E4.2 | **Height Unpinning Pass** (`generator/passes/unpin_height.py`): каскадные `FIXED` высоты → `minHeight`/`Flexible` | (а) COLUMN-хост содержит текст/адаптивные узлы → `height` родителя становится `BoxConstraints(minHeight:)`; (б) scroll-host: content extent > высоты артборда из clean-tree, не константа 800 → корень оборачивается `NAV_SCROLL_HOST`                                                                 | Фикстуры: длинный текст растягивает карточку без RenderFlex overflow; экран выше артборда скроллится; экран ниже — нет                                                                   |
| E4.3 | Оба pass-а зарегистрированы в E1 с декларацией инвариантов и флагами политики                                     | —                                                                                                                                                                                                                                                                                                      | Provenance показывает каждое срабатывание; conservation-валидаторы зелёные после pass-ов                                                                                                 |

**DoD эпика:** оба pass-а в реестре, corpus-прогон без hard-нарушений, метрика «наложенные
Positioned одно-осевых рядов» на корпусе = 0.

---

## EPIC 4.5 — Догоны к E3/E4 (ревью коллеги, верифицировано против кода 2026-06-12)

> Аналог E2.5: E4 в работе, поэтому правки к E3/E4 вынесены отдельным блоком, не ретро-правят
> in-flight код. **Ключевой факт ревью:** две из трёх «мин» коллеги код уже обезвредил —
> отмечено по задачам. Назван 4.5 (не «E5»), чтобы не коллидировать с EPIC 5 «Волны».

| # | Задача | Статус в коде | Файлы | Критерий приёмки |
|---|--------|---------------|-------|------------------|
| E4.5-A | **`styled_primitive` tier.** | ✅ реализовано — см. [epic-4.5-fidelity-contract.md](epic-4.5-fidelity-contract.md) | `generator/ir/fidelity/` | 6-й tier + router + styled emit |
| E4.5-B | **Fingerprint-baseline для legacy-зоны линта.** | ✅ `tests/fixtures/lint/emitter_baseline.txt` + ratchet в `scripts/lint_dart_in_python.py` | `tests/fixtures/lint/`, `scripts/` | Новый fingerprint = CI fail |
| E4.5-C | **Baked text policy.** | ✅ `fidelity/text_policy.py`, `baked_gate.py`, shadow report | `generator/ir/fidelity/` | Live text блокирует baked; strict profiles hard fail |
| E4.5-D | **Static verification manifest.** | ✅ composite manifest + `figma-flutter fidelity promote/validate` | `fidelity_manifest.yaml`, `cli/fidelity.py` | `tier_source` на IR; generate без tier screenshot-loop |

**DoD E4.5:** закрыт — см. [epic-4.5-fidelity-contract.md](epic-4.5-fidelity-contract.md).

## EPIC 4.5 — Контракт fidelity-tier, baked fallback и verification manifest

> Этот эпик вставляется между E4 и E5 как стабилизирующий слой перед массовым rollout компонентов.
> Цель: не дать semantic/native emit превратиться в медленный runtime-эксперимент и не позволить baked fallback сохранять пиксели ценой смерти локализации, accessibility и живого текста.

**Ключевой принцип:**

> `fidelityTier` — это не результат паники во время `generate`.
> Это заранее проверенный capability label:
> `kind + feature_profile + template_version → fidelityTier`.

Обычная генерация **только читает** verification manifest. Тяжёлые golden/diff-прогоны выполняются в CI / visual QA / signoff и обновляют или валидируют manifest.

---

### E4.5.1 — Static verification manifest

| #      | Задача                                                                                                                                                                                                                                                      | Файлы                                                                                            | Критерий приёмки                                                                                                                                                                                                              |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.1 | Ввести статический verification manifest: `kind + feature_profile + template_version → fidelityTier`. Manifest описывает, какие semantic widgets доказанно могут эмититься native, какие требуют styled primitive, baked fallback или считаются unsupported | `docs/figma-feature-coverage.md`, `validation/`, `screens.yaml` или `verification_manifest.yaml` | Обычный `generate` не запускает headless Flutter / browser screenshot loop для выбора tier. Каждый semantic node получает `fidelityTier` и `tier_source`: `manifest`, `policy_fallback`, `manual_override`, `runtime_signoff` |

---

### E4.5.2 — Запрет runtime-diff routing внутри генерации

| #      | Задача                                                                                                                                                                                                                    | Файлы                                                     | Критерий приёмки                                                                                                                                                                                                    |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.2 | Разделить фазы генерации и валидации. Runtime golden diff (`≤ ε`) является задачей CI / visual QA / signoff, а не частью пользовательского compiler pass. Во время live generation routing идёт только по manifest/policy | `generator/ir/emitter.py`, `validation/`, pipeline config | В fast/live generate нет цикла `emit → run Flutter → screenshot → compare → re-emit`. Отсутствующая или stale manifest-запись даёт `native_unverified` или fallback по policy, но не запускает тяжёлый runtime-loop |

---

### E4.5.3 — Расширенный `fidelityTier`

| #      | Задача                                                                                                                                                                                                                             | Файлы                                  | Критерий приёмки                                                                                                                                                  |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.3 | Зафиксировать enum tiers: `native_verified`, `native_unverified`, `styled_primitive`, `svg_baked`, `png_baked`, `unsupported`. `native_unverified` — временное состояние разработки, запрещённое в strict-fidelity/profile release | IR schema, emitter, validation reports | Каждый узел, прошедший semantic path, несёт tier. Strict-fidelity CI отвергает `native_unverified`. `unsupported` не маскируется успешным emit без warning/report |

---

### E4.5.4 — Baked text policy

| #      | Задача                                                                                                                                                                                                                                                                              | Файлы                                                              | Критерий приёмки                                                                                                                                                         |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| E4.5.4 | Ввести политику живого текста. Baked tiers (`svg_baked` / `png_baked`) запрещены для live text: локализуемого, интерактивного, selectable, editable, dynamic или accessibility-critical текста. Для static/decorative/marketing текста baked допускается только как named trade-off | emitter, text semantics, localization report, accessibility report | Subtree с live text не уходит в baked tiers. Static baked text требует `semanticLabel`/alt semantics + warning в report. Strict-l10n profile делает baked text hard fail |

**Классы текста:**

```text
live_localizable
live_accessibility
selectable
editable
dynamic_runtime
decorative_static
marketing_static
```

**Правило:**

```text
live_* / selectable / editable / dynamic_runtime → baked forbidden
decorative_static / marketing_static → baked allowed only with semantic shadow + warning
```

---

### E4.5.5 — Semantic shadow для baked fallback

| #      | Задача                                                                                                                                                                                                | Файлы                                           | Критерий приёмки                                                                                                                                            |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.5 | Если subtree уходит в `svg_baked`/`png_baked`, система обязана сохранить semantic shadow: readable label, source node ids, original text inventory, localization blocker status, accessibility status | emitter, semantics report, accessibility report | Baked subtree не является “чёрной картинкой” без паспорта. Report показывает, какие тексты/роли были запечены, почему, и какие runtime возможности потеряны |

Пример report-записи:

```json
{
  "figmaId": "123:456",
  "fidelityTier": "png_baked",
  "tierSource": "policy_fallback",
  "containsText": true,
  "textPolicy": "marketing_static",
  "semanticLabel": "Summer sale, up to 40% off",
  "localizationBlocker": true,
  "accessibilityStatus": "semantic_shadow_only",
  "reason": "native typography diff exceeded strict_pixel budget"
}
```

---

### E4.5.6 — Baseline-ratchet для линтера «нет Dart в Python»

| #      | Задача                                                                                                                                                                                                                                     | Файлы                                           | Критерий приёмки                                                                                                                                                                                     |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.6 | Внедрить baseline-механизм для CI-линтера, запрещающего Flutter/Dart widget literals в Python. Текущий долг фиксируется как allowlist, новые нарушения запрещены. Baseline должен хранить stable fingerprints, а не только число нарушений | `tests/fixtures/lint/emitter_baseline.txt`, CI, lint script | CI не блокирует текущие 144 legacy violations, но падает на любом новом violation. Удаление старого violation уменьшает burn-down count. Нельзя удалить 10 старых и добавить 10 новых без падения CI |

Формат baseline-записи:

```text
path | normalized_snippet_hash | category | owner_epic
```

Пример:

```text
src/figma_flutter_agent/generator/layout/foo.py | 9f12ab03 | dart_widget_literal | E5-W1
```

---

### E4.5.7 — Burn-down report для emitter debt

| #      | Задача                                                                                                                                              | Файлы                     | Критерий приёмки                                                                                                                                |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.7 | CI должен публиковать burn-down report по Dart-in-Python debt: baseline count, removed legacy violations, new violations, violations by module/wave | CI artifacts, lint script | На каждом PR видно: стало лучше, хуже или без изменений. Новые violations = hard fail. Legacy count должен монотонно снижаться в рамках E5-волн |

---

### E4.5.8 — Semantic emit gate через manifest

| #      | Задача                                                                                                                                                                                                                              | Файлы                                                                           | Критерий приёмки                                                                                                    |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| E4.5.8 | Semantic kind получает право менять Dart path только если manifest подтверждает `native_verified` или разрешённый fallback. Если manifest entry отсутствует, kind остаётся annotation-only либо уходит в styled primitive по policy | `generator/ir/emitter.py`, `verification_manifest.yaml`, `generator/templates/` | Ни один kind из E2 не меняет emit только потому, что классификатор уверен. Emit switch требует manifest-backed tier |

---

### E4.5.9 — Profiles: strict-fidelity / strict-l10n / dev

| #      | Задача                                                                                                                                                                                                                            | Файлы                           | Критерий приёмки                                                                                                                                                                       |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.9 | Ввести profile-aware правила fallback: `strict_fidelity`, `strict_l10n`, `strict_a11y`, `dev`. В strict profiles система предпочитает hard fail / styled primitive живому baked-тексту; в dev может выдавать warning и продолжать | config, emitter policy, reports | Поведение baked/native/fallback различается по профилю явно и тестируется. Strict-l10n запрещает baked text с localization blockers. Dev profile не скрывает blockers, а пишет warning |

---

### E4.5.10 — Связь с E6/E7

| #       | Задача                                                                                                                                                                                   | Файлы                                              | Критерий приёмки                                                                                                                                  |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| E4.5.10 | Связать verification manifest с E6 golden pipeline и E7 text policy. CI/golden прогоны обновляют/валидируют tier entries; text policy определяет, можно ли subtree baked/raster fallback | E6 validation, E7 text semantics, manifest tooling | Tier не назначается вручную без связи с coverage/golden evidence. Text subtree с live policy не получает baked tier даже при pixel-perfect raster |

---

### DoD E4.5

* `fidelityTier` читается из static verification manifest, а не вычисляется тяжёлым runtime-loop внутри обычного `generate`.
* Live generation не делает `emit → run Flutter → screenshot → compare → re-emit`.
* Semantic emit switch невозможен без manifest-backed tier.
* `native_unverified` запрещён в strict-fidelity/release profile.
* Baked tiers запрещены для live/localizable/selectable/editable/accessibility-critical текста.
* Static/decorative/marketing baked text допускается только с semantic shadow и явным warning.
* Strict-l10n profile делает baked text с localization blocker hard fail.
* CI-линтер «нет Dart в Python» работает через baseline-ratchet: текущий долг не блокирует, новый долг запрещён.
* Burn-down report по legacy Dart-string debt публикуется на каждом PR.
* E6 golden pipeline и E7 text policy являются источниками правды для verification manifest.

---

### Короткая формулировка для команды

> E4.5 фиксирует промышленный контракт рендера:
> **пиксели можно спасать fallback’ом, но нельзя молча убивать живой текст, локализацию и accessibility.**
> `fidelityTier` — это не runtime-гадание во время generate, а заранее доказанный capability label из manifest.



---

## EPIC 5 — Волны компонентов + сжигание эвристик

**Цель:** поэтапный rollout 40 kinds вертикальными срезами. Каждая волна обязана удалить
замещаемые legacy-модули — двойного владения не существует.

**E5 — umbrella epic.** Первый mergeable slice — только **E5.W1**; W2–W4 — отдельные follow-up
волны с собственными acceptance criteria. Детали и merge gate: [epic-5-w1.md](epic-5-w1.md).

### E5 Scope and Wave Acceptance

E5 must not be merged as one large W1→W4 batch. Each wave is an independently mergeable slice with its own detector contract, typed payload, template or explicit fallback, positive/negative corpus, classification report, fidelity manifest entries, legacy heuristic burn-down list, and precision/false-positive gates.

The first mergeable E5 slice is **E5.W1** only. W2–W4 remain planned follow-up waves and must not block W1 merge unless W1 introduces architecture that makes later waves impossible.

| Волна | Kinds | Сжигаемые модули (полностью или функции) | Ворота |
| ----- | ----- | ---------------------------------------- | ------ |
| **W1** | BUTTON_FILLED / OUTLINED / TEXT, INPUT_TEXT_FIELD, CHIP_CHOICE, CONTAINER_CARD, CONTAINER_LIST_TILE, TECHNICAL_DIVIDER | `parser/interaction/buttons.py`, `parser/interaction/chips.py` (W1 path), `generator/subtree/auth_buttons.py` | [E5.W1 Precision Gate](epic-5-w1.md): precision ≥ 0.95, per-kind ≥ 0.90, recall ≥ 0.80, blocker-negative FP = 0 |
| W2 | CHIP_FILTER / INPUT / ACTION, CONTROL_CHECKBOX / RADIO / SWITCH / SEGMENTED, INPUT_SEARCH_BAR, MEDIA_AVATAR, MEDIA_BADGE, BUTTON_ICON | `_WEEKDAY_CHIP_LABELS`, UI-лексика в `interaction/shared.py`, `layout/interactive_weekday.py` | W1 закрыта; негативные ловушки W2 зелёные |
| W3 | CONTAINER_GRID / CAROUSEL / ACCORDION, NAV_APP_BAR / TAB_BAR / SCROLL_HOST / BOTTOM_BAR, INPUT_DROPDOWN / STEPPER / SLIDER, NAV_STEPPER / PAGINATION | `parser/interaction/product.py`, `reconcilers_grid*.py`, `reconcilers_media.py`, `widgets/stepper.py` | W2 закрыта |
| W4 | OVERLAY_*, FEEDBACK_*, INPUT_PICKER_*, NAV_DRAWER | остаточные распознаватели | W3 закрыта; research-spike по overlay states |

> **False positive blocks merge. False negative creates backlog.**

### Сквозные правила волн

* Срез = detector + payload + template + positive fixtures + negative fixtures + запись в список снесённых legacy-модулей.
* Каждый срез добавляет строки в `classification_report` и `figma-feature-coverage.md`: какие сигналы приняты, какие ловушки отвергнуты, какой `fidelityTier` доступен.
* Метрики burn-down в CI-отчёте: archetype predicates (база: 162), domain lexicon (база: 340), string-sniffing decisions (база: 144). **W1:** монотонное снижение; hard targets — DoD всего E5, не blocker W1.
* Запрещено добавлять новый `looks_like_*` вне `parser/semantics/`; внутри `parser/semantics/` запрещён fuzzy name/text matching.
* Двойное владение запрещено: если kind переведён в verified semantic path, legacy detector/renderer либо удалён, либо помечен burn-down allowlist с датой удаления.
* Волна считается закрытой только при 0 false positives на blocker-negative fixtures этой волны.

**DoD эпика:** все 4 волны закрыты; счётчики burn-down: predicates ≤ 30 (остаток —
детекторы semantics), domain lexicon ≤ 50, string sniffing ≤ 20.

---

## EPIC 6 — Корпус и пиксельный оракул (параллельный, блокирует приёмку E2+)

**Цель:** измеримость. Без пиксельного оракула приёмка семантического emit невозможна.

**S6 (детали, ворота, slice map):** [epic-6-corpus-oracle.md](epic-6-corpus-oracle.md).

### S6 — ключевые решения (зафиксировано)

```text
>=25 real-design corpus total
8–12 strict_pixel_blocking (release-blocking)
остальное advisory_pixel / semantic_only

pre-E7: non_text_pixel_diff + geometry_iou блокируют;
        text_region_pixel_diff — advisory (glyph mismatch не валит релиз)

E6.8 post-E3: emit(classified) == emit(auto) при report_only / native_unverified / styled fallback

E6.10: E6 публикует fidelity_promotion_candidates.json;
       signoff НЕ мутирует manifest; promote — manual dry-run / write-patch → PR

S5.W1 synthetic = unit gate; S6.1.W1 real-design W1 = integration oracle под E6
```

| #    | Задача                                                                                                                                                                                          | Критерий приёмки                                                                                                                        |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| E6.1 | Расширение **real-design** корпуса (offline dumps): flat canvas, DS variants, chips, long text, shadows, mirror/rotate, deep nesting. Теги: `strict_pixel_blocking` \| `advisory_pixel` \| `semantic_only` | **>= 25** фикстур + goldens; **S6.1.W1**: >=10 W1 cases, >=5 real negative traps                                                              |
| E6.2 | Golden diff в CI: blocking только на **curated subset (8–12)**; полный корпус — advisory report                                                                                                 | Subset: регрессия diff = красный билд; advisory: backlog artifact                                                                        |
| E6.3 | CI-артефакты: classification report (E2), provenance (E1.3), burn-down (E3.4/E5), promotion candidates (E6.10)                                                                                | Артефакты на каждом signoff                                                                                                              |
| E6.4 | Oracle modes: `strict_pixel` (blocking subset, structural channel), `layout_pixel`, `semantic_runtime`                                                                                          | `strict_pixel` blocking на 8–12; text glyph diff advisory до E7                                                                          |
| E6.5 | **Метаморфик-тесты**: shift +10px, duplicate N, z-order                                                                                                                                         | Каждый закон >=1 метаморфик на blocking subset (затем advisory)                                                                          |
| E6.6 | **Coverage matrix** `docs/figma-feature-coverage.md`                                                                                                                                            | Матрица заполнена; каждая `native` — fixture + golden                                                                                  |
| E6.7 | **Adversarial affine fixtures**                                                                                                                                                                 | Native proof или baked tier; «почти» не принимается                                                                                        |
| E6.8 | **Semantic no-op oracle** (post-E3): classify не меняет Dart/pixels без manifest-backed `native_verified`                                                                                     | `report_only=true` → emit идентичен auto IR; debug JSON/metadata only                                                                   |
| E6.9 | **Semantic report corpus gate** + full-tree FP на real-design corpus                                                                                                                            | nameSignal=0; legacy burn-down монотонен; unexpected_semantic_nodes=0                                                                    |
| E6.10 | **Verification evidence pipeline**: signoff → `fidelity_promotion_candidates.json`; manifest patch только через manual `fidelity promote`                                                      | CI `--dry-run` only; `--write-patch` local/PR; generate только читает manifest                                                           |

**DoD эпика:** blocking gates на curated subset + semantic gates; advisory report на полном корпусе;
strict structural pixel oracle; no-op oracle; coverage matrix; **без** auto-promote manifest в CI.

---

## EPIC 7 — Текстовая верность (отдельный трек, RC-K)

**Цель:** pixel-perfect текст — это не `fontSize`, а shaping/metrics/per-run. Смешанный rich text
не должен терять per-span размер, семейство, межстрочность и стиль.

| #    | Задача                                                                                                                                                              | Файлы                                    | Критерий приёмки                                                                                   |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------------- |
| E7.1 | Расширить `TextSpanPart`: per-span `font_size`, `font_family`, `line_height`, `font_style`                                                                          | `schemas/style.py`, `parser/richtext.py` | Смешанный run эмитится с верными per-span размерами; round-trip из Figma `characterStyleOverrides` |
| E7.2 | Закон сохранения `textMetricsFrame`: bbox, render bounds, baseline/glyph offset, line count — conservation-code `inv_text_metrics` (soft→hard в strict text subset) | `geometry/invariants/`                   | Drift метрик текста > ε ловится                                                                    |
| E7.3 | `textAsRaster` fallback-tier для недоказуемого текста (marketing/hero), интеграция с `fidelityTier` (E3.3)                                                          | emitter, assets/render-boundary          | Текст, не прошедший strict pixel/text oracle, уходит в raster/baked tier, а не “почти”             |
| E7.4 | Раздельный oracle «Figma text raster vs Flutter text raster»                                                                                                        | `validation/text/`, `validation/pixel/`  | Text-specific diff показывает style/metrics drift отдельно от layout drift                         |

**DoD эпика:** отдельные gates на per-run style, line-height, baseline/glyph-top; `strict_pixel`
не маскирует текст в corpus-subset; недоказуемый текст имеет safe fallback.


Да, братан. С учётом `llm_visual_refine: false` медленный контур — **не visual refine**. Я копнул глубже: код показывает, что golden/fixture capture сам по себе может каждый раз уходить в cold workspace.

## Что сказал код

### 1. `generate_fixture_goldens.py` не передаёт `project_dir`

Скрипт генерации fixture goldens в цикле по экранам вызывает:

```python
result = capture_planned_flutter_golden_png(
    planned,
    feature_name=entry.feature,
    golden_runtime=args.golden_runtime,
    settings=settings,
    flutter_sdk=flutter_sdk,
    layout_tree=layout_tree,
)
```

Там **нет `project_dir`**. Значит capture не может использовать реальный Flutter project cache. 

---

### 2. Host path без `project_dir` создаёт новый temp workspace

Если `project_dir` не используется, код идёт сюда:

```python
capture_dir, tmp_handle = _prepare_capture_workspace()
...
_run_golden_test_in_workspace(... skip_build_clean=False ...)
```



А `_prepare_capture_workspace()` создаёт новый временный проект:

```python
tmp = tempfile.TemporaryDirectory(prefix="figma-flutter-golden-")
capture_dir = Path(tmp.name) / "golden_capture"
_copy_skeleton_project(capture_dir)
```



И самое важное: skeleton копируется **без `.dart_tool` и `build`**:

```python
ignore=shutil.ignore_patterns(".dart_tool", "build")
```



То есть каждый screen golden потенциально стартует как новый Flutter-проект без кэша.

---

### 3. Docker path делает то же самое

Если `runtime.golden_capture: auto`, код выбирает Docker, когда Docker доступен. 

Docker capture тоже каждый раз создаёт temp dir:

```python
with tempfile.TemporaryDirectory(prefix="figma-flutter-golden-docker-") as tmp:
    capture_dir = Path(tmp) / "project"
    _copy_skeleton_project(capture_dir)
```

Потом запускает:

```bash
docker compose run --rm -v <capture_dir>:/capture golden-capture
```



То есть даже в Docker у вас каждый экран получает новый mounted `/capture` без `.dart_tool/build`.

---

### 4. Warm sandbox уже написан, но не подключён

Есть файл `dev/warm_capture.py`, и он прямо описывает нужную цель:

> persistent warm sandbox for fast iterative Flutter screen PNG capture; reuses `GoldenCaptureHostSession` so incremental builds apply after first cold compile. 

Он хранит sandbox тут:

```text
project/.figma-flutter/capture-sandbox
```

и кеширует session в `_WARM_SESSIONS`. 

Но поиск показал, что `capture_planned_in_warm_sandbox` используется только в самом файле и тесте, не в основном golden generation path. 

## Диагноз

Разраб может быть прав только для **первого cold compile**.

Но текущий код, похоже, делает так:

```text
screen 1 → новый temp Flutter project → cold compile
screen 2 → новый temp Flutter project → cold compile
screen 3 → новый temp Flutter project → cold compile
```

Это не “Flutter так устроен”.
Это **пайплайн сам убивает кэш**.

---

# EPIC 8 — Golden Capture Performance & Warm Runtime

> W0: [epic-8-w0.md](epic-8-w0.md). W1a: [epic-8-w1a.md](epic-8-w1a.md). Цель: превратить golden/screenshot generation из cold-build процесса на 10–15 минут в управляемый warm capture pipeline.
> Локальная итерация должна использовать persistent sandbox / in-project cache и fast PNG capture. True golden / Docker / `--update-goldens` остаются для CI, signoff и nightly corpus.

---

## Контекст проблемы

Текущий golden/fixture capture может создавать новый временный Flutter workspace на каждый экран. При копировании skeleton project намеренно исключаются `.dart_tool` и `build`, поэтому Flutter test cache не переиспользуется. В Docker path происходит аналогично: на каждый capture создаётся новый temp project и монтируется в контейнер как `/capture`.

Фактически система делает cold compile чаще, чем необходимо.

---

## Ключевой принцип

> **Cold compile допустим один раз.
> Повторный capture того же project/sandbox должен быть warm.**

Локальная генерация и visual QA не должны каждый раз создавать новый disposable Flutter project.

---

## E8.1 — Golden timing instrumentation

| #    | Задача                                                                                                                                                             | Файлы                                                                                              | Критерий приёмки                                                                                        |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| E8.1 | Добавить phase timing logs для golden/capture pipeline: workspace prepare, planned write, asset/font sync, pub get, flutter test start/end, PNG read/copy, compare | `validation/golden_capture/*`, `scripts/generate_fixture_goldens.py`, `fixtures/golden_compare.py` | Каждый capture пишет structured timing report в лог и `.debug/perf/golden_capture_<feature>.json` |

Минимальный формат:

```json
{
  "feature": "task_management",
  "mode": "host_temp",
  "fastCapture": true,
  "workspace": "temp",
  "timingsSec": {
    "prepareWorkspace": 1.2,
    "writePlanned": 0.4,
    "syncAssets": 1.8,
    "pubGet": 3.1,
    "flutterTest": 612.0,
    "readPng": 0.1
  }
}
```

---

## E8.2 — Persistent warm capture sandbox

| #    | Задача                                                                                                                                                                                  | Файлы                                                                                                                              | Критерий приёмки                                                                                                                                          |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| E8.2 | Подключить существующий `dev/warm_capture.py` к local fixture/golden generation path. Для локального режима использовать `project/.figma-flutter/capture-sandbox` вместо temp workspace | `dev/warm_capture.py`, `scripts/generate_fixture_goldens.py`, `fixtures/golden_compare.py`, `validation/golden_capture/capture.py` | Повторный capture того же экрана не создаёт `/tmp/figma-flutter-golden-*`; сохраняет `.dart_tool`/`build`; второй прогон быстрее первого минимум в 3 раза |

---

## E8.3 — Fast capture по умолчанию для local/dev

| #    | Задача                                                                                                                                                                                     | Файлы                                                            | Критерий приёмки                                                                                                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| E8.3 | Развести режимы `fast_png_capture` и `true_golden_update`. Local/dev использует fast capture test. `flutter test --update-goldens` разрешён только для CI/signoff/nightly или явного флага | `validation/golden_capture/capture_host.py`, CLI scripts, config | Local capture не вызывает `--update-goldens` без explicit `--update-goldens`; PNG capture пишет image через env path |

---

## E8.4 — Pub get cache key

| #    | Задача                                                                                                                                              | Файлы                                  | Критерий приёмки                                                                                            |
| ---- | --------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| E8.4 | Не запускать `flutter pub get` на каждый capture, если `pubspec.yaml`, `pubspec.lock`, Flutter SDK version и capture skeleton version не изменились | `validation/golden_capture/project.py` | Повторный warm capture пишет `pub get skipped`; `pub get` запускается только при изменении dependency graph |

Cache stamp:

```text
.dart_tool/figma_flutter_agent/pubspec.hash
```

Hash inputs:

```text
pubspec.yaml
pubspec.lock
flutter --version
capture skeleton version
```

---

## E8.5 — Fixture corpus batching

| #    | Задача                                                                                                                     | Файлы                                                               | Критерий приёмки                                                                                 |
| ---- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| E8.5 | Генерация нескольких fixture goldens должна использовать один warm workspace/session, а не cold workspace на каждый screen | `scripts/generate_fixture_goldens.py`, `fixtures/golden_compare.py` | При генерации N screens cold compile происходит максимум один раз на project/sandbox/runtime key |

Сейчас `generate_fixture_goldens.py` идёт циклом по entries и вызывает capture отдельно для каждого экрана. 
Нужно передавать/reuse `host_session` или warm sandbox между итерациями.

---

## E8.6 — Runtime mode contract

| #    | Задача                                                                                                                                                                                      | Файлы                                       | Критерий приёмки                                                                                     |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| E8.6 | Явно разделить runtime modes: `local_fast`, `local_true_golden`, `ci_docker`, `nightly_corpus`. `auto` не должен тихо выбирать Docker для локального hot loop, если цель — быстрая итерация | `validation/golden_runtime.py`, config, CLI | Логи явно пишут выбранный mode и причину. Local command по умолчанию не уходит в Docker cold capture |

Проблема сейчас: `auto` выбирает Docker, если Docker доступен. 
Для CI это ок. Для локальной скорости — часто нет.

---

## E8.7 — Docker warm volume

| #    | Задача                                                                                                                                                                                                  | Файлы                                                                    | Критерий приёмки                                                                                                   |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| E8.7 | Для Docker capture использовать persistent named volume/cache для Flutter/Dart artifacts или persistent mounted capture workspace. Не создавать полностью cold `/capture` на каждый экран в corpus mode | `docker/render-capture/*`, `validation/golden_capture/capture_docker.py` | Docker corpus capture второго экрана не пересобирает весь Flutter test target с нуля; timings показывают cache hit |

Текущий Docker path создаёт temp project на каждый capture. 

---

## E8.8 — Capture cache by content hash

| #    | Задача                                                                                                                                          | Файлы                                                        | Критерий приёмки                                                                                   |
| ---- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| E8.8 | Добавить cache PNG результата по hash: planned Dart files + asset manifest + layout tree relevant geometry + capture mode + Flutter SDK version | `validation/golden_capture/cache.py`, `render_log`, fixtures | Если generated code/assets не изменились, повторный capture возвращается из cache без Flutter test |

Cache key:

```text
feature_name
planned_files_hash
asset_manifest_hash
layout_tree_hash
flutter_version
capture_mode
device_pixel_ratio
theme_variant
```

---

## E8.9 — Performance gates

| #    | Задача                                                                                                                | Файлы                          | Критерий приёмки                                                                    |
| ---- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------ | ----------------------------------------------------------------------------------- |
| E8.9 | Ввести performance thresholds для local/warm capture. Не как flaky hard gate на CI, а как warning/error в perf report | perf tooling, CI optional gate | Warm local capture > 60s получает warning; >180s получает failure в local perf test |

Целевые SLA:

```text
Cold first local capture: <= 5 min target, <= 8 min warning
Warm repeated local capture: <= 30 sec target, <= 60 sec warning
Fixture corpus N screens: 1 cold compile + warm incremental per screen
CI true golden: допускается дольше, но timing report обязателен
```

---

## E8.10 — Runtime geometry capture reuse

| #     | Задача                                                                                                                                                                | Файлы                                                             | Критерий приёмки                                                                     |
| ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| E8.10 | Если `runtime_geometry_capture_if_missing=true`, runtime geometry должен использовать тот же warm capture/session/cache, а не запускать отдельный cold golden capture | `stages/runtime_geometry_check.py`, `validation/golden_capture/*` | Geometry gate не вызывает второй независимый cold capture для того же planned output |

Runtime geometry сейчас при missing keys вызывает `capture_planned_flutter_golden_png`. 

---

## DoD E8

* Local/dev golden capture использует persistent warm sandbox или in-project cache.
* Повторный capture того же экрана не создаёт новый temp Flutter project.
* `.dart_tool` и `build` сохраняются между warm captures.
* `flutter pub get` пропускается, если dependency graph не изменился.
* `--update-goldens` не используется в local fast path без явного флага.
* Fixture corpus generation переиспользует одну session/workspace на batch.
* Docker mode имеет persistent cache/volume или явно помечен как CI-only cold path.
* Runtime geometry capture переиспользует warm capture/cache.
* Каждый capture пишет timing breakdown.
* Warm повторный capture целится в секунды/десятки секунд, а не 10–15 минут.

---

## Короткий текст для команды

> Сейчас golden generation медленный не потому, что “Flutter всегда так”, а потому что код часто создаёт новый disposable Flutter workspace без `.dart_tool/build`, а затем запускает `pub get` и `flutter test` как cold compile.
> В репе уже есть `warm_capture.py`, который решает именно эту проблему, но он не подключён к основному fixture/golden path.
> E8 должен сделать warm capture основным local/dev режимом, а cold true-golden оставить для CI/signoff/nightly.


---

## Приложение А. Реестр kinds

Домены и состав — по разделам 2.1–2.5 исходного ТЗ «Расширение семантического ядра IR»:

### INPUTS_DATA

* `INPUT_TEXT_FIELD`
* `INPUT_SEARCH_BAR`
* `INPUT_DROPDOWN`
* `INPUT_PICKER_DATE`
* `INPUT_PICKER_TIME`
* `INPUT_STEPPER`
* `INPUT_SLIDER`
* `INPUT_FILE_UPLOADER`

### ACTIONS_CONTROLS

* `BUTTON_FILLED`
* `BUTTON_OUTLINED`
* `BUTTON_TEXT`
* `BUTTON_FAB`
* `BUTTON_ICON`
* `CHIP_CHOICE`
* `CHIP_FILTER`
* `CHIP_INPUT`
* `CHIP_ACTION`
* `CONTROL_CHECKBOX`
* `CONTROL_RADIO`
* `CONTROL_SWITCH`
* `CONTROL_SEGMENTED`

### NAVIGATION_LAYOUT

* `NAV_APP_BAR`
* `NAV_BOTTOM_BAR`
* `NAV_TAB_BAR`
* `NAV_DRAWER`
* `NAV_STEPPER`
* `NAV_PAGINATION`
* `NAV_SCROLL_HOST`

### DATA_DISPLAY

* `CONTAINER_CARD`
* `CONTAINER_LIST_TILE`
* `CONTAINER_GRID`
* `CONTAINER_CAROUSEL`
* `CONTAINER_ACCORDION`
* `MEDIA_AVATAR`
* `MEDIA_BADGE`
* `TECHNICAL_DIVIDER`

### OVERLAYS_FEEDBACK

* `OVERLAY_DIALOG`
* `OVERLAY_BOTTOM_SHEET`
* `OVERLAY_SNACKBAR`
* `OVERLAY_BANNER`
* `FEEDBACK_LOADER`
* `FEEDBACK_SKELETON`
* `FEEDBACK_TOOLTIP`

Каждый kind при имплементации получает строку в таблице соответствия:

```text
kind → detector sources → payload → template → wave → burned legacy modules → fidelityTier support
```

---

## Приложение Б. Изменения к исходному ТЗ (дельта)

1. Критерий приёмки «`dart analyze` на cash_change_layout» заменён на корпусные критерии (E6) — приёмка по одному макету и по node-id исключена как анти-паттерн.
2. Константа «800px» в scroll-критерии заменена высотой артборда из clean-tree.
3. Добавлены: контракт классификатора с законом отката (E2.2–E2.3), правило пиксельного downgrade (E3.3), Pass Manager с законами сохранения (E1), волны с обязательным сжиганием legacy (E5), пиксельный oracle (E6).
4. Unstacking-критерий формализован (E4.1): попарная непересекаемость AABB + монотонность + дисперсия зазоров, выбор ROW/COLUMN/WRAP по структуре рядов.
5. Принято из ревью: RC-I (`node.type` подменяется семантикой → E2.5-A/C), RC-K (rich text per-span → E7), RC-L (oracle resize/mask → E6.4), RC-M (guard-мутации → E2.5-B), RC-N (`fidelityTier` → E3.3/E3.5), RC-P/H (метаморфики + coverage matrix → E6.5/E6.6), RC-J (adversarial affine → E6.7).
6. Добавлен safety-layer для уже летящего E2: `report_only` по умолчанию, classification report, no-op oracle, LLM gray-zone OFF, controlled vocabulary, post-classification conservation checkpoint.
7. Уточнён принцип: **E2 is annotation, not rendering.** Semantic kind не меняет Dart до E3/native verification.

---

## Приложение В. Принцип E2 одной строкой

> **E2 is annotation, not rendering.**
>
> Классификатор имеет право сказать: «это похоже на кнопку с confidence 0.91, потому что
> `component.role=button` и структура совпала».
>
> Он не имеет права из-за этого менять layout, Dart, painter order, clean-tree type или
> Material render path.
>
> Право менять render появляется только в E3 после pixel oracle proof.

```
```
