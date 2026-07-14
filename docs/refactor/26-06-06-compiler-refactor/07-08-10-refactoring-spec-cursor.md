# Техническое задание на рефакторинг

## Programs 07, 08 и 10: decorative fidelity, property testing, artifact identity

**Версия:** 1.3 — consilium final  
**Дата:** 3 июля 2026 года  
**Статус:** утверждено к поинкрементной реализации  
**Milestone:** M4  
**Аудитория:** разработчик, coding agent, reviewer, владелец продукта

**Источники:**

- `07_decorative-primitive-fidelity.md`
- `08_property-based-testing.md`
- `10_provenance-cache-determinism.md`
- `contracts/PIPELINE_ARROWS.md`
- Program 02 conservation registry
- Programs 03–06 compiler contracts
- результаты консилиума и проверки живого кода

**Вне scope:**

- Program 09;
- hierarchical visual oracle;
- visual refine;
- автоматический поиск исправлений по pixel diff;
- screen-, feature-, asset filename- и `figmaId`-specific patches.

---

# 1. Цель

Programs 07, 08 и 10 являются тремя слоями одной системы:

```text
Program 10 — можно ли доверять артефакту и конкретному запуску?
Program 08 — сохраняются ли законы компилятора на множестве входов?
Program 07 — получает ли пользователь корректный визуальный примитив?
```

| Program | Действие | Результат |
|---|---|---|
| **10 — harden** | Идентичность артефактов, lifecycle запуска и cache compatibility | Старый, несовместимый или незавершённый артефакт не считается актуальным |
| **08 — build** | Synthetic/property/metamorphic test layer | Нарушения compiler laws находятся автоматически и сводятся к минимальному примеру |
| **07 — unify** | Формальная модель `substrate ⊕ glyph ⊕ stroke ⊕ badge` | Иконки, checkbox, badges и navigation primitives перестают зависеть от локальных compensators |

Сквозной тезис:

```text
10 обеспечивает доверие к доказательству.
08 масштабирует доказательство.
07 применяет доказанные законы к пользовательской fidelity.
```

---

# 2. Подтверждённый baseline

## 2.1 Program 10

Текущий `screen_ir_cache_fingerprint()` содержит:

- `cleanTreeHash`;
- root Figma ID;
- root type;
- root width;
- root height.

В fingerprint отсутствуют parser version, IR schema version и generation-config fingerprint.

В проекте существует `PARSER_VERSION` и `EMITTER_VERSION`, но отдельного `IR_SCHEMA_VERSION` пока нет: `generator/ir/version.py` содержит только `EMITTER_VERSION`.

Следовательно, `10-P0-1a` обязан не только использовать `irSchemaVersion`, но и создать для него единый источник правды и правила повышения версии.

Debug pipeline уже использует:

```text
raw.json
processed.json
pre_emit.json
plan.dart
screen.dart
llm_parsed.json
llm_validated.json
snapshot.json
provenance.json
run.meta.json
```

Основные debug artifacts документированы в `.debug/screen/<project>/<feature>/`.

`run.meta.json` уже является живым артефактом. Его текущая модель содержит:

- `pipeline_run_id`;
- `candidate_build_run_id`;
- `committed_build_run_id`;
- writeback outcome;
- written files;
- analyze result.

Reader уже поддерживает fallback старых полей. Поэтому Program 10 должен **расширить и мигрировать** существующую schema, а не создавать второй writer или новый конфликтующий формат.

Planner timing сейчас является телеметрией: start фиксируется перед синхронным вызовом, а завершение — после возврата функции. Такой механизм не способен прервать зависшую синхронную стадию.

## 2.2 Program 08

`LAW-CP1-TYPE-TRUTH` уже принадлежит Program 02 и зарегистрирован как blocking conservation law. Program 08 не создаёт новый law, а закрывает его тестовое доказательство.

Отдельного полного тестового набора для positive, negative и permitted mutation semantics пока нет.

В проекте присутствуют:

- hand-built `CleanDesignTreeNode` fixtures;
- conservation harness;
- geometry metamorphic tests;
- real-screen corpus;
- golden tests.

Отсутствуют:

- единый `tests/synthetic/`;
- recursive strategies;
- formal transform protocol;
- replayable failure artifacts;
- shrinking pipeline;
- property-specific CI markers.

`pyproject.toml` сейчас регистрирует шесть pytest markers, но `property_fast` и `property_nightly` среди них отсутствуют.

## 2.3 Program 07

Render-boundary collapse сохраняет IDs потомков в `flatten_figma_node_ids`, но удаляет `children`. Это сохраняет identity multiset, но способно уничтожить сведения о ролях `substrate`, `glyph`, `stroke` и `badge`.

