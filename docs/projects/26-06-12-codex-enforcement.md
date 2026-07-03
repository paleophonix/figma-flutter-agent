# ТЗ: Энфорсмент Project Bible — гейты на отклонения

> Версия 1.0, 2026-06-12. Источник: аудит кодовой базы против `.cursor/rules/project-bible.mdc`.
> Все нарушения верифицированы по живому коду `main`; счётчики приведены на момент аудита.
>
> **СТАТУС: РЕАЛИЗОВАНО И ПРИНЯТО (2026-06-12).** Все пять WP закрыты до публикации ТЗ
> (параллельная разработка). Реализация: общий fingerprint-модуль `scripts/lint_baseline.py`
> (WP-3); гейты `lint_settings_purity.py` (5 fp), `lint_hardcoded_colors.py` (30 fp),
> `lint_regex_dart_surgery.py` (35 fp), `semantics_legacy_burndown.py` (242 fp, зоны
> interaction/flex_policy/emit/other — WP-1), `lint_dart_in_python.py` (fingerprint+legacy
> count). Все проведены в `signoff.{ps1,sh}` с `$ErrorActionPreference=Stop` +
> `if LASTEXITCODE -ne 0 { exit }`. Ratchet верифицирован: инъекция нарушения → exit 1 (в т.ч.
> с `--write-burndown`), заморозка → exit 0. Остаток: `lint_dart_in_python` ещё гибрид
> (count для legacy-зоны + fingerprint для clean) — WP-3.1 хотел чистый fingerprint, не критично.

## 1. Диагноз

Ядро анти-патчинга соблюдается (0 условий на `figmaId` / `screen_id` / текст-значение,
0 viewport-магии в `generator/`, 0 non-UTF-8 Dart I/O). Но **правила кодекса опережают
энфорсмент**: пять кодифицированных запретов нарушены и при этом **не покрыты ни одним
автоматическим гейтом**, поэтому отклонения растут молча (baseline сниффинга вырос 104→105
за одну сессию).

Это нарушает дух §3.2 «know which rails are real»: правило, не подкреплённое гейтом, —
это пожелание, а не safety rail.

### 1.1. Матрица покрытия (правило → гейт)

| Правило Bible | Нарушений (верифиц.) | Текущий гейт | Требуется |
|---|---|---|---|
| §13.3 archetype-предикаты в эмите | **247 вызовов** в `generator/layout/widgets/emit/` | `semantics_legacy_burndown` покрывает только `parser/interaction` | расширить scope + паттерны |
| §6 settings purity | **5** `load_settings()` в `generator/ir/` | нет | новый lint |
| §13.1 анонимные цвета в эмите | **~10** `Color(0x…)` в `generator/layout/widgets/` | нет | новый lint + allowlist |
| §13.2 regex-хирургия Dart | 4 сайта (`positioned.py` и др.) | нет | новый lint + sanctioned-allowlist |
| §13.4 fingerprint-baseline | baseline = голый count (`105`) | count-ratchet (swap-уязвим) | конверсия в fingerprints |

### 1.2. Принцип

**Gate-first, then burn-down.** Сначала заморозить рост каждого класса нарушений гейтом
(CI краснеет на новое нарушение), затем сжигать накопленный долг волнами. Фактический
burn-down §13.3 — это E5 Phase 3 (отдельный эпик); настоящее ТЗ — про **энфорсмент**, не
про переписывание легаси.

---

## WP-1 — Heuristic burn-down gate (§13.3)

**Цель:** заморозить 247 archetype-предикатов в продакшн-эмите и сделать рост невозможным.

**Контекст:** `scripts/semantics_legacy_burndown.py` уже считает `looks_like_*` + lexicon +
string-sniff в `parser/interaction` и форсит монотонность через baseline. Scope узкий —
`generator/layout` (где живут `row_is_*`/`stack_is_*`/`column_is_*`/`hosts_*`) не покрыт.

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| WP-1.1 | Расширить scope скана с `parser/interaction` на `generator/layout/**` | `scripts/semantics_legacy_burndown.py` | Скан видит `emit/`, `flex_policy/`, `widgets/` |
| WP-1.2 | Расширить `_PREDICATE_RE` на `row_is_*`/`stack_is_*`/`column_is_*`/`hosts_*`/`is_compact_*`/`is_centered_*` (вызовы, не только def) | там же | Счётчик ловит 247 текущих вызовов |
| WP-1.3 | Зафиксировать baseline на текущем числе; CI падает на **росте** | baseline JSON | `monotonic_ok=false` при +1 предикат |
| WP-1.4 | Вынести метрику в signoff-отчёт (`logs/semantics/legacy_burndown.json`) с разбивкой по зонам | `scripts/signoff.ps1:37` | Отчёт показывает `interaction` + `layout` отдельно |

**DoD WP-1:** baseline заморожен; добавление любого нового `row_is_*`/`looks_like_*`-вызова в
`generator/layout` или `parser/interaction` = красный CI; счётчик монотонно не растёт.

---

## WP-2 — Settings purity gate (§6/§15)

**Цель:** запретить `load_settings()` внутри компилятора (replay-детерминизм), сделать
видимыми текущие 5 нарушений.

**Верифицированные сайты:** `generator/ir/presence/sanitize.py:265`,
`generator/ir/expression.py:53` и `:107`, `generator/ir/materialize.py:108`,
`generator/ir/passes/semantic.py:17`.

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| WP-2.1 | Lint: запрет `load_settings()` в `src/figma_flutter_agent/generator/**` и `parser/**` вне allowlist | новый `scripts/lint_settings_purity.py` | Скан печатает 5 текущих сайтов как violations |
| WP-2.2 | Grandfather-baseline (как §13.4 — fingerprints), CI падает на **новом** сайте | baseline | Новый `load_settings()` в компиляторе = красный |
| WP-2.3 | Подключить в signoff | `scripts/signoff.{ps1,sh}` | Гейт в цепочке |