Asset exporter получает готовый SVG от Figma, проверяет его валидность, filters и path count. Отсутствие прямого чтения parsed stroke facts ещё не доказывает потерю stroke: stroke может быть встроен в SVG или преобразован в fill. Поэтому первым шагом должен быть survival audit, а не неподтверждённый production fix.

---

# 3. Scope

## 3.1 In scope

### Program 10

- создание `IR_SCHEMA_VERSION`;
- IR-cache identity stamps;
- generation-config fingerprint;
- cache compatibility verdicts;
- миграция существующего `run.meta.json`;
- artifact identity contract;
- dump content identity;
- soft stage budgets;
- архитектура hard deadlines;
- canonical pre-emit determinism;
- stale artifact diagnostics.

### Program 08

- test closure для `LAW-CP1-TYPE-TRUTH`;
- deterministic clean-tree builders;
- transform protocol;
- explicit transform preconditions;
- Hypothesis integration после стабилизации builders;
- conservation properties;
- metamorphic properties;
- shrinking и replay;
- corpus-seeded distributions;
- property-specific CI markers и profiles.

### Program 07

- decorative decision inventory;
- typed decorative contract;
- role-preserving render-boundary collapse;
- stroke survival audit;
- flatten/downgrade provenance;
- per-role fidelity routing;
- generic plate/glyph/stroke laws;
- controlled migration существующих special cases.

## 3.2 Out of scope

| Тема | Статус |
|---|---|
| Program 09 | Backlog |
| Visual refine | Backlog |
| Full pixel-diff search | Backlog |
| Raw Figma JSON property generator | P2 или отдельная программа |
| Full content-addressed `.debug` store | Program 10 P2 |
| Remote artifact cache | Program 10 P2 |
| Byte-identical final Dart для LLM path | Не является gate |
| Golden PNG как основной property oracle | Запрещено |
| Text rasterization внутри decorative contract | Запрещено |

---

# 4. Зависимости

## 4.1 Prerequisites

| Зависимость | Требование |
|---|---|
| Program 02 | Stable law registry и conservation runner |
| Program 03 | Semantic upgrade только через evidence/veto policy |
| Program 04 | Call-site/definition shadow proof для reusable-instance properties |
| Program 06 | Typed geometry constraints для resize metamorphic tests |

## 4.2 M2/M3 relationship

Program 10 целиком не становится новым prerequisite для M2 задним числом.

Для доверия к M2 signoff evidence необходимо одно из двух.

### Вариант A — clean full run

```text
cached_ir_used = false
source_dump_hash recorded
processed_hash recorded
pre_emit_hash recorded
run status = completed
CI run attached
```

### Вариант B — cached evidence

Cached IR прошёл Program 10 compatibility gate.

Таким образом:

```text
Program 10 целиком ≠ prerequisite M2.
Fresh clean-run proof или совместимый cache = prerequisite доверия к evidence.
```

До закрытия M2:

- M3 authority остаётся выключен;
- Programs 07 и 10 работают в additive/report-only/shadow;
- blocking cache rejection включается только отдельным decision record.

---

# 5. Общие нормативные правила

1. Один increment — один PR.
2. Additive model, shadow validation и authority switch не смешиваются.
3. Каждый blocking mechanism проходит:

```text
off → report_only → shadow → enforce
```

4. `law_id` и `family_id` хранятся отдельно.
5. В документации указывается владелец law. `LAW-CP1-TYPE-TRUTH` принадлежит Program 02; Program 08 является consumer/test owner.
6. Settings читаются на pipeline boundary и передаются typed context/policy.
7. Новый generated artifact имеет canonical deterministic serialization.
8. Timestamp, absolute path, run ID и session-local directory не входят в deterministic fingerprint.
9. Новый structural bug не закрывается добавлением golden PNG.
10. Ни один production route не получает screen-specific исключение.
11. Enforce требует отдельного decision record:

```text
law_id
route или artifact kind
baseline evidence
known mismatches
fallback
rollback
owner
approval
```

---

# 6. Stable laws

## 6.1 Program 10

```text
LAW-ARTIFACT-IDENTITY-COMPLETE
LAW-ARTIFACT-REUSE-COMPATIBLE
LAW-ARTIFACT-PRODUCER-COMPLETE
LAW-ARTIFACT-UPSTREAM-CLOSED
LAW-RUN-META-SCHEMA-COMPATIBLE
LAW-RUN-LIFECYCLE-CONSISTENT
LAW-PIPELINE-STAGE-BOUNDED
LAW-PREEMIT-DETERMINISTIC
```

## 6.2 Program 08 consumers

```text
LAW-SYNTHETIC-CASE-VALID
LAW-METAMORPHIC-PRECONDITION-DECLARED
LAW-PROPERTY-FAILURE-REPLAYABLE
LAW-PROPERTY-ORACLE-DETERMINISTIC

Consumed from Program 02:
LAW-CP1-TYPE-TRUTH
```

## 6.3 Program 07

```text
LAW-DECORATIVE-ROLE-PRESERVATION
LAW-DECORATIVE-GLYPH-INTRINSIC-BOUNDS
LAW-DECORATIVE-STROKE-SURVIVAL
LAW-DECORATIVE-STROKE-SINGLE
LAW-DECORATIVE-FLATTEN-DECLARED
LAW-DECORATIVE-DOWNGRADE-PROVENANCE
```

---

# 7. Execution order

```text
1.  10-P0-1a  additive IR identity stamps
2.  08-P0-0   LAW-CP1-TYPE-TRUTH tests              [parallel]
3.  10-P0-1b  shadow compatibility verdict
4.  10-P0-2   run.meta.json schema migration + lifecycle
5.  10-P0-3   artifact_identity.md
6.  10-P0-4   soft stage budgets
7.  07-P0-0   decorative decision inventory
8.  07-P0-1   additive decorative contract
9.  07-P0-2   role-preserving collapse
10. 07-P0-3   stroke survival audit
11. 08-P0-1   deterministic synthetic builders
12. 08-P0-2   transform/replay protocol
13. 08-P0-3   first conservation properties + marker registration
14. 08-P0-4   refined rename metamorphic
15. 08-P1-1   Hypothesis strategies
16. 07-P1     controlled consumer migrations
17. 10-P1     enforce, hard deadlines, determinism
18. P2        nightly scale and burn-down
```

`08-P0-0` допускается разрабатывать параллельно с `10-P0-1a`.

---

# 8. Program 10 — Artifact identity, cache и determinism

## 8.1 10-P0-1a — additive IR identity stamps

### Цель

Добавить metadata fields при записи cached IR без изменения read behavior.

### Единый источник IR schema version

В `src/figma_flutter_agent/generator/ir/version.py` необходимо добавить:

```python
IR_SCHEMA_VERSION = "1"
```

Файл становится единственным источником:

```text
EMITTER_VERSION
IR_SCHEMA_VERSION
```

### Bump policy

`IR_SCHEMA_VERSION` повышается при несовместимом изменении:

- структуры `ScreenIr`;
- обязательных полей cached IR;
- значения или семантики существующего поля;
- identity/reference model;
- правил интерпретации cached IR reader.

Не требует повышения:

- изменение emitter без изменения IR schema;
- logging;
- debug-only поле вне canonical payload;
- изменение форматирования Dart;
- добавление optional metadata, которое старый reader безопасно игнорирует.

Bump policy фиксируется рядом с константой или в `contracts/artifact_identity.md`.

### Новые metadata fields

`screen_ir_cache_fingerprint()` и `ir_cache_metadata_for_write()` получают:

```text
irCacheFingerprintVersion
cleanTreeHash
cleanRootFigmaId
cleanRootType
cleanRootWidth
cleanRootHeight
parserVersion
irSchemaVersion
generationConfigFingerprintVersion
generationConfigHash
```

### Generation-config fingerprint

Хешируется не весь YAML, а versioned allowlist настроек, влияющих на semantic/layout output.

Пример категорий:

```text
widget extraction settings
semantic/classification settings
layout pass settings
geometry settings
fidelity settings
naming settings, если они влияют на IR identity
```

Не входят:

- logging;
- verbosity;
- UI preferences;
- output path;
- unrelated development settings.

### Allowlist artifact

Добавить:

```text
tests/fixtures/generation_config_fingerprint_allowlist.json
```

Он содержит canonical список settings paths, входящих в fingerprint.

Изменение allowlist требует:

- явного diff;
- повышения `generationConfigFingerprintVersion`, если hash surface несовместимо изменился;
- обновления ratchet test.

### DoD

- `IR_SCHEMA_VERSION` создан и имеет bump policy;
- новые IR dumps содержат stamps;
- старые dumps продолжают читаться;
- cache acceptance не меняется;
- generated Dart не меняется;
- порядок YAML keys не меняет hash;
- semantic setting change меняет hash;
- irrelevant setting change не меняет hash;
- allowlist fixture и ratchet test присутствуют.

---

## 8.2 10-P0-1b — shadow compatibility verdict

### Цель