**DoD WP-2:** 5 текущих сайтов в baseline как debt; новый вызов блокирует PR; burn-down
сжигается в E2.6 (Settings Context Purity).

---

## WP-3 — Fingerprint baselines (§13.4)

**Цель:** заменить swap-уязвимые count-ratchet на fingerprint-baseline во всех burn-down
гейтах. Сейчас `tests/fixtures/lint/dart_sniff_baseline.json` = `{"layout_widgets_count": 105}`
— удаление 10 + добавление 10 нарушений оставит счётчик, CI промолчит.

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| WP-3.1 | Формат baseline: список stable fingerprints `path \| normalized_snippet_hash \| category` вместо int | `scripts/lint_dart_in_python.py`, `semantics_legacy_burndown.py` | Baseline хранит fingerprints |
| WP-3.2 | CI падает на: новый fingerprint; рост total; violation вне allowlist; переезд legacy-violation в новый модуль | lint scripts | Тест на каждое условие |
| WP-3.3 | Исчезновение fingerprint → burn-down report (зелёный) | lint | Удаление долга не краснит, фиксируется как прогресс |
| WP-3.4 | Создать недостающий `tests/fixtures/lint/emitter_baseline.txt` (на него ссылается план E3.4, файл отсутствует) | `tests/fixtures/lint/` | Файл существует, в формате WP-3.1 |

**DoD WP-3:** все burn-down baselines на fingerprints; swap долга вбок ловится; план-ссылка на
`tests/fixtures/lint/emitter_baseline.txt` перестаёт быть битой.

---

## WP-4 — Hardcoded color gate (§13.1)

**Цель:** запретить анонимные `Color(0x…)` в генерируемой логике; цвета должны приходить из
токенов/стиля Figma.

**Верифицированные сайты:** `generator/layout/widgets/selection.py:32` (`0xFF28A745`),
`input/icons.py:24/53`, `stepper.py:175`, `thumbnail.py` и др. (~10).

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| WP-4.1 | Lint: запрет литералов `Color(0x…)` в строках-эмитах `generator/layout/**` | новый lint или расширение `lint_dart_in_python` | Текущие ~10 сайтов как violations |
| WP-4.2 | Allowlist: `0x00000000` (transparent), чистый white/black для системных оверлеев — **с явным комментарием-обоснованием** | allowlist-конфиг | Доменные цвета (`0xFF28A745`, `0xFF71717A`) не в allowlist |
| WP-4.3 | Fingerprint-baseline на остаток | baseline | Новый анонимный цвет = красный |

**DoD WP-4:** доменные хардкод-цвета заморожены; новый анонимный цвет в эмите блокирует PR;
burn-down при переводе на токены.

---

## WP-5 — Regex-Dart-surgery gate (§13.2)

**Цель:** запретить мутацию Dart через regex+срез вне санкционированного пути (AST sidecar
или typed syntax repair с тестами).

**Верифицированные сайты:** `generator/dart/llm_codegen/positioned.py:88-98`
(`re.search(r"child:")` + `block[:pos]+insert+block[pos:]`), `text_richtext.py:96`,
`layout_extract.py:45`, `layout_strip.py:67`.

| # | Задача | Файлы | Критерий приёмки |
|---|--------|-------|------------------|
| WP-5.1 | Lint: паттерн `re.(sub\|search)` рядом со срезом строки по Dart-форме (`child:`, `Positioned`, `SizedBox`, `Container`) в `generator/dart/**` | lint | Текущие 4 сайта как violations |
| WP-5.2 | Allowlist: модули с пометкой «sanctioned typed syntax repair» + обязательный тест-файл | allowlist | Сайты без теста — красный |
| WP-5.3 | Fingerprint-baseline на остаток; миграция в AST sidecar — burn-down | baseline | Новая regex-хирургия = красный |

**DoD WP-5:** regex-хирургия Dart заморожена; новая блокируется; легаси-сайты помечены debt с
тестами либо мигрируют в sidecar.

---

## 2. Сводный DoD

- Все пять классов нарушений имеют гейт в `scripts/signoff.{ps1,sh}`.
- Каждый baseline — fingerprint-формат (WP-3), не count.
- CI краснеет на **любое новое** нарушение любого из пяти классов.
- Все burn-down счётчики монотонно не растут; их снижение видно в signoff-отчётах.
- Матрица §1.1 закрыта: каждое правило §13.x/§6 → активный гейт.

## 3. Последовательность

```
WP-3 (fingerprint-инфраструктура — фундамент для всех baseline)
  → WP-1 (heuristic gate, самый высокий leverage: замораживает 247)
  → WP-2 (settings gate, 5 сайтов, готовит E2.6)
  → WP-4 (color gate)
  → WP-5 (regex-Dart gate)
```

WP-3 первым: остальные WP переиспользуют fingerprint-механику. WP-1 — следующий по leverage.

## 4. Вне scope

- **Фактический burn-down §13.3** (удаление 247 предикатов) — это E5 Phase 3, отдельный эпик.
  Настоящее ТЗ только **замораживает** рост и делает долг измеримым.
- **Сжигание `load_settings()`** — E2.6 (Settings Context Purity). ТЗ ставит гейт, E2.6 чистит.
- Перевод хардкод-цветов на токены — попутно в соответствующих волнах E5.

## 5. Замечание

Линтер при последнем редактировании `project-bible.mdc` отнормализовал часть путей `.figma_debug/`
→ `.debug/` в §5.1 (строки ~397-401), создав рассинхрон с остальным документом. Если ребрендинг
каталога не намеренный — поправить в рамках этого же PR (тривиально).