Сравнивать current identity и cached identity, не блокируя legacy route.

### Verdict

```text
compatible
incompatible
legacy_unknown
```

### Semantics

| Условие | Verdict |
|---|---|
| Все обязательные stamps совпали | `compatible` |
| Хотя бы один обязательный stamp не совпал | `incompatible` |
| Старый artifact не содержит новых stamps | `legacy_unknown` |

### Shadow artifact path

Отчёт хранится отдельно для каждого экрана:

```text
.debug/screen/<project>/<feature>/ir-cache-compatibility-report.json
```

Repo-wide `generated/ir-cache-compatibility-report.json` не использовать: multi-screen runs не должны перезаписывать друг друга.

### Минимальная запись

```text
feature
pipeline_run_id
artifact_path
verdict
missing_fields
mismatched_fields
current_fingerprint
cached_fingerprint
legacy_reuse_result
```

### DoD

- legacy behavior остаётся authoritative;
- parser/schema/config mismatch фиксируется;
- `legacy_unknown` не маскируется как `compatible`;
- report canonical и deterministic;
- multi-screen reports не конфликтуют;
- ни один cache artifact не удаляется автоматически.

---

## 8.3 10-P0-1c — blocking cache rejection

Выполняется только после shadow period и decision record.

### Behavior

- `incompatible` → typed error;
- `legacy_unknown` → policy-controlled:
  - allow with warning;
  - reject;
  - regenerate.

### Wizard UX

Сообщение содержит:

```text
какое поле не совпало
какой artifact признан stale
какое действие обновляет IR
```

Не использовать одно общее сообщение `cache invalid`.

### Rollback

Feature mode:

```text
off
report_only
shadow
enforce
```

Legacy reader остаётся доступен для rollback.

---

## 8.4 10-P0-2 — миграция `run.meta.json` и lifecycle

### Важно

`run.meta.json` уже существует. Запрещено:

- создавать второй writer;
- вводить новый несовместимый файл с тем же именем;
- удалять старые поля;
- ломать существующий `RunMetaRecord.from_dict()`.

### Schema version

Добавить:

```text
runMetaSchemaVersion
```

### Existing fields сохраняются

```text
feature
pipeline_run_id
candidate_build_run_id
committed_build_run_id
writeback
written_files
analyze_passed
captured_at
```

### Lifecycle extension

Добавить:

```text
status
started_at
updated_at
completed_at
current_stage
source_dump_hash
processed_hash
cached_ir_used
cached_ir_verdict
pre_emit_hash
plan_bundle_hash
final_bundle_hash
failure_kind
failure_message
```

### Status

```text
started
parsed
ir_ready
planned
validated
completed
failed
timed_out
```

### Migration rules

- старый payload без `runMetaSchemaVersion` читается как legacy schema;
- существующие fallback-поля сохраняются;
- неизвестные optional поля безопасно игнорируются;
- один canonical writer обновляет весь record;
- обновление выполняется atomic replace;
- lifecycle update не должен сбрасывать writeback-поля;
- writeback update не должен сбрасывать lifecycle-поля.

### Правила запуска

- новый run сначала пишет `started`;
- каждый stage обновляет `current_stage`;
- `plan.dart` и `screen.dart` получают тот же `pipeline_run_id`;
- только `completed` считается успешным evidence;
- artifact с другим run ID считается stale относительно текущего run;
- старые artifacts не обязательно удаляются: они сохраняются для forensic analysis.

### DoD

- schema version добавлена;
- legacy records читаются;
- lifecycle и writeback объединены в одной модели;
- нет двух конкурирующих writers;
- aborted run не выглядит completed;
- success, validation failure, exception и legacy migration покрыты tests;
- metadata пишется atomically;
- ошибка записи metadata не маскирует исходный pipeline error.

---

## 8.5 10-P0-3 — `contracts/artifact_identity.md`

### Цель

Документировать identity каждого reusable artifact и реальные gaps.

### Таблица контракта

Для каждого artifact:

```text
artifact kind
producer
consumers
schema version
identity fields
upstream inputs
completion condition
current validation
missing validation
rollout mode
```

### Обязательные artifacts

- raw dump;
- processed dump;
- cached `llm_parsed`;
- cached `llm_validated`;
- pre-emit IR;
- plan Dart bundle;
- final Dart bundle;
- incremental snapshot;
- asset manifest;
- dump prefetch entry;
- `run.meta.json`.

### DoD

- таблица соответствует live code;
- предполагаемые поля отделены от реализованных;
- отсутствие поля помечено как gap;
- `run.meta.json` имеет собственную schema version и migration policy;
- provenance не включается в cache identity.

---

## 8.6 10-P0-4 — soft stage budgets

### Цель

Обнаруживать медленные завершившиеся стадии и иметь structured timing evidence.

### Typed policy

```text
StageBudgetPolicy
  soft_budget_by_stage
  mode
```

Policy создаётся на pipeline boundary.

### P0 behavior

```text
stage started
stage returned
duration calculated
duration > soft budget
→ warning
→ structured timing artifact
```

### Важно

P0 soft budget не обещает прерывание зависшей синхронной функции.

### DoD

- start log гарантирован перед stage;
- duration записывается после возврата;
- превышение soft budget имеет structured diagnostic;
- budgets задаются per-stage;
- environment metadata сохраняется;
- timeout и performance regression имеют разные codes;
- env не читается непосредственно внутри planner helper.

---

## 8.7 10-P1 — hard deadlines

Hard deadline реализуется через реальную cancellation boundary:

1. worker process;
2. cancellable external subprocess;
3. cooperative cancellation checkpoints;
4. async cancellation для действительно async operations.

Запрещено считать post-call elapsed check настоящим timeout.

### DoD

- synthetic hung worker завершается bounded failure;
- ошибка содержит stage name;
- parent pipeline освобождает ресурсы;
- partial artifact получает status `timed_out`;
- механизм работает на Windows и CI;
- rollback отключает hard deadline, сохраняя timing telemetry.

---

## 8.8 10-P1 — canonical pre-emit determinism

Нормативная граница:

```text
same validated IR
+ same parser/IR/emitter versions
+ same generation config
+ same assets identity
= same canonical pre_emit hash
```

### Canonicalization исключает

- timestamps;
- absolute paths;
- run IDs;
- nondeterministic map ordering;
- transient debug metadata.

### DoD

- два последовательных запуска минимум двух fixtures дают одинаковый hash;
- divergence показывает first differing path;
- LLM output фиксирован входным validated IR;
- final Dart byte equality не является обязательной частью gate.

---

# 9. Program 08 — Property-based и metamorphic tests

## 9.1 08-P0-0 — test closure `LAW-CP1-TYPE-TRUTH`

### Ownership

```text
Law owner: Program 02
Test/coverage consumer: Program 08
```

Не создавать второй law с новым ID.

### Тесты

1. Тип не изменился → pass.
2. Тип изменился без permit → violation.
3. Тип изменился с точным permit → pass.
4. Permit другого node ID → violation.
5. Permit другого old/new type pair → violation.
6. Удаление и повторное создание node не маскирует mutation.
7. Registry invocation вызывает тот же check.
8. Отсутствующий baseline явно классифицируется как unavailable evidence в integration layer и не выдаётся за доказанный pass.

### DoD

- создан `tests/test_type_truth_conservation.py`;
- positive, negative и permit branches покрыты;
- test вызывает law через registry;
- stable violation code проверяется;
- test входит в blocking CI.

---

## 9.2 08-P0-1 — deterministic synthetic builders

### Структура

```text
tests/synthetic/
  builders.py
  models.py
  validity.py
  canonical.py
```

### Builders

```text
node
vector
text
stack
row
column
cluster
viewport
decorative primitive
```

### Knobs

- depth;
- fanout;
- overlap;
- stack/flex mix;
- sizing modes;
- optional placement;
- reusable instances;
- decorative roles.

### Требования

- deterministic IDs;
- canonical serialization;
- explicit validity check;
- invalid case не передаётся compiler oracle;
- первая версия не требует Hypothesis.

### DoD

- минимум 100 deterministic generated trees проходят validity;
- одинаковый seed даёт одинаковое дерево;
- builder не использует filesystem, LLM и network;
- simple tree читаем в failure output.

---

## 9.3 08-P0-2 — transform и replay protocol

### Transform record

```text
transform_id
law_id
preconditions
source_seed
source_tree
transformed_tree
canonical_mapping
expected_invariant
```

### Failure artifact

```text
seed
law_id
transform_id
compiler versions
settings fingerprint
source tree
transformed tree
minimal tree
failure details
```

### DoD

- failure запускается обычным pytest по artifact;
- replay не зависит от process random state;
- artifact path deterministic;
- schema version указана;
- property runner и replay runner используют один oracle.

---

## 9.4 08-P0-3 — conservation properties и CI markers

### Properties

#### Multiset

```text
valid transform/pass
→ node identity multiset conserved
с учётом explicit omission permits
```

#### Graph sync

```text
clean tree + synchronized IR
→ все IR figmaId разрешаются в clean tree
```

#### Paint order

```text
stack children без declared reorder
→ relative paint order preserved
```

### Pytest markers

В `pyproject.toml` зарегистрировать:

```toml
"property_fast: deterministic blocking property tests for pull requests"
"property_nightly: expanded advisory property search"
```

### CI safety

Запрещён silent-green случай, когда marker не зарегистрирован или test selection пуст.

CI command должен дополнительно проверять, что найдено ненулевое количество tests, например через отдельный collection check или обязательный marker smoke test.

### DoD

- `property_fast` и `property_nightly` зарегистрированы;
- marker registration покрыта config test или CI assertion;
- `pytest -m property_fast` собирает ненулевое число tests;
- properties используют registered Program 02 laws;
- initial budget определяется benchmark;
- ориентир: 100–200 examples и менее 60 секунд;
- failure сохраняет replay artifact;
- golden capture не запускается.

---

## 9.5 08-P0-4 — refined rename metamorphic

Формулировка `rename all names/IDs → literal output equality` запрещена.

### Property A — non-evidence names

```text
rename names outside declared evidence set
→ authoritative semantic/layout decisions unchanged
```

Evidence-bearing names могут изменить candidate set, но сами по себе не должны вызывать production upgrade без обязательных evidence.

### Property B — alpha-renaming IDs

Все node IDs заменяются биективным отображением:

```text
old_id → new_id
```

Одновременно обновляются:

- parent/child references;
- IR figma IDs;
- cluster call-sites;
- asset references;
- provenance references;
- omission permits.

### Сравнивается

- canonical graph topology;
- law verdicts;
- semantic kinds;
- decorative roles;
- reusable-definition relation;
- asset family и role.

Не сравниваются буквальные filenames, содержащие ID.

### DoD

- incomplete remap признаётся invalid transform;
- non-evidence rename и alpha-ID rename являются отдельными tests;
- failure содержит remap table;
- candidate behavior отделён от authoritative behavior.

---

## 9.6 08-P1 — Hypothesis integration

Hypothesis добавляется как direct dev dependency только после стабилизации deterministic builders.

### Strategies

- recursive clean-tree;
- depth/fanout limits;
- shrink-safe invariants;
- corpus-seeded distributions;
- explicit invalid-tree filtering до compiler oracle.

### CI tiers

```text
property_fast:
  blocking
  limited examples
  deterministic profile

property_nightly:
  advisory initially
  expanded examples
  artifacts retained
```

10k examples не включаются в blocking signoff до измерения runtime и flake rate.

---

## 9.7 08-P1 — дополнительные metamorphic properties

### Duplicate instance

```text
duplicate reusable instance
→ definition identity unchanged
→ call-site count +1
```

### Independent sibling permutation

Только при precondition:

```text
no overlap
no paint-order dependency
no explicit sibling-order semantic
```

Ожидание:

```text
same semantic/layout contract
```

### Decorative resize

После Program 07 contract:

```text
resize substrate/parent
→ glyph intrinsic extent preserved
→ alignment follows declared role
→ plate/glyph relationship remains valid
```

---

# 10. Program 07 — Decorative primitive fidelity

## 10.1 07-P0-0 — decision inventory

### Цель

Найти все места, принимающие решения о plate/glyph/stroke/badge.

### Категории

```text
fact_reader
role_candidate
flatten_decider
asset_export_decider
fidelity_tier_decider
emit_decider
repair_compensator
unknown
```

### Обязательные routes

- render-boundary collapse;
- composite icon export;
- checkbox/checkmark semantics;
- icon badge stack;
- navigation substrate;
- extracted-widget paint recovery;
- raster fallback;
- SVG emit;
- Material Icon substitution;
- BoxFit selection.

### Baseline requirement

Тот же PR обязан создать initial baseline inventory.

Новый `unknown` после baseline → CI failure. Существующие baseline `unknown` не должны делать первый run постоянно красным.

### DoD

- canonical JSON inventory;
- baseline committed в том же PR;
- ratchet не допускает роста `unknown`;
- новый emit/flatten decider требует классификации;
- inventory не меняет output.

---

## 10.2 07-P0-1 — additive decorative contract

Контракт размещается только по фиксированному пути:

```text
src/figma_flutter_agent/compiler/contracts/decorative.py
```

Запрещены альтернативные пути в `schemas/` или `generator/ir/contracts/`.

Parser и generator могут импортировать нейтральный compiler contract; parser не импортирует generator.

### Модель

```text
DecorativePrimitiveFacts
  primitive_id
  substrate
  glyph
  stroke
  badge
  flatten_policy
  source
  evidence
```

### Role

```text
node_id
role
intrinsic_bounds
placement_bounds
paint_source
fidelity_requirement
```

### Flatten policy

```text
preserve_roles
source_flattened
baked_fallback
unknown
```

### DoD

- additive/report-only;
- zero emit diff;
- deterministic serialization;
- один node не получает конфликтующие roles без diagnostic;
- decorative role не повышает semantic control kind;
- facts доступны parser, asset и emit layers без обратной зависимости.

---

## 10.3 07-P0-2 — role-preserving collapse

До удаления `children` collapse stage формирует role map.

### Требование

```text
original subtree
→ decorative role facts
→ flatten descendants
→ render boundary with preserved role provenance
```

`flatten_figma_node_ids` продолжает использоваться для identity multiset, но не заменяет role map.

### DoD

- collapsed boundary содержит substrate/glyph mapping;
- unknown role явно записывается;
- source-flattened и compiler-flattened различаются;
- collapse без facts разрешён только как `unknown` в shadow;
- test доказывает сохранение roles после `children = []`;
- output не меняется на P0.

---

## 10.4 07-P0-3 — stroke survival audit

### Цель

Установить, где именно stroke теряется или преобразуется.

### Audit pipeline

```text
raw Figma stroke
→ parsed stroke fact
→ export request
→ downloaded SVG
→ optimized SVG
→ manifest
→ Flutter SVG/raster route
```

### Verdict

```text
preserved_as_stroke
preserved_as_fill
lost
rasterized
unverifiable
```

### Правила

- отсутствие XML-атрибута `stroke` не является автоматической потерей;
- визуально эквивалентное conversion-to-fill допустимо;
- `lost` требует воспроизводимого fixture;
- production exporter fix разрешён только после подтверждения loss;
- `unverifiable` получает named fidelity downgrade.

### DoD

- минимум один stroked fixture;
- raw/parser/export/optimized artifacts сравниваются;
- failing stage локализован;
- regression test фиксирует доказанный механизм;
- corpus family `stroke_lost_on_export` создаётся только при реальном loss.

### Verification additions

В baseline включаются:

```text
tests/test_svg_filter_raster_fallback.py
tests/test_asset_raster_fallback.py
```

---

## 10.5 07-P0-4 — downgrade provenance

Каждый переход:

```text
native/styled/vector
→ baked/raster/fallback
```

содержит:

```text
node_id
decorative_role
source_tier
target_tier
reason
evidence
artifact
```

Provenance не входит в cache key, но может участвовать в advisory determinism comparison.

---

## 10.6 07-P1 — controlled migrations

Одна consumer family на PR:

```text
07-P1-1 icon badge / extracted paint
07-P1-2 navigation substrate
07-P1-3 checkbox / decorative checkmark
07-P1-4 composite SVG export
07-P1-5 remaining vector routes
```

Каждый PR содержит:

- shadow comparison;
- generic law tests;
- минимум один real corpus fixture;
- output-change statement;
- rollback;
- отдельный decision record.

---

## 10.7 Generic decorative tests

Новый файл:

```text
tests/test_decorative_plate_glyph_laws.py
```

Минимум пять laws:

1. Plate preserved.
2. Glyph remains centered/aligned.
3. Glyph intrinsic bounds do not become plate bounds.
4. Stroke survives exactly once.
5. Plate color does not merge into screen background.

Дополнительно:

- badge remains overlay;
- filtered glyph may rasterize independently from native plate;
- undeclared flatten produces diagnostic.

---

# 11. Corpus families

Для закрытых механизмов используются Program 00 families:

```text
stale_ir_replay
legacy_ir_identity_unknown
run_meta_schema_mismatch
incomplete_run_artifact_reused
plan_stage_hang
type_truth_unpermitted_mutation
rename_variance
role_blind_collapse
stroke_lost_on_export
glyph_intrinsic_bounds_lost
undeclared_decorative_flatten
```

Family создаётся только при наличии:

- воспроизводимого case;
- mechanism description;
- responsible stage;
- law ID;
- regression test.

---

# 12. Verification

## 12.1 Program 10

```powershell
poetry run pytest tests/test_ir_load.py -q
poetry run pytest tests/test_dart_debug_snapshots.py -q
poetry run pytest -k "ir_cache or run_meta or run_lifecycle or pre_emit_determinism" -q
```

## 12.2 Program 08

```powershell
poetry run pytest tests/test_type_truth_conservation.py -q
poetry run pytest tests/test_conservation_harness.py -q
poetry run pytest tests/test_geometry_constraint_algebra.py -q
poetry run pytest -m property_fast -q
```

Дополнительный CI guard обязан подтвердить, что `property_fast` собрал ненулевое число tests.

## 12.3 Program 07

```powershell
poetry run pytest tests/test_decorative_plate_glyph_laws.py -q
poetry run pytest tests/test_transaction_income_emit_laws.py -q
poetry run pytest tests/test_home_bottom_navigation_emit_laws.py -q
poetry run pytest tests/test_structural_image_assets.py -q
poetry run pytest tests/test_svg_filter_raster_fallback.py tests/test_asset_raster_fallback.py -q
```

## 12.4 Milestone bundle

```powershell
poetry run ruff check .
poetry run mypy src
poetry run pytest -q
poetry run figma-flutter defects validate
```

---

# 13. PR discipline

Запрещено объединять в одном PR:

- создание `IR_SCHEMA_VERSION` и blocking cache rejection;
- additive IR stamps и shadow verdict;
- shadow compatibility и cache deletion;
- `run.meta.json` migration и hard process timeout;
- deterministic builders и Hypothesis integration;
- decorative contract и production emit migration;
- stroke audit и exporter fix без доказанного failure;
- несколько decorative consumer families;
- Program 09;
- visual refine.

Каждый PR обязан содержать:

```text
increment ID
scope
changed routes/artifact kinds
behavior/output change
tests
evidence artifact
fallback
rollback
```

---

# 14. Milestone 4 Definition of Done

## Program 10

- `IR_SCHEMA_VERSION` имеет единый источник и bump policy;
- новые cached IR имеют versioned identity;
- generation-config allowlist зафиксирован fixture и ratchet test;
- compatibility verdict различает `compatible`, `incompatible`, `legacy_unknown`;
- blocking rejection включается отдельно;
- существующий `run.meta.json` мигрирован без потери старых полей;
- `runMetaSchemaVersion` и backward-compatible reader реализованы;
- lifecycle отличает completed от aborted;
- `artifact_identity.md` соответствует live code;
- soft budgets работают;
- hard deadlines имеют реальную cancellation boundary;
- canonical pre-emit determinism проходит CI.

## Program 08

- `LAW-CP1-TYPE-TRUTH` имеет полное blocking coverage без дублирования ownership;
- `property_fast` и `property_nightly` зарегистрированы;
- CI не может дать silent green при пустой marker selection;
- synthetic builder и validity oracle стабильны;
- failure воспроизводится по artifact;
- минимум три metamorphic properties входят в blocking CI;
- один production family сведён к минимальному synthetic case;
- golden count не растёт для structural bugs.

## Program 07

- decorative contract находится в `compiler/contracts/decorative.py`;
- decision inventory имеет committed baseline;
- role map переживает render-boundary collapse;
- stroke survival доказан по всей цепочке;
- минимум пять generic decorative laws проходят;
- минимум две consumer families используют общий contract;
- corpus frequency per-screen icon fixes снижается или остаётся ratcheted.

## Общие условия

- M3 authority не включён автоматически;
- каждый enforce route имеет decision record;
- Program 09 и visual refine не попали в scope;
- нет новых screen/`figmaId`-specific patches;
- full CI и corpus validation зелёные.

---

# 15. Первый безопасный набор инкрементов

## PR-1 — `10-P0-1a`

Только:

```text
IR_SCHEMA_VERSION + bump policy
irCacheFingerprintVersion
parserVersion
irSchemaVersion
generationConfigFingerprintVersion
generationConfigHash
allowlist fixture
ratchet tests
write-path stamps
```

PR-1 не должен:

- отклонять старые dumps;
- менять wizard behavior;
- удалять cache;
- создавать shadow verdict;
- включать enforce;
- менять generated Dart.

## PR-2 — `08-P0-0`

Параллельно:

```text
LAW-CP1-TYPE-TRUTH test closure
registry path
positive/negative/permit tests
blocking CI
```

## Следующие PR

```text
PR-3: 10-P0-1b
shadow verdict + per-screen report

PR-4: 10-P0-2
run.meta.json schema migration + lifecycle

PR-5: 10-P0-3
artifact_identity.md

PR-6: 10-P0-4
soft stage budgets
```

Эти PR нельзя объединять в один.

---

# 16. Финальный статус

ТЗ v1.3 утверждено к реализации.

```text
Первый production-safe шаг:
10-P0-1a

Параллельный независимый шаг:
08-P0-0

Program 09:
backlog

Visual refine:
backlog
```

Это окончательная canonical-редакция для M4: в ней учтены A1 — источник `IR_SCHEMA_VERSION`, A2 — миграция существующего `run.meta.json`, A3 — обязательная регистрация property markers и защита от пустого CI selection.
