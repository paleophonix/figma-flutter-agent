# OpenCode / Debug / Repair — состояние проекта

**Дата:** 2026-06-19  
**Аудитория:** другие coding-агенты, consilium, product  
**Репозиторий:** `figma-flutter-agent` (Python CLI + optional control panel)

Документ фиксирует **текущее состояние** интеграции OpenCode, wizard debug, control-panel repair и **согласованный, но ещё не реализованный** дизайн 7-шагового пайплайна. Использовать как единый контекст для планирования и реализации.

---

## 1. Краткое резюме

| Область | Статус |
|---------|--------|
| Figma → Flutter compiler (основной продукт) | Production-ready CLI, LLM screen IR + deterministic emitter |
| Wizard interactive menu (`figma-flutter -i`) | Работает; пункт **debug** добавлен (phase 1) |
| Wizard **debug** → OpenCode local | **Phase 1 готов:** выбор экрана, bundle артефактов, auto `opencode serve`, session stub |
| 7-шаговый agent pipeline (recognise → summarize) | **Спроектирован, не реализован** — см. §8.0 (phases), §16 (M0–M6) |
| Control panel headless repair | **Код есть, локально выключен** (`repair.enabled: false`) |
| OpenCode submodule `src/opencode` | Инициализирован; Docker/prod использует npm `opencode-ai` |
| Sandbox/worktree для repair без правок в main `src/` | **Отдельный epic, не начат** |

---

## 2. Назначение репозитория

Python CLI **`figma-flutter`**:

- fetch Figma frame / file;
- parse → LLM screen IR (default) → validate → emit → write в **существующий** Flutter project;
- debug-артефакты в agent repo: `.debug/<project>/<feature>/`;
- optional: control panel (Discord, API, ARQ workers, Postgres) для remote generate/repair.

**Не цель:** hand-edit generated Dart под один экран; screen-specific patches запрещены doctrine (fix the law, not the screen).

Ключевые документы:

- `AGENTS.md` — agent context для Cursor/Codex
- `.cursor/rules/debug-context.mdc` — канон `.debug/` layout v9
- `.cursor/rules/project-bible.mdc` — compiler laws, anti-patching
- `README.md` — команды, wizard table

---

## 3. Архитектура основного compiler pipeline

```text
cli → pipeline → fetch → parse → llm (screen IR) → validate → planner/emitter → writer → sync snapshot
```

| Слой | Путь | Роль |
|------|------|------|
| Parse | `parser/` | Figma truth, geometry, classification |
| IR validate | `generator/ir/validate.py` | Render-safety guards до codegen |
| Emitter | `generator/ir/emitter.py`, `generator/layout/` | Deterministic Dart |
| AST sidecar | `tools/dart_ast_sidecar/` | Post-emit syntax/layout rules |
| Analyze repair | `llm/repair`, pipeline loops | In-pipeline dart analyze repair (не OpenCode) |

Default generation: **`generation.use_screen_ir: true`** в `.ai-figma-flutter.yml`; нужен API key провайдера LLM.

---

## 4. Debug artifacts (layout v9)

Экран = flat folder:

```text
<agent-repo>/.debug/<project>/<feature>/
  raw.json
  processed.json
  pre_emit.json
  plan.dart
  screen.dart
  last.log
  dart-errors.json
  semantics.json
  figma.png
  snapshot.json
  …
```

- `<project>` — имя папки Flutter-проекта (e.g. `limbo`, `ataev`)
- `<feature>` — slug из `screens.yaml`
- Активный экран: `<project_dir>/wizard-state.yml`
- Helpers: `src/figma_flutter_agent/debug/paths.py` → `screen_root(project_dir, feature)`

**Hot triage read order:** `last.log` → `dart-errors.json` → `processed.json` → `pre_emit.json` → `screen.dart` → `figma.png` → `semantics.json`

---

## 5. OpenCode — что это и где лежит

[OpenCode](https://github.com/anomalyco/opencode) — headless coding agent (TypeScript/Bun), API через `opencode serve` (default port **4096**).

| Расположение | Назначение |
|--------------|------------|
| `src/opencode/` | Git submodule (`branch: dev`), sparse checkout для local dev |
| `.opencode/` | Конфиг и agents/skills **этого** репо |
| Docker profile `repair` | `npm install -g opencode-ai@1.0.0 && opencode serve` — **не submodule** |

`.opencode/opencode.json`:

- provider: OpenRouter (`OPENROUTER_API_KEY`)
- deny: `git push`, `task`

**Submodule не обязателен** для runtime: достаточно global CLI или Docker.

---

## 6. Реализовано: Wizard debug menu (Phase 1)

### 6.1 UX

Главное меню `figma-flutter -i`, пункт **8. debug** (заменил **analyze**).

- **analyze** перенесён в submenu **check → analyze**
- **debug** использует **тот же submenu, что run:**
  - `ir-offline` — только кэш артефактов
  - `full` — regenerate live Figma
  - `offline` — regenerate из cached dump
  - `return`

Выбор экрана — **как run**, через manifest + active screen:

- `_wizard_project_dir` → `screens.yaml` → `_wizard_resolve_screen` → `_persist_active_screen`
- **Не** прямой обход `.debug/` пользователем

### 6.2 Код (Phase 1)

| Файл | Роль |
|------|------|
| `src/figma_flutter_agent/wizard/debug_agent.py` | Handler `_wizard_debug` |
| `src/figma_flutter_agent/debug/context.py` | `collect_screen_debug_context`, hot-triage file list |
| `src/figma_flutter_agent/dev/opencode/client.py` | HTTP: health, create_session |
| `src/figma_flutter_agent/dev/opencode/runtime.py` | `ensure_opencode_serve()` — probe → spawn → poll |
| `src/figma_flutter_agent/config/settings.py` | `OPENCODE_BASE_URL`, `OPENCODE_SERVER_PASSWORD` |
| `src/figma_flutter_agent/wizard/menus.py` | Menu item 8 = debug |
| `src/figma_flutter_agent/wizard/check.py` | analyze в check submenu |

### 6.3 Phase 1 outcome (что делает сейчас)

1. Режим ir-offline / full / offline (optional regenerate via `generate_screen_for_preview`)
2. `collect_screen_debug_context` — preflight (`processed.json` или `last.log` required)
3. Rich summary: screen, debug root, список файлов, log tail size
4. Auto bootstrap `opencode serve` если не отвечает
5. `create_session(title=f"debug-{feature}")` — **stub only**
6. Сообщение: «Agent prompt/skills wiring is a follow-up»

**Не делает:** шаги recognise/inspect/…, sandbox, правки кода, prompt к агенту.

### 6.4 Env для wizard debug

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENCODE_BASE_URL` | `http://127.0.0.1:4096` | OpenCode serve URL |
| `OPENCODE_SERVER_PASSWORD` | empty | Basic auth |
| `OPENROUTER_API_KEY` | — | OpenCode provider (via `.opencode/opencode.json`) |

### 6.5 Тесты (Phase 1)

- `tests/test_debug_context.py`
- `tests/test_opencode_runtime.py`
- `tests/test_wizard_debug_menu.py`

*(На момент написания — uncommitted в working tree вместе с исходниками.)*

---

## 7. Реализовано: Control panel repair (headless)

### 7.1 Статус эксплуатации

- `repair.enabled: false` в `.control-panel.yml` (локально)
- `OPENCODE_*` / `REPAIR_OPENCODE_URL` в `.env` часто не заданы
- `http://127.0.0.1:4096` обычно не слушает без ручного/Docker старта

### 7.2 Pipeline (legacy design — 11 internal stages)

`src/control_panel/repair/orchestrate.py`:

```text
PREP → CONTEXT → DIAGNOSE (5 epistemic roles parallel) → EVAL → CONSILIUM → PLAN → BUILD → GATES → REVIEW → PUBLISH
```

| Stage | OpenCode agent | Model config key |
|-------|----------------|------------------|
| CONTEXT | LLM RepairTicket (не OpenCode) | `repair.models.context` |
| DIAGNOSE ×5 | diagnose-skeptic, empiric, architect, pragmatist, devil | `repair.models.diagnose` |
| CONSILIUM | repair-consilium | `repair.models.consilium` |
| PLAN | repair-planner | `repair.models.plan` |
| BUILD | repair-build | `repair.models.build` |
| REVIEW | repair-review | `repair.models.review` |

- Worktree: `create_repair_worktree` → artifacts в `.repair/debug/<project>/<feature>/`
- Gates: ruff + pytest в worktree
- Publish: GitLab MR
- REST: `POST /v1/repair-jobs`, SSE events

Config: `.control-panel.yml` → `repair.models.*`, `opencode_base_url`, `repair.enabled`

### 7.3 OpenCode agents (текущие, `.opencode/agents/`)

**Diagnose (read-only, 5 ролей):**

- `diagnose-skeptic`, `diagnose-empiric`, `diagnose-architect`, `diagnose-pragmatist`, `diagnose-devil`

**Repair (write на build):**

- `repair-consilium`, `repair-planner`, `repair-build`, `repair-review`

Permissions: build allows ruff/pytest; deny git push.

### 7.4 OpenCode skills (текущие, `.opencode/skills/`)

| Skill | Назначение |
|-------|------------|
| `diagnose` | Read-only triage, `.repair/debug/` |
| `debug` | Control panel infra debug (не screen compiler) |
| `fix` | Control panel infra fix |

**Нет:** recognise, inspect, plan, repair, review, summarize как отдельных skills.

---

## 8. Согласованный дизайн: 7-шаговый pipeline (NOT IMPLEMENTED)

Product/architecture decision (обсуждение 2026-06-19). **Заменяет** epistemic fan-out + consilium единой линейной машиной состояний.

**Pre-implementation anchors** (consilium review 2026-06-19): §8.0 FailureClass + phase order + three truths — read **before** coding any gate.

### 8.0 FailureClass, phase order, three truths (READ FIRST)

#### Canonical phase order (no paradox)

Run Gate **reads** artifacts and runIds that **Data Refresh** produces. Gate **cannot** run before refresh.

```text
Data Refresh (Данные)
  wizard: ir-offline | full | offline
  → update .debug/<project>/<feature>/, candidate stamps, run.meta, logs
Run Gate (M0)
  → read artifacts + served_run_id_probe + capture passport
  → emit run_manifest.json, case_mode SCREEN | FORENSIC | BLOCKED
Agent pipeline
  recognise → inspect → diagnose → plan → repair
  → check → [fix → check]* → capture → review ⇄ loop → summarize
```

**Not:** `Verify → Run Gate → Данные`. **Yes:** `Data Refresh → Run Gate → Recognise`.

Wizard submenu (ir-offline/full/offline) = **Data Refresh only** — not agent steps 1–7.

#### Three truths (then judgment)

| Layer | Question | Owner |
|-------|----------|-------|
| **Run Gate** | Which build identity is truth? Fresh / rolled back / stale capture / no serve? | deterministic M0 |
| **Check** | Did compiler path compile, validate, analyze, write? | deterministic post-repair |
| **Capture** | Does verified build **look** like Figma? | deterministic visual gate |
| **Review** | Law closed? Safe to ship / loop / stop? | agent ×1 or ×5 — **only after** check + capture (SCREEN) |

```text
Run Gate  = truth of build identity / freshness
Check     = truth of compiler / write validity
Capture   = truth of visual result
Review    = judgment (never substitutes for the three gates above)
```

#### FailureClass — single enum (implementation law)

**One module, all consumers.** Do **not** fork local enums in `run_gate.py`, `check.py`, etc.

```text
src/figma_flutter_agent/dev/opencode/failure_class.py
```

| Consumer | Uses |
|----------|------|
| `run_gate.py` | Run Gate verdicts subset |
| `check.py` | post-repair classify + route |
| `capture_gate.py` | visual / stale capture |
| review routing | `REVIEW_REJECTED`, `REVIEW_STOP` |
| `summarize.py` | escalate reason codes |
| loop budgets | `same_root_hash` keys per class |

**Enum members** (canonical names — full routing table §8.10):

```python
# failure_class.py — StrEnum, single source of truth
FRESH_OK
ROLLED_BACK
STALE_CAPTURE
NO_SERVE
PATCH_CODE_EMIT
PATCH_CODE_COMPILER
PATCH_RUNTIME
PATCH_VISUAL
TOOLCHAIN_FLAKE
INFRA_HARD
REVIEW_REJECTED
REVIEW_STOP
UNKNOWN_BLOCKED
```

`classify_failure()` lives beside the enum (same package). §8.10 table remains the **routing spec**; §8.0 is the **import contract**.

Legacy alias in doc: `failure_taxonomy.py` → **rename to** `failure_class.py` at M0.

### 8.1 Шаги

| # | Step | Read/Write | Agents (prod / MVP) | Задача |
|---|------|------------|---------------------|--------|
| 1 | **recognise** | read | **×5 / ×1** | **Что** не так (symptom, UX/product); без модулей и без «почему» |
| 2 | **inspect** | read | **×1** | **Где** в системе: карта связанных сущностей — `.debug/` + **read-only repo** |
| 3 | **diagnose** | read | **×5 / ×1** | **Почему**: named law + layer; evidence + repairShape |
| 4 | **plan** | read | **×1** | Numbered implementation plan, tests |
| 5 | **repair** | write | **×1** (build mode) | Правки **только в sandbox/worktree** `src/figma_flutter_agent` |
| — | **check** | deterministic | **0** | Compiler/emit truth — §8.0 Check |
| — | **fix** (optional) | deterministic | **0** | Emit-layer llm_repair после failed **check** — §8.8 invariants |
| — | **capture** | deterministic | **0** | Visual truth — §8.0 Capture |
| 6 | **review** | read | **×5 / ×1** | **CONTINUE \| LOOP \| STOP** — после **check + capture** (SCREEN) |
| 7 | **summarize** | read | **×1** | Ticket RU + dev EN; routing §8.4.1 |

**Panel size:** `debug_pipeline.ensemble.enabled` — см. §8.5. **MVP default ×1** on recognise/diagnose/review.

**Полный runtime path** (after Data Refresh + Run Gate — §8.0):

```text
Data Refresh → Run Gate →
recognise → inspect → diagnose → plan → repair
  → check → [fix → check]*
  → capture
  → review ⇄ (loop) → summarize
```

Wizard submenu (ir-offline/full/offline) = **Data Refresh** перед Run Gate — не шаги 1–7.

### 8.2 Master prompt + step skills (согласовано 2026-06-19)

**Не** один monolith prompt на всё и **не** 14 полных копий (2 boards × 7 steps). Сборка **слоями**:

```text
prompt(step N) =
  L1 = master[board]                         # plain body → _acdp_layer("L1:PURPOSE")
  L2 = skill[step].l2-role
  L3 = repair-invariants + skill[step].l3   # shared INSIDE L3, strict order L1→L2→L3→L4→L5→L6
  L4 = skill[step].l4-capabilities
  L5 = skill[step].l5-actions
  L6 = render(l6-environment.tpl, runtime) # reasoning_chain, run_context, paths
+ JSON schema gate + output_path             # orchestrator; not in markdown bodies
```

| Layer | Count | Path |
|-------|-------|------|
| **Master** | **2** (screen, forensic) | `.opencode/prompts/repair-master-{screen,forensic}.md` (**L1 body only**) |
| **Shared invariants** | **1** | `.opencode/prompts/repair-invariants.md` — merged into **L3** via `_compose_acdp_prompt(l3_core=…, l3_principles_ext=…)` |
| **Step skill** | **7** | `.opencode/skills/<step>/` — `meta.yaml` + `l2-role.md` … `l6-environment.tpl` |
| **Reference impl** | diagnose step 3 | `.opencode/skills/diagnose/` |
| **Board fork skills** | recognise, inspect (min.) | planned: `recognise-screen`, `inspect-forensic`, … |

**Отдельный «промпт-файл на каждый шаг × board» не делаем** — дублирование. Board меняет **master + 1–2 step skills**; остальное общее.

**Deprecated (после миграции):** 5× `diagnose-*`, `repair-consilium`, monolith `repair-master.md`

### 8.3 Context model: one operative, file-backed case materials (согласовано 2026-06-19)

OpenCode — **полноценный coding agent**, не batch LLM. **Один и тот же агент** проходит 7 фаз одного «дела» (не расщепление личности на 7 ботов):

```text
recognise → inspect → diagnose → plan → repair
  → check → [fix → check]*
  → capture
  → review ⇄ (loop) → summarize
огляделся   карта       почему      план     задержал   проверка  починил?  отчёт    архив
           модулей     (law)
                                                      (determ.) (OpenCode fix)
```

**7 agent steps** + deterministic gates (**check**, **capture**) + OpenCode **fix** sub-phase (post-check, build mode). **Run Gate (§8.9)** — **after Data Refresh**, **before** recognise (§8.0).

**Метафора:** хороший оперативник **не лезет каждый раз в записную книжку** за вчерашним инсайтом — свои выводы он **держит в голове** (они в контексте). За **материалами по делу** (Figma/debug artifacts) — лезет, когда нужно доказательство.

#### Два слоя контекста

| Слой | Что это | Куда | На каждый шаг |
|------|---------|------|---------------|
| **Reasoning chain** | Structured outputs **всех** завершённых шагов `1 … N−1` | **В prompt** (compact JSON) | **Да, always — cumulative** |
| **Case materials** | Raw debug bundle: logs, JSON, png, Dart | **На диске** в worktree | **Нет в prompt** — read via tools по необходимости |

File-first касается **первички**, не **собственных мыслей** агента. `state/*.json` на диске = audit trail + recovery; **working memory = reasoning chain в prompt**.

#### Workspace layout (planned)

```text
<worktree>/
  .repair/
    manifest.json              # index case materials only (paths, hot read order)
    state/
      recognise.json             # persisted; also injected into next prompts
      inspect.json
      diagnose.json
      plan.json
      repair.json
      check.json
      fix.json                   # OpenCode fix attempts (post-check)
      fix.diff                   # optional; orchestrator git diff appendix
      capture.json               # visual gate; passport + diff
      review.json
      recognise/panel/           # 5× panelist JSON (ensemble)
      diagnose/panel/
      review/panel/
    candidate/
      planned_files/             # canonical edit root for fix phase only
      pre_emit.json              # read-only context for fix
      plan.dart                  # read-only mirror
    debug/<project>/<feature>/   # case materials (read-only for fix; mirrors regenerated)
    reports/
      summarize.json             # executive archive (both parts + routing)
      ticket_summary.md          # RU human — публикуется в тикет только при task_completed
      dev_summary.md             # подробное EN — всегда пишется
    data_context.json            # dev handoff для следующего прогона (обязателен при ¬task_completed)
  src/figma_flutter_agent/       # sandbox for repair step
```

#### Reasoning chain — cumulative (invariant)

**Каждый шаг N получает в prompt выводы ВСЕХ прошлых шагов `1 … N−1`, не только N−1.**

Orchestrator собирает **`reasoning_chain.json`** (append-only в рамках одного «дела»):

```text
step 1 recognise  → chain = { recognise }
step 2 inspect    → chain = { recognise, inspect }
step 3 diagnose   → chain = { recognise, inspect, diagnose }
…
step 6 review     → chain = { …, check, fix?, capture, review }
step 7 summarize  → chain = { …, review, summarize }
```

**Также всегда в `run_context` (с шага 1):** `run_manifest`, `case_mode`, `agent_board`, loop budgets — не теряются на шаге 5. При повторном прогоне: **`data_context`** из `.repair/data_context.json` (если prior summarize ¬completed).

Deterministic слои **входят в chain** после выполнения (compact, не raw logs):

- **`check`**, **`fix`** — перед **review** и при **diagnose.refine** / **plan.revise**

**Запрещено:** «prior step only», «read state/*.json if needed», передача только diff от предыдущего шага.

Session chat history — **вторичный кэш**; source of truth = **cumulative reasoning_chain + state/*.json on disk**.

#### Executive JSON + detail log (согласовано 2026-06-19)

Аналог чат/док: **compact handoff в chain**, **полный разбор на диске**, grep on demand.

| Слой | Файл | В cumulative chain | В prompt |
|------|------|--------------------|----------|
| **Executive** | `state/<step>.json` | ✅ append | ✅ compact slice |
| **Detail** | `state/<step>.detail.log` | ❌ | ❌ by default |
| **Human blurb** (optional) | agent chat response | ❌ | ❌ — audit only |

**Rules:**

1. **Executive JSON** — единственный обязательный handoff; schema + gates; следующий шаг **не обязан** читать detail.
2. **Detail log** — рассуждения, tool trace, длинные цитаты; grep **только** по якорям из executive (`entityId`, `lawId`, `evidence_refs`).
3. Поле, нужное для plan/repair/review — **обязано** быть в executive JSON.
4. Orchestrator может собирать detail из session transcript; agent добавляет refs в detail, не дублируя executive.

```text
.repair/state/
  diagnose.json
  diagnose.detail.log
```

#### Что идёт в prompt на шаг N

**Always in prompt:**

- Master prompt `[board]` + step skill + «шаг N/7»
- **`reasoning_chain`:** structured outputs **всех** шагов `1 … N−1` (bounded JSON)
- **`run_context`:** manifest, case_mode, budgets
- Задача шага + schema / путь для `state/<step>.json`
- Указатель на case materials: «manifest: `.repair/manifest.json`; читай `.repair/debug/…` **только чтобы подтвердить гипотезу**»

**Not in prompt (on disk, read on demand):**

- `processed.json`, `pre_emit.json`, full `last.log`, `figma.png`, …
- Sandbox sources, full gate logs (кроме краткого summary от repair/review)

Пример reasoning chain в prompt (**шаг 6 review** — видны **все** prior steps):

```json
{
  "run_context": { "case_mode": "SCREEN", "agent_board": "screen", "verdict": "FRESH_OK" },
  "recognise": { "symptoms": [{ "id": "primary_cta_misaligned", "severity": "P0" }] },
  "inspect": { "entities": [{ "id": "entity_primary_cta_emit", "repoPaths": ["…/emit/text.py"] }] },
  "diagnose": { "laws": [{ "id": "flex_cross_axis_…", "entityIds": ["entity_primary_cta_emit"] }] },
  "plan": { "steps": [{ "lawId": "flex_cross_axis_…", "targetFiles": ["…/emit/text.py"] }] },
  "repair": { "filesTouched": ["…/emit/text.py"], "gates": { "ruff": "ok", "pytest": "ok" } },
  "check": { "passed": true, "failure_class": null },
  "fix": null,
  "capture": { "passed": true, "kind": "verified", "captured_run_id": "run_123" }
}
```

Agent **не** re-read `state/*.json` с диска для prior steps — **уже в cumulative chain**. Re-read disk — **case materials** и углубление в repo paths из inspect.

#### Handoff правила

1. После шага N orchestrator пишет `state/<step>.json` **и** **append** в **`reasoning_chain`** — следующий шаг получает **весь** chain `1…N`, не slice `[N]`.
2. `manifest.json` — только внешние артефакты, не дублирует reasoning chain.
3. **summarize** — полный reasoning chain в prompt; case materials по необходимости.
4. Одна OpenCode **session** на всё «дело» (preferred); model может меняться per step.
5. Session chat history — вторичный кэш; **reasoning chain + executive JSON** — source of truth.
6. **`state/<step>.detail.log`** — optional appendix; never substitute for executive JSON in chain.

#### Anti-patterns

| Не делать | Делать |
|-----------|--------|
| Stuff 32k `last.log` в каждый step | Log в `.repair/debug/`; читать по refs |
| «Prior steps: read state/*.json if needed» | **Cumulative** reasoning_chain inline — все шаги 1…N−1 |
| 7 изолированных сессий без памяти | Один operative, растущий reasoning chain |
| Prose-only handoff / «grep the log instead of JSON» | Executive JSON required; detail = appendix only |

### 8.4 Compiler expert contract — machine-readable steps (согласовано 2026-06-19)

#### Главный риск

Сделать 7 шагов слишком **«агентскими»** (prose, vibes, markdown essays) и недостаточно **«компиляторными»** (named laws, layers, evidence, gates).

OpenCode здесь — **судебный эксперт при компиляторе**, не художник и не generic coder. Каждый step обязан писать **machine-readable JSON** (strict schema). Markdown — только **summarize** (`ticket_summary.md`, `dev_summary.md`); primary handoff = **`summarize.json`**.

**🔴 Master prompt invariant (red line):** anything the **next step** needs for gates or routing **must** live in **executive JSON** (`state/<step>.json`). Prose and `*.detail.log` are appendix only — never handoff. Schema gates **reject** steps that omit required machine fields.

#### Orchestrator gates (deterministic, между шагами)

Python orchestrator **валидирует JSON** после каждого шага (Pydantic + JSON Schema). Agent prose не является handoff.

| Gate | Rule |
|------|------|
| After **recognise** | `symptoms[]` non-empty OR `escalate: true` + reason |
| After **inspect** | `entities[]` non-empty OR `blocked: true`; each entity has `id`, `relatesToSymptoms[]` ⊆ recognise ids, `artifactRefs[]` ≥1; `repoPaths[]` ≥1 OR step `blocked` with `missing_evidence`; **no** `lawId`, `repairShape`, `targetFiles`, `action`, or fix fields; `summary` is WHERE-only (soft warn on causal markers: because, should fix, violates) |
| After **diagnose** | каждый item в `laws[]` имеет `id`, `layer`, `evidence[]` (≥1 ref), `repairShape`; каждый law ссылается на `entityId` из inspect |
| After **plan** | каждый `plan.steps[]` ссылается на `lawId` из diagnose; имеет `actionKind`; `CODE_CHANGE` имеет `tests[]` + `targetFiles`; `REPORT_ONLY` / `INFRA_RETRY` / `HUMAN_REQUIRED` **не** маршрутизируются в repair |
| Before **repair** | `diagnose.blocked === false`; `planStepOrders` только для steps с `actionKind=CODE_CHANGE` |
| After **repair** | `repair.filesTouched[]`, gate results (ruff/pytest) in JSON |
| After **check** | `check.passed`; if fail — `route`, `failureLayer`, `failure_hash` (deterministic, no LLM) |
| After **fix** | `fix.attempt`, errors before/after; then re-**check** |
| After **review** | `review.decision` ∈ `{CONTINUE, LOOP, STOP}`; if LOOP — `reason_code` + deterministic `route`; if CONTINUE — all targeted `lawCompliance[]` closed + `fix_proven` consistent with manifest |
| After **summarize** | `dev.summary` non-empty **always**; `ticket.summary` non-empty **only if** `task_completed=true`; orchestrator routes per §8.4.1 |
| **repair** forbidden | если `forbidden[]` из diagnose нарушено — fail gate без merge |

Agent **не переходит** на следующий шаг, пока JSON не прошёл schema + gate. Retry step, не «ну ладно, поняли друг друга».

#### Test regression lifecycle — select → write → run → prove (согласовано 2026-06-19)

Tests in the repair pipeline are **law regression proof**, not pixel gates. Visual truth = **capture**; compiler truth = **check**; tests prove the **named law** survives the next screen.

```text
diagnose.law id  →  plan.tests[]  →  repair writes/runs  →  review.lawCompliance evidence  →  summarize.dev mirror
```

**Not in repair loop:** full `signoff`, corpus-oracle gate, demo-signoff fixture sweep — **release/CI** gates after merge, not per repair iteration.

| Phase | Where | Who | What |
|-------|-------|-----|------|
| **Corpus link** | diagnose | agent ×N | `laws[].id` must use stable slug (registry / corpus-test linkage). `proposedLaw=true` when vocabulary is new — human may be required at STOP. |
| **Select** | plan | agent ×1 | Each actionable `plan.steps[]` **must** name `tests[]` — existing file or **new** path under `tests/`. Sources: same layer/module as `targetFiles`, repo-map `deepModules`, grep for law-adjacent fixtures (`tests/test_*<module>*`). Orchestrator gate: **no named test → plan blocked**. |
| **Generate** | repair | agent build | Add or update tests **named in plan** before or alongside compiler patch. New tests = minimal reproduction of **law**, not screen snapshot. Forbidden: golden PNG updates, fixture baseline refresh to hide failure. |
| **Run (local)** | repair | agent + orchestrator | `ruff check` on `src/` + **scoped** `pytest` on touched paths → `repair.gates.{ruff,pytest}`. OpenCode build permissions allow these commands. |
| **Run (compiler gate)** | check | orchestrator 0 LLM | Full screen pipeline after patch: parse, validate, **dart analyze** on planned Dart, write. Optional: re-run scoped pytest on sandbox `src/` if in check scope. Fail → `PATCH_CODE_COMPILER` → **repair.retry**, not diagnose. |
| **Run (visual gate)** | capture | orchestrator | Flutter render + diff vs `figma.png` — **not pytest**. |
| **Prove** | review | agent ×N | `lawCompliance[].evidence` may cite `tests/…` **only if** repair/check recorded pass. Review **does not re-run** pytest; spot-check file exists if ref is suspicious. |
| **Archive** | summarize | agent ×1 | `dev.laws[].tests`, `verification`, artifact pointers — mirror only, no new test claims. |

**Scoped pytest policy (repair + check):**

```text
default targets = plan.steps[].tests[] + sibling modules of filesTouched
fallback        = tests/ subtree matching first path segment of touched src module
never           = full pytest suite every repair pass (too slow; hides flake budget)
```

Orchestrator may call [`run_repair_gates`](src/control_panel/repair/gates.py) on worktree with `touched_paths` — **CP headless MR path**, same semantics as `repair.gates`.

**fix step:** does **not** create or run compiler tests. Only patches `.repair/candidate/planned_files/**`; unblock = **check** (dart analyze path).

**Outcomes (routing):**

| Signal | Next |
|--------|------|
| `repair.gates.pytest=fail` before check | repair retry / agent self-fix in same pass |
| check `PATCH_CODE_COMPILER` (ruff/pytest) | **repair.retry** (same plan, no re-diagnose) |
| check `PATCH_CODE_EMIT` (dart analyze) | **fix** loop → check |
| check `PATCH_VISUAL` (capture) | **diagnose.refine** — tests alone do not close visual law |
| review LOOP `lawCompliance` missing test evidence | **repair.retry** or **plan.revise** per `reason_code` |
| CONTINUE | tests cited in summarize `dev.laws[]`; ticket **omits** test paths |

**Acceptable fix rule (tests):** every closed law in review should answer *which test proves it* and *why it generalizes beyond this screen*.

#### Triad: recognise → inspect → diagnose (согласовано 2026-06-19)

**recognise ×5**, **inspect ×1**, **diagnose ×5** — см. §8.5 roster + merge rules.

Три шага — **разные вопросы**, не три названия одного копания в `.debug/`:

| Step | Вопрос | Аналогия | Read scope |
|------|--------|----------|------------|
| **recognise** | **Что** болит? | Жалоба клиента | figma/capture/semantics, ticket text |
| **inspect** | **Где** это живёт в системе? | «Кнопка съехала → вот `button.py`, emitter/text, IR node X» | `.debug/` **+ read-only** `src/figma_flutter_agent/` в worktree |
| **diagnose** | **Почему** сломалось (law)? | «Emitter не сохранил scroll host в preview branch» | Углубление в **модули из inspect** + evidence |

```text
recognise:  symptom = "primary CTA misaligned vertically"
inspect:    entities = [semantics:BUTTON@node, screen.dart:142,
             generator/layout/widgets/emit/text.py, generator/layout/style/text.py]
            (карта связей; механизм не объясняем)
diagnose:   law = flex_cross_axis_alignment_must_preserve_figma_baseline
            layer = emitter
            evidence inside text.py:…
```

**Inspect — первый шаг с repo.** Read-only обход sandbox/worktree `src/figma_flutter_agent/` по symptom anchors — не свободный grep всего репо. Связать symptom → debug artifact → repo file(s). Cartographer, not detective, not designer.

```text
recognise: ЧТО болит
inspect:   ГДЕ это живёт  (artifactRefs + repoPaths)
diagnose:  ПОЧЕМУ        (law + evidence inside module)
```

**Inspect не дублирует recognise:** recognise не называет `button.py`; inspect не говорит «потому что padding 12px», не делает visual compare (`figma.png`, capture, heatmap forbidden). `figma.json` / `raw.json` — только когда symptom указывает на fetch/parse/source geometry. Figma node ids допустимы в `artifactRefs`, не как branch key в summary.

**Diagnose не дублирует inspect:** diagnose берёт `entityId` из inspect и формулирует **named law** + **why** внутри модуля. **diagnose.refine** не перезапускает inspect unless orchestrator routes `inspect.refine`.

**FORENSIC board:** те же три вопроса, другие entities — `stages/write.py`, `run_gate`, analyze gate, capture passport — не emitter под UI.

**Skills:** `.opencode/skills/inspect-screen/`, `.opencode/skills/inspect-forensic/` — отдельные fork'и (`inspect-visual` deprecated).

**Inspect preflight (orchestrator):** `artifact_index`, `symptom_anchors[]`, `semantic_index_compact`, optional `diff_summary` — text index, not fat dump.

**Entity taxonomy:** `kind` = debug_artifact | compiler_module | pipeline_module | control_surface | toolchain_surface. One entity = one compiler/pipeline concern, not one screen region.

#### Repo navigation map (согласовано 2026-06-19)

Compact **module atlas** injected into L6 for code-aware steps — not a repo essay, not evidence.

**Source of truth (MVP):** `.opencode/context/repo-map.yaml` (curated). **Code (later):** `src/figma_flutter_agent/dev/opencode/repo_map.py` — load YAML, slice by step/board/symptoms/paths, validate paths exist.

**Three layers:**

| Layer | Content | When injected |
|-------|---------|---------------|
| **global** | Top-level compiler areas (parser, ir, layout, stages, debug, dev/opencode) | inspect, diagnose, plan, repair, review |
| **symptomHints** | recognise symptom id → artifactReads + repoSurfaces + roles | inspect only (+ orchestrator match on `recognise.symptoms[].id`) |
| **deepModules** | File-level role + look_when for emit/layout files | diagnose/plan/repair/review — **lazy slice** for selected `repoPaths` / `targetFiles` only |

**Not the same as inspect_preflight:** preflight = factual artifact index on disk; repo map = curated **where to look** in compiler by symptom/layer.

**Rules (all steps receiving map):**

```text
1. Repo map helps choose reads; it is not evidence.
2. Do not cite repo map as proof of root cause or law violation.
3. Output must still cite real artifactRefs/repoPaths after read.
```

| Step | Repo map |
|------|----------|
| recognise | no (vision + semantic hints only) |
| inspect | **required** — global + symptomHints |
| diagnose | global one-liner + deepModules slice for inspect.entity repoPaths |
| plan | deepModules slice for planned targetFiles + test map |
| repair | deepModules slice for assigned targetFiles |
| fix | **none** (allowedEditFiles only — anti src wander) |
| review | touched files + module one-liners |
| summarize | optional names for dev summary |

**L6 placeholders:** `{repo_map_compact_json}`, optional `{symptom_surface_hints_json}`, `{repo_map_deep_json}` (lazy).

**JSON envelope:**

```json
{
  "repoMapVersion": 1,
  "confidence": "curated",
  "stalenessPolicy": "navigation_only_not_evidence",
  "global": { "parser/": "…", "generator/layout/": "…" },
  "screenSymptomHints": { "text_duplication_and_overlap_in_form": { "artifactReads": [], "repoSurfaces": [] } },
  "forensicSurfaces": { "write": "stages/write.py", "run_gate": "dev/opencode/run_gate.py" }
}
```

**Gate (code):** orchestrator validates `repoSurfaces` / inspect `repoPaths` exist; CI test on repo-map paths.

**FORENSIC inspect:** inject `forensicSurfaces` only — no screen emitter symptomHints.

#### Role of each step (compiler-facing)

| Step | JSON job | Not allowed |
|------|----------|-------------|
| recognise | symptoms, userVisible, severity | module paths; «потому что»; law ids |
| inspect | **`entities[]`**: symptom links, artifact refs, **repo paths**, role tags (`emitter`, `parser`, …) | named laws; repairShape; **writes**; «почему emit съехал» |
| diagnose | **named laws**, layer, evidence, repairShape, forbidden; **`entityIds[]`** | screen-specific fixes as recommendation; repo map без law |
| plan | steps bound to `lawId`, files, tests | plan без law linkage |
| repair | files changed, gates, diff stats | edits outside sandbox / hand-edit generated Dart |
| review | **`decision`**: continue / loop / stop; lawCompliance; regression; cross-check `change_proof` | «LGTM» без `decision`; continue при `fix_proven=false` |
| summarize | **`task_completed`**, `ticket` (RU md), `dev` (EN md + structured); routing flags | ticket text при STOP/LOOP; dev summary без law ids |

#### Example: `inspect.json` (entity map — no «why»)

```json
{
  "step": "inspect",
  "agent_board": "screen",
  "entities": [
    {
      "id": "entity_primary_cta_emit",
      "relatesToSymptoms": ["primary_cta_misaligned"],
      "kind": "compiler_module",
      "role": "emitter",
      "repoPaths": [
        "src/figma_flutter_agent/generator/layout/widgets/emit/text.py",
        "src/figma_flutter_agent/generator/layout/style/text.py"
      ],
      "artifactRefs": [
        ".repair/debug/demo_app/sign_in/semantics.json:BUTTON.primary",
        ".repair/debug/demo_app/sign_in/screen.dart:142",
        ".repair/debug/demo_app/sign_in/processed.json:/children/3:5131"
      ],
      "summary": "Primary CTA text emit + style surfaces; shell anchor at screen.dart:142",
      "confidence": "medium"
    }
  ],
  "blocked": false,
  "notes": ""
}
```

#### Example: `diagnose.json` (canonical shape)

```json
{
  "step": "diagnose",
  "blocked": false,
  "escalate": false,
  "laws": [
    {
      "id": "preview_branch_must_preserve_scroll_contract",
      "priority": "P0",
      "layer": "generated shell",
      "entityIds": ["entity_preview_shell_emit"],
      "evidence": [
        ".repair/debug/ataev/order_details/screen.dart:36",
        ".repair/debug/ataev/order_details/responsiveness_report.json"
      ],
      "repairShape": "interactive preview uses same scroll host as fallback",
      "forbidden": ["screen-specific padding", "generated Dart hand edit"]
    }
  ],
  "notes": ""
}
```

Field semantics (`diagnose.laws[]`):

- **`id`** — stable law slug (registry / corpus-test linkage), not free text
- **`layer`** — compiler layer taxonomy: `parser`, `ir`, `emitter`, `planned reconcile`, `generated shell`, …
- **`entityIds`** — links to `inspect.entities[]`
- **`evidence`** — paths under worktree (prefer `.repair/debug/…`); line suffix optional
- **`repairShape`** — universal fix intent, not coordinates for one screen
- **`forbidden`** — explicit anti-patterns for plan/repair gates
- **`blocked`** — true → skip repair, jump to summarize with escalate flag

Evidence paths in JSON use **worktree-relative** paths (orchestrator rewrites from manifest).

#### Example: `plan.json` (implementation plan — read-only step)

```json
{
  "step": "plan",
  "blocked": false,
  "steps": [
    {
      "order": 1,
      "lawId": "preview_branch_must_preserve_scroll_contract",
      "entityIds": ["entity_preview_shell_emit"],
      "actionKind": "CODE_CHANGE",
      "repairClass": "EMITTER_LAW",
      "targetFiles": [
        "src/figma_flutter_agent/generator/layout/widgets/emit/text.py"
      ],
      "action": "Unify scroll host selection between preview and fallback branches",
      "tests": ["tests/test_preview_scroll_host.py"],
      "risk": "medium"
    }
  ],
  "notes": ""
}
```

`actionKind` routing:

| actionKind | Routes to repair | Typical FORENSIC use |
|------------|------------------|----------------------|
| **CODE_CHANGE** | yes | pipeline/compiler patch |
| **REPORT_ONLY** | no | stale capture / rollback truth documented |
| **INFRA_RETRY** | no | deterministic re-capture / re-check |
| **HUMAN_REQUIRED** | no | proposedLaw / policy needs human |

`repairClass` is mapped from `diagnose.laws[].repairShape` at plan time.

#### Example: `repair.json` (write step — **build mode only**)

```json
{
  "step": "repair",
  "blocked": false,
  "filesTouched": [
    "src/figma_flutter_agent/generator/layout/widgets/emit/text.py",
    "tests/test_preview_scroll_host.py"
  ],
  "planStepOrders": [1],
  "gates": {
    "ruff": "ok",
    "pytest": "ok"
  },
  "diffStat": { "files": 2, "additions": 28, "deletions": 6 },
  "notes": ""
}
```

Field semantics (`repair`):

- **`filesTouched`** — paths under sandbox worktree only
- **`planStepOrders`** — which `plan.steps[].order` were implemented
- **`gates`** — ruff/pytest on touched scope (agent runs in build mode)
- **`diffStat`** — for review / change_proof cross-check

#### Review — evidence judge (согласовано 2026-06-19; closure doctrine 2026-06-19)

**Review — не второй recognise и не pixel-police.** Это **read-only closure judge** после repair, check, optional fix, capture.

```text
Review judges closure of the case, not perfection of the screenshot.
Strict on proof. Calm on residuals. Brutal on shortcuts. Bounded on loops.

Do not approve without proof.
Do not loop without a named blocker.
```

**Две независимые рубрики:**

| Rubric | Question |
|--------|----------|
| **Law closure** | Закрыты ли named laws, ради которых был repair? |
| **Product blocker** | Остался ли verified blocking symptom (P0/P1), который нельзя честно отдать? |

Не «красиво/некрасиво», не «diff красный», не повторный vision pass.

**×5 panel** (§8.5): `CONTINUE | LOOP | STOP`; merge **CONTINUE ≥4/5** + hard gates.

Orchestrator **не** идёт в review после **check** alone. **SCREEN:** check + capture (verified) first. Summarize only after **`review.decision=CONTINUE`** or **STOP**.

##### CONTINUE formula

```text
CONTINUE =
  check.passed
  + SCREEN: capture.kind=verified AND capture.passed (or capture.skipped by config)
  + every targeted law: lawCompliance.status=closed with evidence
  + change_proof_ok AND fix_proven consistent
  + scope_ok (repair ⊆ plan)
  + no forbidden shortcut
  + no required P0/P1 blocker in symptomClosure
```

Forbidden:

```text
CONTINUE because "looks mostly okay"
CONTINUE from green tests alone / visual improvement alone / repair prose alone
```

##### LOOP formula

Only with **one** `reason_code` + **one** `route`. Named blockers only:

```text
LAW_NOT_CLOSED
CAPTURE_GATE_FAILED
SYMPTOM_STILL_P0
REGRESSION_INTRODUCED
CHANGE_PROOF_MISMATCH
FORBIDDEN_SHORTCUT_USED
SCOPE_DRIFT
TEST_COVERAGE_MISSING
WRONG_LAYER_FIXED
FIX_PROVEN_FALSE
```

Forbidden LOOP:

```text
LOOP because "residual pixel diff" when capture.passed=true and no open law/P0 symptom
LOOP for P2/P3 polish when laws closed
LOOP for new symptoms not in recognise
```

`RESIDUAL_NON_BLOCKING` → `regression_risks[]` on CONTINUE, **not** LOOP.

##### STOP formula

```text
LOOP_BUDGET_EXHAUSTED
PROPOSED_LAW_NEEDS_HUMAN
EVIDENCE_CONFLICT
INFRA_BLOCKED
(same_root_hash repeat without improvement)
```

##### Anti-pixel-police (L3)

```text
Residual visual difference is not a LOOP reason by itself.
LOOP for visual output only if capture failed, required P0/P1 symptom open, or named law open.
```

Review reads **capture_verdict** summary (passed, changedRatio, threshold, mismatchKind) — **not** figma.png/heatmap as primary judge.

##### Anti-LGTM (L3)

Every closed law needs `lawCompliance[]` with evidence (test path, capture.json:/passed, artifact ref). No evidence → not closed.

##### L6 inputs (no vision re-analysis)

```json
{
  "capture_verdict": {
    "passed": false,
    "kind": "verified",
    "changedRatio": 0.13,
    "threshold": 0.05,
    "mismatchKind": "global_plus_form_region",
    "largestRegions": ["header", "form", "cta"]
  },
  "symptom_law_matrix": [
    {
      "symptomId": "global_vertical_and_typographic_misalignment",
      "severity": "P0",
      "lawIds": ["…"],
      "requiredForContinue": true
    }
  ],
  "review_rubric": { "continueRequires": ["…"], "forbiddenLoopTriggers": ["residual diff alone"] },
  "loop_budget": { "diagnose_refine_count": 1, "max_diagnose_refinements": 2 }
}
```

##### reason_code enum + routes

| reason_code | Typical route |
|-------------|---------------|
| **REVIEW_OK** | summarize |
| **LAW_NOT_CLOSED** | diagnose.refine / plan.revise |
| **CAPTURE_GATE_FAILED** | diagnose.refine |
| **SYMPTOM_STILL_P0** | diagnose.refine |
| **REGRESSION_INTRODUCED** | repair.retry / fix (by failure_class) |
| **CHANGE_PROOF_MISMATCH** | repair.retry / forensic |
| **FORBIDDEN_SHORTCUT_USED** | plan.revise / STOP |
| **SCOPE_DRIFT** | repair.retry / STOP |
| **TEST_COVERAGE_MISSING** | repair.retry (tests) |
| **WRONG_LAYER_FIXED** | plan.revise |
| **FIX_PROVEN_FALSE** | forensic / repair.retry |
| **PROPOSED_LAW_NEEDS_HUMAN** | STOP |
| **LOOP_BUDGET_EXHAUSTED** | STOP |
| **EVIDENCE_CONFLICT** | STOP |
| **INFRA_BLOCKED** | STOP |
| **RESIDUAL_NON_BLOCKING** | (CONTINUE only) regression_risks |

##### review.json shape (extended)

Required: `decision`, `reason_code`, `route`, `lawCompliance[]`, `symptomClosure[]`, `change_proof_ok`, `scope_ok`, `forbidden_shortcuts_found[]`, `regression_risks[]` (with `blocking: false` for residuals), `task_completed_recommendation` (agent; orchestrator owns `task_completed`).

##### Orchestrator hard overrides

```text
CONTINUE but check.passed=false → coerce LOOP/STOP
CONTINUE but SCREEN capture not verified/passed → coerce LOOP
CONTINUE but change_proof_ok=false → coerce LOOP
CONTINUE but any targeted law not closed → coerce LOOP
LOOP but budget exhausted → coerce STOP
LOOP reason=residual pixels only while capture.passed=true → coerce CONTINUE + regression_risks OR rewrite reason
CONTINUE on FORENSIC for product screen ticket → invalid; forensic_completed separate from SCREEN task_completed
```

##### FORENSIC review

```text
FORENSIC review judges pipeline truth, not UI fidelity.
forensic_completed may be true while SCREEN task_completed=false until reroute + verified capture.
```

##### Canonical example: `limbo/login_version_1` (anti-LGTM)

`capture.png` alone looks acceptable; **capture_verdict** fails: `changedRatio≈0.13`, `threshold≈0.05`, global mismatch. Correct review:

```json
{
  "decision": "LOOP",
  "reason_code": "CAPTURE_GATE_FAILED",
  "route": "diagnose.refine",
  "task_completed_recommendation": false
}
```

Not CONTINUE («looks mostly okay»). Not LOOP for «one pixel» — **named capture gate failure**.

##### Legacy examples (short)

| `decision` | Meaning | Orchestrator |
|------------|---------|--------------|
| **CONTINUE** | Case contract closed | → **summarize** |
| **LOOP** | Named blocker + budget | → route by `reason_code` |
| **STOP** | Human required | → **summarize** escalate |

Inputs: reasoning chain, check, fix, capture **verdict summaries**, symptom_law_matrix, change_proof — not vision bundle.

#### Example: `review.json` (LOOP — capture gate)

```json
{
  "step": "review",
  "decision": "LOOP",
  "reason_code": "CAPTURE_GATE_FAILED",
  "route": "diagnose.refine",
  "task_completed_recommendation": false,
  "lawCompliance": [
    {
      "lawId": "preview_branch_must_preserve_scroll_contract",
      "status": "partial",
      "evidence": [".repair/state/capture.json:/passed=false"],
      "notes": "Capture ratio exceeds threshold in regions linked to P0 symptom."
    }
  ],
  "symptomClosure": [
    {
      "symptomId": "global_vertical_and_typographic_misalignment",
      "status": "open",
      "lawIds": ["preview_branch_must_preserve_scroll_contract"],
      "evidence": [".repair/state/capture.json:/largestRegions"]
    }
  ],
  "change_proof_ok": true,
  "scope_ok": true,
  "forbidden_shortcuts_found": [],
  "regression_risks": [],
  "notes": ""
}
```

#### Example: `review.json` (CONTINUE)

```json
{
  "step": "review",
  "decision": "CONTINUE",
  "reason_code": "REVIEW_OK",
  "route": "summarize",
  "task_completed_recommendation": true,
  "lawCompliance": [
    {
      "lawId": "preview_branch_must_preserve_scroll_contract",
      "status": "closed",
      "evidence": [
        "tests/test_preview_scroll_host.py",
        ".repair/state/capture.json:/passed"
      ],
      "notes": ""
    }
  ],
  "symptomClosure": [
    {
      "symptomId": "primary_cta_misaligned",
      "status": "addressed",
      "lawIds": ["preview_branch_must_preserve_scroll_contract"],
      "evidence": [".repair/state/capture.json:/passed"]
    }
  ],
  "change_proof_ok": true,
  "scope_ok": true,
  "forbidden_shortcuts_found": [],
  "regression_risks": [
    {
      "risk": "Minor residual footer diff below capture threshold",
      "blocking": false
    }
  ],
  "notes": ""
}
```

**Hard gates (orchestrator overrides agent):** see Review — evidence judge section above.

#### Schema location (planned)

```text
src/figma_flutter_agent/dev/opencode/schemas/
  recognise.schema.json
  inspect.schema.json
  diagnose.schema.json
  plan.schema.json
  repair.schema.json
  review.schema.json
  summarize.schema.json
```

OpenCode step prompt includes: «Output **only** JSON matching schema X; write to `.repair/state/<step>.json`».

Master prompt reinforces: **fix the law, not the screen**; law ids must exist in project corpus or be flagged `proposedLaw: true` for human review.

#### Step 7: summarize — archivist & handoff (согласовано 2026-06-19; closure doctrine 2026-06-19)

```text
review = decides
summarize = translates + archives + routes
```

**Summarize — не судья, а секретарь суда.** Скучный, честный, полезный для следующего шага. **Не пересматривает** — архивирует verdict review без искажения.

```text
Mirror review closure; do not re-judge.
Translate, archive, and route. Do not litigate.

No new judgment. No fake success. No product noise. No lost engineering context.
```

##### Forbidden (no re-litigation rights)

```text
- change review.decision
- re-evaluate capture or images
- add new laws/symptoms/blockers not in chain
- write success if review is not CONTINUE
- publish ticket on STOP
- grep repo or re-run checks
```

If `review.decision=LOOP` → summarize **must not run**. If invoked:

```json
{ "step": "summarize", "blocked": true, "blocked_reason": "SUMMARIZE_NOT_ALLOWED_FOR_LOOP" }
```

##### When summarize runs

| review.decision | summarize | ticket RU | dev EN | data_context |
|-----------------|-----------|-----------|--------|--------------|
| **CONTINUE** | yes | publish if `task_completed=true` | always | optional |
| **STOP** | yes | **no** (status event only) | always | **required** |
| **LOOP** | **blocked** | — | — | — |

```text
CONTINUE → RU ticket + EN dev archive
STOP     → no success ticket + EN dev + data_context
LOOP     → summarize blocked
```

##### Dual outputs

| Part | Audience | Lang | When publish |
|------|----------|------|--------------|
| **ticket** | Product / Discord / GitLab | **RU** | only `task_completed=true` |
| **dev** | Next engineer / next run | **EN** | **always** (especially on STOP) |

**Ticket answers:** what changed for user? which visible symptoms closed? what to verify manually?

**Ticket must not:** repo paths, raw law slugs, loop jargon, dart analyze, «мы думали».

**Dev answers:** decision, reason_code, laws status, symptom_closure mirror, files, tests, gates, blockers, loop budget, next_steps, artifact_pointers, regression_risks.

##### task_completed — orchestrator-owned

```text
agent writes:  agent_task_completed_recommendation (+ coercion_reason in dev if mismatch)
orchestrator:  task_completed, task_completed_source, forensic_completed, screen_completed
```

Agent **never** overrides orchestrator hard gates in persisted publish flags.

FORENSIC nuance:

```json
{
  "task_completed": false,
  "forensic_completed": true,
  "screen_completed": false
}
```

Forensic success ≠ «экран исправлен» in product ticket.

##### L6 inputs

```text
review_summary_json
task_completed_gate_snapshot_json
summarize_rubric_json
law_label_map_ru_json   # .opencode/context/law-label-map-ru.yaml
reasoning_chain_json
```

No vision. No repo map (optional law labels only).

##### Law label map RU

Curated: `.opencode/context/law-label-map-ru.yaml`. Unknown laws → short plain RU from review/diagnose text, not raw slug alone in ticket.

##### STOP status event (not ticket summary)

```text
Ремонт остановлен: автоматический бюджет исчерпан, инженерный контекст сохранён для следующего запуска.
```

or human-law variant. One line RU lifecycle signal; full truth in dev + data_context.

##### Canonical anti-example: `limbo/login_version_1`

After review `LOOP / CAPTURE_GATE_FAILED`: ticket `publish=false`, dev documents 13% capture blocker, **no** «login repaired» headline.

#### Example: `summarize.json` (task completed — CONTINUE)

```json
{
  "step": "summarize",
  "blocked": false,
  "review_decision": "CONTINUE",
  "review_reason_code": "REVIEW_OK",
  "task_completed": true,
  "task_completed_source": "orchestrator_hard_gate",
  "agent_task_completed_recommendation": true,
  "forensic_completed": false,
  "screen_completed": true,
  "ticket": {
    "publish": true,
    "language": "ru",
    "summary_md_path": ".repair/reports/ticket_summary.md",
    "headline": "Форма входа выровнена относительно макета",
    "user_visible_change": "Поля, CTA и social-login блок соответствуют verified Figma reference.",
    "symptoms_closed": [
      "Исправлено вертикальное смещение формы",
      "Убрано наложение текста в полях"
    ],
    "what_to_verify": [
      "Перегенерировать экран",
      "Проверить fresh preview по runId",
      "Сверить форму и CTA с Figma"
    ]
  },
  "dev": {
    "language": "en",
    "summary_md_path": ".repair/reports/dev_summary.md",
    "decision": "CONTINUE",
    "laws": [
      {
        "lawId": "preview_branch_must_preserve_scroll_contract",
        "layer": "generated_shell",
        "status": "closed",
        "files": ["src/figma_flutter_agent/generator/layout/common.py"],
        "tests": ["tests/test_preview_scroll_host.py"],
        "evidence": [".repair/state/capture.json:/passed"]
      }
    ],
    "symptom_closure": [],
    "verification": {
      "check": "passed",
      "capture": "verified_passed",
      "change_proof": "ok"
    },
    "blockers": [],
    "regression_risks": [],
    "next_steps": [],
    "artifact_pointers": [
      ".repair/state/review.json",
      ".repair/state/check.json",
      ".repair/state/capture.json"
    ]
  },
  "routing": {
    "ticket_destination": "gitlab_or_discord",
    "data_context_written": false,
    "resume_hint": null
  }
}
```

#### Example: `summarize.json` (STOP — not completed)

```json
{
  "step": "summarize",
  "blocked": false,
  "review_decision": "STOP",
  "review_reason_code": "LOOP_BUDGET_EXHAUSTED",
  "task_completed": false,
  "task_completed_source": "orchestrator_hard_gate",
  "agent_task_completed_recommendation": false,
  "forensic_completed": false,
  "screen_completed": false,
  "ticket": {
    "publish": false,
    "language": "ru",
    "summary_md_path": null,
    "headline": null
  },
  "dev": {
    "language": "en",
    "summary_md_path": ".repair/reports/dev_summary.md",
    "decision": "STOP",
    "reason_code": "LOOP_BUDGET_EXHAUSTED",
    "blockers": [
      "same_root_hash repeated without state improvement after diagnose refinements"
    ],
    "next_steps": [
      "Human: decide whether proposed law should be accepted",
      "Re-run from diagnose.refine with data_context injected"
    ],
    "artifact_pointers": [
      ".repair/state/review.json",
      ".repair/state/reasoning_chain.json"
    ]
  },
  "routing": {
    "ticket_destination": "none",
    "status_event": "Ремонт остановлен: автоматический бюджет исчерпан, инженерный контекст сохранён.",
    "data_context_written": true,
    "data_context_path": ".repair/data_context.json",
    "resume_hint": "diagnose.refine"
  }
}
```

**Data context** (`.repair/data_context.json`) — orchestrator-written after summarize when ¬completed; summarize.dev block is source. Inject on next Run Gate / «Данные». Optional mirror: `.debug/<project>/<feature>/repair_data_context.json`.

#### Example: `summarize.json` (LOOP — blocked)

```json
{
  "step": "summarize",
  "blocked": true,
  "blocked_reason": "SUMMARIZE_NOT_ALLOWED_FOR_LOOP"
}
```

#### `data_context.json` shape (orchestrator-written after summarize)

```json
{
  "schema_version": 1,
  "case_id": "repair_limbo_login_version_1_20260619",
  "source_run_id": "run_abc",
  "task_completed": false,
  "forensic_completed": false,
  "screen_completed": false,
  "written_at": "2026-06-19T12:00:00Z",
  "dev_summary_ref": ".repair/reports/dev_summary.md",
  "dev": { "...": "same structured block as summarize.dev" },
  "reasoning_chain_ref": ".repair/state/reasoning_chain.json",
  "resume_hint": "recognise",
  "board": "screen"
}
```

Next Run Gate / «Данные» **must** load `data_context.json` when present and append to `run_context` — cumulative chain from prior case **plus** dev handoff, без re-parsing всего `.debug/` с нуля.

#### Summarize inputs (prompt)

- Full **cumulative reasoning chain** `recognise … review`
- `run_manifest.json`, `review.json`, `capture.json`, `check.json`
- Orchestrator injects **`task_completed` candidate** + hard gate snapshot (agent may disagree in notes, orchestrator wins on publish)

#### Summarize skill contract

- **×1** model — archive step, no ensemble; anti-creative mirroring only
- Write **`summarize.json`** + md files when applicable
- **ticket**: RU, 3–8 short paragraphs max, `what_to_verify[]`, law labels from `law-label-map-ru.yaml`
- **dev**: EN always; mirror `review.lawCompliance` and `review.symptomClosure`
- **LOOP** → `blocked=true`; orchestrator must not call summarize on LOOP

#### Legacy CP mapping

| Planned | Legacy CP |
|---------|-----------|
| `ticket` + `publish=true` | `post_ticket_comment(render_ticket_markdown(...))` |
| `ticket.publish=false` | status comment / SSE event only — short human line |
| `data_context.json` | replaces ad-hoc «grep last repair job» for retry |

### 8.5 Model policy: 5-agent ensemble on decisions, 1 model on execution (согласовано 2026-06-19)

**Principle:** cheap ≠ weak. Target roster = **OpenRouter green-tier** models. **Ensemble ×5** on recognise / diagnose / review in **production**; **MVP ships ×1** first (§16 M5).

#### Feature flag (M1–M4 default off)

```yaml
debug_pipeline:
  ensemble:
    enabled: false          # MVP: recognise ×1, diagnose ×1, review ×1
    panel_size: 5           # when enabled → production panels below
```

| Mode | recognise | diagnose | review |
|------|-----------|----------|--------|
| **MVP** (`enabled: false`) | ×1 | ×1 | ×1 |
| **Production** (`enabled: true`) | ×5 | ×5 | ×5 |

**Why:** prove state machine, Run Gate, schemas, sandbox, check/capture **before** merge-rules orchestration. Ensemble is **M5**, not M1.

#### Ensemble steps (5 agents each)

| Step | Agents | Why ×5 |
|------|--------|--------|
| **recognise** | **5** | Symptom completeness, vision + contrarian severity |
| **diagnose** | **5** | Named law, layer, evidence — replaces legacy 5× diagnose-* + consilium |
| **review** | **5** | CONTINUE / LOOP / STOP — false CONTINUE is catastrophic |

#### Single-model steps (×1)

| Step | Agents | Model role |
|------|--------|------------|
| **inspect** | **1** | Entity map, grep, repo paths — deterministic |
| **plan** | **1** | `plan.json` from laws — structured, no debate |
| **repair** | **1** | Code workhorse — execute plan in build mode |
| **fix** | **1** | Post-check candidate Dart patch — build mode, narrow bundle |
| **summarize** | **1** | Archive JSON (+ optional cheap md) |

Deterministic gates (**check**, **capture**) — **0 OpenCode**. **fix** is OpenCode build (×1), not an ensemble step.

#### Target model roster (green tier — product chart `llm-costs`)

Approx OpenRouter slugs (verify at deploy):

| Model | Role in roster | Notes |
|-------|----------------|-------|
| `qwen/qwen3-vl-235b-a22b-thinking` | **vision** | recognise — figma.png / capture |
| `qwen/qwen3.7-max` | general / judge | highest green-tier score (~66) |
| `moonshotai/kimi-k2.7-code` | code-aware reader | inspect-adjacent; repair option |
| `deepseek/deepseek-v4-pro` | reasoner | diagnose / plan |
| `xiaomi/mimo-v2.5-pro` | contrarian | review skeptic slot |
| `minimax/minimax-m3` | fast panelist | all ensembles |

Flagships (red tier: GPT-5.5, Opus, Sonnet, Gemini Pro) — **not default**; reserve for human escalation or optional judge-only slot if green panel deadlocks.

#### Default 5-panels (draft)

**recognise ×5** (plan mode, vision required on panel):

```yaml
recognise_panel:
  - qwen/qwen3-vl-235b-a22b-thinking   # vision
  - qwen/qwen3.7-max
  - moonshotai/kimi-k2.7-code
  - minimax/minimax-m3
  - xiaomi/mimo-v2.5-pro
```

**diagnose ×5** (plan mode; epistemic roles in agent prompt, same models):

```yaml
diagnose_panel:
  - deepseek/deepseek-v4-pro             # architect
  - qwen/qwen3.7-max                     # empiric
  - moonshotai/kimi-k2.7-code            # pragmatist
  - xiaomi/mimo-v2.5-pro                 # skeptic
  - minimax/minimax-m3                   # devil / edge cases
```

**review ×5** (plan mode; vote on `decision`):

```yaml
review_panel:
  - qwen/qwen3.7-max                     # law closure
  - deepseek/deepseek-v4-pro             # anti-patching
  - moonshotai/kimi-k2.7-code            # regression / tests
  - xiaomi/mimo-v2.5-pro                 # skeptic / fix_proven
  - minimax/minimax-m3                   # product symptom closure
```

**×1 singles:**

```yaml
debug_pipeline:
  models:
    inspect: minimax/minimax-m3
    plan: deepseek/deepseek-v4-pro
    repair: moonshotai/kimi-k2.7-code      # code workhorse, build mode
    summarize: minimax/minimax-m3
```

Alternative: **`openrouter/fusion`** with same 5 slugs as panel — equivalent if Fusion judge replaces hand-rolled merge; **default = 5 parallel subagents** for explicit `ensemble/*.json` audit.

#### Ensemble merge → executive JSON (deterministic orchestrator)

Each panelist writes `.repair/state/<step>/panel/<agent_id>.json` + optional detail log. Orchestrator emits **one** executive `state/<step>.json`.

| Step | Merge rule |
|------|------------|
| **recognise** | Union `symptoms[]` by `id`; dedupe; **severity = max**; drop panelists with zero symptoms unless all empty → escalate |
| **diagnose** | Laws present in **≥3/5** panels → keep; else judge pass (`qwen3.7-max` tie-break); **conflicting layers** → `blocked: true` |
| **review** | **`CONTINUE` only if ≥4/5** vote CONTINUE **and** hard gates pass; **STOP** if ≥3/5 STOP; else **LOOP** + merge `reason_code` majority |

Panel disagreement → `ensemble.disagreement: true` in executive JSON + full panel preserved on disk for audit.

#### Cost posture

Green tier ≈ **$0.26–1.25 / M input** vs flagships **$3–5 / M**. **5 × cheap** on three steps << **1 × Opus** on a long repair loop triggered by wrong law.

Benchmark reference: product chart `llm-costs` (green targets ~56–66 vs flagships ~56–75 — gap small; vision via Qwen-VL).

#### Deprecated

- Single-model recognise / diagnose / review for production pipeline
- Default **`openrouter/fusion`** without explicit 5-slug panel config
- Legacy `.opencode/agents/diagnose-*` as **separate** orchestration (roles absorbed into diagnose_panel prompts)

### 8.5.1 OpenCode **Plan mode** vs pipeline **plan** step (согласовано 2026-06-19)

**Это разные вещи.** Не путать UI toggle OpenCode с шагом 4 нашего orchestrator.

| | **OpenCode Plan mode** | **Pipeline step `plan`** |
|--|------------------------|---------------------------|
| **Что** | Built-in **permission profile** / agent mode в TUI | Orchestrated **шаг 4/7** с `plan.json` |
| **Переключение** | `Tab` в TUI: Build ↔ Plan | Python orchestrator вызывает step skill |
| **Tools** | `write`/`edit`/`patch`/`bash` **off**; `read`/`grep`/`glob` on | То же via agent `permission: edit: deny` |
| **Исключение** | Может писать только `.opencode/plans/*.md` | Пишет **`.repair/state/<step>.json`** (orchestrator, не agent edit tool) |
| **Output** | Prose plan в чате / optional md | **Executive JSON** + optional `<step>.detail.log` |
| **Gate** | Нет — UX convenience | Каждый `steps[]` → `lawId` из diagnose + named test |

**OpenCode docs:** [Intro — Plan mode](https://opencode.ai/docs/), [Modes](https://open-code.ai/en/docs/modes), [Permissions](https://opencode.ai/docs/permissions/).

#### Plan mode для read-only шагов (resolved)

Orchestrator **принудительно** выставляет OpenCode **`mode: plan`** (или agent с `edit: deny`) на всех шагах **без write**:

| Pipeline step | OpenCode mode | Tools |
|---------------|---------------|-------|
| 1 recognise | **plan** | read; vision input |
| 2 inspect | **plan** | read, grep, glob |
| 3 diagnose | **plan** | read, grep, glob |
| 4 plan | **plan** | read, grep, glob |
| 5 **repair** | **build** | edit/write in **sandbox only** |
| 6 review | **plan** | read, grep, diff |
| 7 summarize | **plan** | read (optional write только `summarize.md` via orchestrator) |

**Refine loops:** `diagnose.refine`, `plan.revise` — остаются **plan** mode.

**Единственный build step:** **repair** (и `repair.retry`).

Planned `.opencode/opencode.json` fragment:

```json
{
  "agent": {
    "repair-build": {
      "permission": {
        "edit": "allow",
        "bash": {
          "ruff *": "allow",
          "pytest *": "allow",
          "git push *": "deny"
        }
      }
    }
  }
}
```

Orchestrator per step: `POST /session/.../message` with `mode: "plan"|"build"` (verify serve API at M4 wiring).

**Как используем в pipeline:**

```text
Steps 1–4 (+ refine/revise)  → mode=plan  → executive JSON → .repair/state/
Step 5 repair                → mode=build → sandbox src/ only
Steps 6–7                    → mode=plan  → review.json / summarize.json
```

**Не используем** `.opencode/plans/*.md` как source of truth — только `.repair/state/*.json`. Md в `.opencode/plans/` = optional human appendix (= `*.detail.log`), не для gates.

**Legacy mapping:** `repair-planner`, `diagnose-*` agents (`edit: deny`) ≈ plan mode + step skills.

**Open decision:** exact serve API field name for mode switch (verify when wiring M4).

### 8.6 Sandbox (NOT IMPLEMENTED)

**Invariant:** агент **не** правит основной `src/figma_flutter_agent` в agent repo напрямую.

Planned: git worktree (как control panel) или `.temp/repair-<id>/` copy → правки только там → gates → optional MR.

Control panel уже имеет `create_repair_worktree` / `copy_processed_snapshot` — переиспользовать для wizard local.

### 8.7 Planned code locations (next implementation)

| Component | Path |
|-----------|------|
| Pipeline orchestrator | `src/figma_flutter_agent/dev/opencode/pipeline.py` |
| Worktree manifest + materialize bundle | `src/figma_flutter_agent/dev/opencode/workspace.py` |
| Step state schemas + gates | `src/figma_flutter_agent/dev/opencode/state.py`, `schemas/` |
| Wizard hook | extend `wizard/debug_agent.py` after session stub |
| Headless parity | refactor `control_panel/repair/orchestrate.py` to shared pipeline |
| Master prompt | `.opencode/prompts/repair-master.md` |
| Skills ×7 | `.opencode/skills/*` |
| Agents ×7 | `.opencode/agents/debug-*.md` |
| **Run Gate (M0)** | `src/figma_flutter_agent/dev/opencode/run_gate.py` |
| **`FailureClass` (M0)** | `src/figma_flutter_agent/dev/opencode/failure_class.py` — §8.0 |
| **Agent board router** | `src/figma_flutter_agent/dev/opencode/board.py` |
| Post-repair **check** + route | `src/figma_flutter_agent/dev/opencode/check.py` |
| **Capture** gate | `src/figma_flutter_agent/dev/opencode/capture_gate.py` (wraps `debug/capture.py`) |
| Optional **fix** (emit layer) | OpenCode build pass — `.opencode/skills/fix/`; same session contract as repair |
| **`runId` stamp + probe** | pipeline start + generator emit; `served_run_id_probe` backends |
| **Ensemble orchestrator** | `dev/opencode/ensemble.py` — 5-panel merge → executive JSON |
| **Summarize router** | `dev/opencode/summarize.py` — ticket vs `data_context.json` publish |

### 8.8 Post-repair **check**, OpenCode **fix**, **capture** (согласовано 2026-06-19; fix OpenCode contract 2026-06-19)

**Two gate types after agent repair:**

| Gate | Type | Question | Failure class (typical) |
|------|------|----------|-------------------------|
| **check** | deterministic, 0 LLM | Compiles, validates, writes? | `PATCH_CODE_*`, `ROLLED_BACK` |
| **fix** | **OpenCode build** (post-check sub-phase) | Candidate planned Dart analyzable? | loops → `diagnose.refine` |
| **capture** | deterministic, 0 LLM | **Looks** like Figma on verified build? | `PATCH_VISUAL`, `STALE_CAPTURE` |

**Invariant:** **check** ≠ success. **Without capture** (SCREEN board) we do not know visual outcome — **no review CONTINUE** on analyze alone.

**check** runs compiler stages shared with `generate` (validate, analyze, write) — **not** CP `run_repair_gates`. **capture** runs [`run_project_debug_capture`](src/figma_flutter_agent/debug/capture.py) + diff vs `figma.png` + updates Run Gate capture passport.

#### Core fix invariant (anti hand-edit)

```text
Fix is not a repair of generated Dart in the product project.
Fix is a bounded candidate-materialization correction inside .repair/candidate/planned_files/.
The compiler-law repair remains the source of durable behavior.

planned_files fix may unblock check;
it must never become the product fix.
```

```text
Fix can unblock check.
Fix cannot close a law.
Fix cannot prove product correctness.
```

Closure remains only through: **repair → check → [fix → check]\* → capture → review**.

#### Two repair layers (do not conflate)

| Step | Layer | Target | Engine |
|------|-------|--------|--------|
| **`repair`** (agent step 5) | **Compiler law** | `src/figma_flutter_agent` in sandbox/worktree | OpenCode build |
| **`fix`** (post-check sub-phase) | **Candidate materialization** | `.repair/candidate/planned_files/**` only | OpenCode build (same session/skill/executive JSON contract) |

**Analog in plain `generate`:** [`run_analyze_repair_loop`](src/figma_flutter_agent/stages/llm_repair/loop.py) — **legacy outside** OpenCode debug pipeline only. Inside debug/repair pipeline: **`emit_fix_engine: opencode`** (default); `legacy_llm_repair` compat fallback.

**`fix` is not** a mini diagnose → plan → repair. It is a **narrow OpenCode pass** when the compiler law may already be plausible but **candidate planned Dart** fails parse/analyze.

**Do not** bounce to full `diagnose.refine` on every check failure — especially when `diagnose.json` law is stable and only Dart analyze/syntax failed (emit-layer).

#### Main path

```text
recognise → … → repair → check → [fix → check]* → capture → review → summarize
```

#### Sub-loop (after `check` / `capture`)

```text
repair → check → route
             ├─ emit fail → fix → check (loop, bounded)
             │       fix exhausted → diagnose.refine → plan.revise → repair …
             ├─ check OK → capture
             │       ├─ capture OK → review
             │       ├─ PATCH_VISUAL → diagnose.refine → plan.revise → repair …
             │       └─ STALE_CAPTURE → deterministic re-capture (×N) → else FORENSIC
             ├─ PATCH_CODE_COMPILER → repair.retry (build)
             ├─ PATCH_RUNTIME_FAILURE → diagnose.refine OR repair.retry
             ├─ TOOLCHAIN_FLAKE → deterministic retry (not LLM)
             ├─ GATE_INFRA_FAILURE → stop
             └─ (from review) REVIEW_REJECTED → plan.revise | repair.retry | fix
```

Formula: **check** = compiler truth; **capture** = visual truth; **review** = judgment only after both (SCREEN).

---

#### What `generate` runs today (source of truth)

From [`run_pipeline`](src/figma_flutter_agent/pipeline/run/core.py) — post-plan block:

| Order | Stage | In **`check`** | In **OpenCode `fix`** |
|-------|-------|----------------|------------------------|
| parse gate | `enforce_emit_parse_gate` | yes | after candidate patch → re-**check** |
| validate | `validate_planned_generation` | yes | — |
| **llm_repair** | `run_analyze_repair_loop` | no | **not in debug pipeline** (legacy generate only) |
| llm_visual_refine | `run_visual_refine_loop` | no | no |
| pre_write analyze | `analyze_planned_dart_files` | yes | re-run via **check** |
| write + analyze | `commit_planned_files` | yes | — |
| **capture** | `run_project_debug_capture` | **no** — separate **`capture`** gate | — |

**capture** gate (after check pass): regenerate/run screen with patched compiler if needed, PNG + `capture.json` + diff vs `figma.png`; set `capture.kind=verified` only when runIds align (§8.9).

Agent `check` does **not** repeat fetch → parse → llm → plan; it validates output after OpenCode **`repair`** (compiler patch), typically following a **re-generate** of the screen with patched compiler.

**Not CP repair gates:** [`run_repair_gates`](src/control_panel/repair/gates.py) stays for headless MR on agent repo — **not** screen check.

---

#### `check.json` (machine-readable)

```json
{
  "step": "check",
  "passed": false,
  "failedStage": "pre_write_analyze",
  "failure_class": "PATCH_CODE_EMIT",
  "failureLayer": "emit",
  "route": "fix",
  "stages": {
    "post_plan_parse_gate": "ok",
    "validate": "ok",
    "pre_write_analyze": "fail",
    "write": "skipped",
    "capture": "skipped"
  },
  "evidence": ["dart-errors.json:…"],
  "same_root_hash": "sha256:…",
  "symptom_hash": "sha256:…"
}
```

Full enum + routes: **§8.10**. Routing is **deterministic (0 LLM)** — not an agent classifier.

**Routing** (summary; canonical table §8.10):

| failedStage / signal | failureLayer | route |
|----------------------|--------------|-------|
| `*_parse_gate`, `pre_write_analyze`, `write_analyze`, Dart syntax/import | **emit** | `PATCH_CODE_EMIT` → **fix** |
| compiler pytest/ruff on sandbox `src/` (if in check scope) | **compiler** | `PATCH_CODE_COMPILER` → **repair.retry** |
| `validate` layout/runtime contract | law/emit | `PATCH_RUNTIME` |
| `capture` visual diff (verified) | law/visual | `PATCH_VISUAL` |
| write rollback before analyze | infra/truth | `ROLLED_BACK` → FORENSIC |
| analyze timeout, capture lock once | infra | `TOOLCHAIN_FLAKE` |
| SDK/sandbox broken | infra | `INFRA_HARD` |
| all ok (compiler) | — | → **capture** (not review yet) |

#### `capture.json` (visual gate — before review)

```json
{
  "step": "capture",
  "passed": false,
  "kind": "verified",
  "captured_run_id": "run_123",
  "target_build_run_id": "run_123",
  "served_build_run_id": "run_123",
  "png_hash": "sha256:…",
  "diff": { "score": 0.12, "threshold": 0.05, "heatmap": ".repair/debug/…/diff_heatmap.png" },
  "failure_class": "PATCH_VISUAL",
  "route": "diagnose.refine",
  "source": "flutter_test"
}
```

**SCREEN board:** `review` **blocked** unless `capture.passed` **or** capture disabled in config (explicit `capture.skipped: true` with reason — dev only).

**FORENSIC board:** capture may be `forensic`; visual diff **must not** gate success — review uses pipeline/write truth only.

#### When to route where

| Route | When | Next step |
|-------|------|-----------|
| **PATCH_CODE_EMIT** | Law likely OK; Dart/planned files fail analyze | **`fix`** → **check** (bounded) |
| **PATCH_CODE_COMPILER** | OpenCode patch broke compiler src / tests | **repair.retry** (same plan, no re-diagnose) |
| **PATCH_RUNTIME_FAILURE** | compiles but wrong runtime contract | **diagnose.refine** if novel; else **repair.retry** |
| **PATCH_VISUAL_FAILURE** | **capture** diff / law not closed on verified PNG | **diagnose.refine** → plan.revise → repair |
| **STALE_CAPTURE** | capture runId ≠ served | deterministic **re-capture** → else FORENSIC |
| **TOOLCHAIN_FLAKE** | timeout, flake | re-**check** deterministically |
| **GATE_INFRA_FAILURE** | hard infra | stop / escalate |
| **fix exhausted** | `fix_attempt >= max_fix_attempts` **or** `same_root_hash` repeat without state improvement | **`diagnose.refine`** → `plan.revise` → … (not another fix) |
| **diagnose refinements exhausted** | `diagnose.refine_count >= max_diagnose_refinements` still failing | **STOP_HUMAN** |
| **REVIEW_REJECTED** | law compliance | **plan.revise** / **repair.retry** / **fix** by review reason |

#### Fix — canonical edit root and mirrors (согласовано 2026-06-19)

**One canonical edit root:**

```text
allowed (fix may write):
  .repair/candidate/planned_files/**

read-only (fix may read):
  .repair/debug/<project>/<feature>/**
  .repair/candidate/pre_emit.json
  .repair/candidate/plan.dart
  .repair/state/**
  check_summary / analyze_errors injected in L6

forbidden:
  src/figma_flutter_agent/**
  apps/*/lib/**
  sandbox/*/lib/**
  .debug/** (agent repo canonical debug — not worktree edit target)
  goldens/**
  fixtures/**
```

```text
fix edits planned_files only
orchestrator regenerates mirrors (e.g. debug screen.dart copy) after fix
```

Fix must **not** edit `.repair/debug/.../screen.dart` directly — risk of mirror/candidate desync.

#### Fix — routing (deterministic classifier only)

Fix runs **only** when classifier returns `PATCH_CODE_EMIT`:

```text
PATCH_CODE_EMIT           → fix → check
PATCH_CODE_COMPILER       → repair.retry
PATCH_RUNTIME_FAILURE     → diagnose.refine OR repair.retry
PATCH_VISUAL              → diagnose.refine
TOOLCHAIN_FLAKE           → deterministic retry (no fix)
WRITE_COMMIT / ROLLED_BACK / NO_SERVE / STALE_CAPTURE (infra) → fix skip
```

The fix skill confirms `failure_class`; it does not self-route on visual or compiler failures.

#### Fix — narrow bundle (orchestrator preflight)

Fix must not receive full `.debug`, vision history, or whole-repo grep permission.

```json
{
  "check_summary": {
    "failure_class": "PATCH_CODE_EMIT",
    "failedStage": "pre_write_analyze",
    "same_root_hash": "sha256:…"
  },
  "analyze_errors": [
    {
      "file": ".repair/candidate/planned_files/order_details_layout.dart",
      "line": 42,
      "code": "undefined_identifier",
      "message": "Undefined name X"
    }
  ],
  "allowedEditFiles": [
    ".repair/candidate/planned_files/order_details_layout.dart"
  ],
  "frozenContext": {
    "diagnoseLawIds": ["preview_branch_must_preserve_scroll_contract"],
    "planStepOrders": [1],
    "repairFilesTouched": ["src/figma_flutter_agent/generator/…"]
  },
  "attempt": 1,
  "maxAttempts": 2
}
```

#### Fix — master L1, output, loop (согласовано 2026-06-19)

**No separate fix-master L1.** Use board master (`repair-master-screen` or `repair-master-forensic`) + shared invariants + `fix/` skill L2–L6. Fix L3 states: law frozen; materialization only.

**Output contract:**

```text
source of truth = real file edits under planned_files/ + fix.json
unified diff in chat = not handoff
optional appendix: .repair/state/fix.diff (orchestrator: git diff planned_files/)
errorsAfter = next check.json only (fix may note expectedErrorsAfter)
```

**One OpenCode invocation = one fix attempt.** Orchestrator owns loop:

```text
check fail PATCH_CODE_EMIT → fix attempt 1 → check → fix attempt 2 → check
→ exhausted / same_root_hash / no improvement → diagnose.refine
```

Fix agent does **not** run check, capture, or inner repair loops.

#### Example: `fix.json`

```json
{
  "step": "fix",
  "phase": "emit_materialization",
  "attempt": 1,
  "maxAttempts": 2,
  "blocked": false,
  "exhausted": false,
  "failure_class": "PATCH_CODE_EMIT",
  "same_root_hash": "sha256:…",
  "allowedEditFiles": [
    ".repair/candidate/planned_files/order_details_layout.dart"
  ],
  "filesTouched": [
    ".repair/candidate/planned_files/order_details_layout.dart"
  ],
  "errorsBefore": 3,
  "expectedErrorsAfter": 0,
  "diagnoseLawIdsFrozen": [
    "preview_branch_must_preserve_scroll_contract"
  ],
  "planStepOrders": [1],
  "diffRef": ".repair/state/fix.diff",
  "routeAfter": null,
  "notes": "Minimal candidate Dart correction for undefined identifier from materialization."
}
```

No `lawClosed`, `task_completed`, or product success fields in `fix.json`.

#### Review LOOP → fix

Only when `reason_code` is emit/analyze materialization, e.g.:

```text
REVIEW_REJECTED_EMIT_ANALYZE
CHECK_REGRESSION_AFTER_REVIEW
MISSING_CANDIDATE_DART_CORRECTION
```

Same narrow bundle as post-check fix. Review must **not** route visual/law failures to fix:

```text
LAW_NOT_CLOSED        → diagnose.refine / plan.revise
compiler regression     → repair.retry
PATCH_VISUAL          → diagnose.refine
PATCH_CODE_EMIT       → fix
```

#### FORENSIC fix policy

**Default: fix skip** on FORENSIC (writeback/serve/capture trust not established).

**Edge case allowed** — forensic **candidate** materialization only:

```json
{
  "case_mode": "FORENSIC",
  "failure_class": "PATCH_CODE_EMIT",
  "candidate_available": true,
  "allowedEditFiles": [".repair/candidate/planned_files/…"],
  "fix_purpose": "make candidate analyzable before writeback",
  "forbidden": ["screen visual diagnosis", "capture-based success"]
}
```

Skip fix when failure is `WRITE_COMMIT_FAILURE`, `TOOLCHAIN_FLAKE`, `INFRA_HARD`, `STALE_CAPTURE`, `NO_SERVE`.

#### `emit_fix_engine` config

```yaml
debug_pipeline:
  emit_fix_engine: opencode   # opencode | legacy_llm_repair
  loops:
    max_fix_attempts: 2
```

| Engine | When |
|--------|------|
| **opencode** (default) | debug/repair pipeline — OpenCode `fix/` skill |
| **legacy_llm_repair** | compat fallback; plain `figma-flutter generate` unchanged |

#### Fix decision table (frozen)

| Question | Decision |
|----------|----------|
| Canonical edit root | Only `.repair/candidate/planned_files/**` |
| `screen.dart` mirror | Read-only; orchestrator regenerates from candidate |
| Output | File edits + `fix.json`; `fix.diff` by orchestrator |
| Invocation | One OpenCode pass per attempt |
| Loop owner | Orchestrator |
| Review → fix | Yes, same narrow `PATCH_CODE_EMIT` bundle |
| `run_analyze_repair_loop` | Legacy for generate; replaced in debug pipeline |
| FORENSIC fix | Skip default; candidate analyze edge case only |

#### `fix` invariants (anti-masking)

```text
fix may modify candidate planned Dart only under allowedEditFiles
fix result is never promoted as compiler repair unless diagnose law set unchanged
     and check proves no source-law bypass (compiler src untouched by fix)
fix cannot close diagnose.laws[] — law closure is review + capture responsibility
fix can only unblock check (emit/materialization path)
fix must not hand-edit project lib or debug mirrors as canonical truth
```

If **`fix` makes check pass** but **capture** or **review** still fail → route **diagnose.refine**, not «done».

#### Fix exhaustion → `diagnose.refine` (согласовано 2026-06-19)

Emit-layer **`fix`** assumes **law + compiler patch are plausible**; only **materialized Dart** is wrong. If **`fix` loops without progress**, the hypothesis is wrong — **law or plan**, not «ещё один llm_repair».

**Deterministic escalation (0 LLM):**

```text
PATCH_CODE_EMIT → fix #1 → check
               → fix #2 → check
               → fix #N → check   (N = max_fix_attempts, default 2; product knob up to 3)
               → still fail AND (same_root_hash OR no state improvement)
               → diagnose.refine
```

| Trigger | Route |
|---------|-------|
| `fix.json.attempt >= max_fix_attempts` and check still fail | **diagnose.refine** |
| `same_root_hash` repeated ≥2 with **no state improvement** | **diagnose.refine** (or **STOP_HUMAN** if refinements exhausted) |
| failure_class **changed** emit → visual/runtime | **diagnose.refine** (new law class) |
| check **passed** after fix | → **review** (skip diagnose) |

**`diagnose.refine` rules:**

- OpenCode **plan mode** (read-only)
- **Cumulative chain preserved** — refine/amend `diagnose.laws[]`, do **not** restart recognise/inspect unless review explicitly routes there
- After refine → **plan.revise** → **repair** (build) → **check** → …

**Not:** fix attempt #4 «на авось»; **not** full pipeline restart; **not** repair.retry for emit analyze failures.

#### Example: `fix.json`

```json
{
  "step": "fix",
  "attempt": 2,
  "maxAttempts": 2,
  "exhausted": true,
  "routeAfter": "diagnose.refine",
  "same_root_hash": "sha256:…",
  "stateImprovement": false,
  "errorsBefore": 3,
  "errorsAfter": 1,
  "plannedFilesHash": "sha256:…"
}
```

When `exhausted: true` and check still fails — orchestrator **must** route **`diagnose.refine`**, not loop fix.

#### `diagnose.refine` vs `fix` vs `repair.retry`

| Situation | Step |
|-----------|------|
| Undefined name in generated Dart after compiler fix | **fix** |
| Visual diff still wrong after fix + check | **diagnose.refine** |
| Wrong scroll host in plan shape (law OK, plan bad) | **diagnose.refine** → **plan.revise** |
| Typo in Python compiler patch / pytest fail | **repair.retry** |
| Same analyze error after N× fix (N = max_fix_attempts) | **diagnose.refine** — law/emitter likely wrong |

#### Loop budget

```yaml
debug_pipeline:
  loops:
    max_fix_attempts: 2              # llm_repair; product knob 3 ok — then → diagnose.refine
    max_repair_retries_per_plan: 2   # OpenCode compiler retry
    max_diagnose_refinements: 2      # after fix/repair loops exhausted
    max_total_candidate_patches: 4
    max_toolchain_retries: 2
    max_check_after_fix: 2           # check cycles per fix attempt
  escalation:
    fix_exhausted_route: diagnose.refine
    same_root_hash_repeat_without_improvement: 2  # → diagnose.refine or STOP_HUMAN
    diagnose_refinements_exhausted: STOP_HUMAN
```

**Classifier:** routing after **check** is **deterministic (0 LLM)**. Agent involvement only on ambiguous visual/semantic remainder after rules exhaust.

#### Planned code

- **`run_screen_check_phase`** — extract from `run_pipeline` tail; shared by generate + agent
- **`run_agent_fix_phase`** — thin wrapper → `run_analyze_repair_loop`
- **`classify_failure()`** — shared with Run Gate; returns `FailureClass` from **`failure_class.py`** (§8.0)
- Agent orchestrator: Run Gate → … → `repair` → `check` → (`fix` → `check`)\* → **`capture`** → review

### 8.9 RUN GATE (M0) — deterministic precondition before agent (согласовано 2026-06-19, consilium 2026-06-19)

**Type:** deterministic gate, **0 LLM, 0 agents**. Runs **after** artifact refresh (`Данные`) and **before** recognise/inspect/… Agent pipeline **must not start** until Run Gate emits verdict + `case_mode`.

Fixes root lie: served build had **no passport** — freshness was guessed from logs/Chrome, which can lie, lag, or describe rollback.

#### Core doctrine

```text
fresh/stale is NOT vibes, NOT Chrome screenshot alone
fresh = served_build_run_id == committed_build_run_id (and capture verified when used)

no build passport → no screen diagnosis
served_runId != committed → FORENSIC, not SCREEN
write rollback → error overlay with failed runId, NOT silent previous build
capture without matching runId → forensic, not verified
fix_proven only when project lib committed moved — NOT .debug bundle alone
```

#### Four runIds (not one `latest`)

`pipeline_run_id` may be a **failed candidate** while served build is last **successful** commit. Never compare «served vs latest» alone.

| Field | Meaning |
|-------|---------|
| `pipeline_run_id` | Current pipeline execution (may have failed) |
| `candidate_build_run_id` | Run id stamped into **this run's** planned/candidate emit |
| `committed_build_run_id` | Run id in **project lib on disk** after write (post-commit or post-rollback) |
| `served_build_run_id` | Run id **actually running** in preview/capture probe |

**ROLLED_BACK** when: `pipeline_run_id != committed_build_run_id` **and** `writeback=rollback` (equivalently `candidate != committed` after failed write).

#### `runId` stamp — three surfaces + probe abstraction

File comment alone is invisible to runtime; runtime alone is invisible to disk audit.

**Emit (generator):**

```dart
// FFA_RUN_ID: <uuid>

class OrderDetailsLayout extends StatelessWidget {
  static const String ffaRunId = '<uuid>';
  // ...
}
```

**Runtime probe** (`served_run_id_probe` — not web-only):

| Backend | Implementation |
|---------|------------------|
| **web** | `window.FFA_RUN_ID`, debug banner, hidden DOM probe |
| **flutter test / golden** | semantics label, find widget, test harness |
| **file** | read `static const ffaRunId` / comment from committed layout on disk |

Orchestrator compares probe result to `committed_build_run_id` and `candidate_build_run_id`.

#### Capture passport

```json
"capture": {
  "kind": "verified | forensic",
  "captured_run_id": "run_123",
  "target_build_run_id": "run_123",
  "captured_at": "2026-06-19T12:00:00Z",
  "png_hash": "sha256:…",
  "source": "flutter_test | chrome | manual"
}
```

**Rule:** `kind=verified` **only if** `captured_run_id == served_build_run_id == committed_build_run_id`. PNG present but runId missing/mismatch → **`forensic`**.

#### Run manifest (gate output)

Path: `.debug/<project>/<feature>/run_manifest.json`

```json
{
  "feature": "order_details",
  "pipeline_run_id": "run_123",
  "candidate_build_run_id": "run_123",
  "committed_build_run_id": "run_122",
  "served_build_run_id": "run_122",
  "stages": { "plan": "ok", "write": "rollback", "capture": "forensic" },
  "writeback": "rollback",
  "verdict": "ROLLED_BACK",
  "candidate_available": true,
  "case_mode": "FORENSIC",
  "allowed_questions": ["why write/analyze/capture failed"],
  "forbidden_questions": ["why visible Chrome UI layout is wrong"],
  "capture": {
    "kind": "forensic",
    "captured_run_id": null,
    "target_build_run_id": "run_123",
    "png_hash": "sha256:…",
    "source": "chrome"
  },
  "change_proof": {
    "debug_bundle": { "changed": true, "hash_before": "…", "hash_after": "…" },
    "project_lib": {
      "changed": false,
      "committed_run_id_before": "run_122",
      "committed_run_id_after": "run_122"
    },
    "changed_files": ["lib/generated/order_details_layout.dart"],
    "diff_stat": { "files": 1, "additions": 0, "deletions": 0 },
    "fix_proven": false
  }
}
```

**`candidate_available`:** not a separate verdict — flag on **`ROLLED_BACK`**. Same route (forensic); when true, agent may read candidate code from debug/planned artifacts; when false, logs/manifest only.

**`change_proof.fix_proven`:** `true` **only if** `project_lib.changed` **and** `committed_build_run_id` advanced. Debug `.debug/<project>/<feature>/screen.dart` changing while writeback rolls back → **`fix_proven: false`** — review/summarize must not claim «fix landed».

#### Verdicts (Run Gate subset of §8.10 enum)

| Verdict | Condition | `case_mode` |
|---------|-----------|-------------|
| **FRESH_OK** | write committed; served == committed == candidate; capture verified (if used) | **SCREEN** |
| **ROLLED_BACK** | write failed/rollback; committed ≠ candidate/pipeline | **FORENSIC** |
| **STALE_CAPTURE** | write ok; capture runId ≠ served | re-capture (deterministic); else FORENSIC capture-infra |
| **NO_SERVE** | no valid served probe | hard stop — no screen agent |

**Invariant:** kill silent `served_preview: previous build`. Codegen/write failed → preview shows **error overlay** with failed `pipeline_run_id`, not yesterday's frame as current truth.

Replace: [`wizard/run_actions.py`](src/figma_flutter_agent/wizard/run_actions.py) → `served_preview: previous build`.

#### Agent case_mode (injected before step 1)

```json
{
  "case_mode": "SCREEN",
  "agent_board": "screen",
  "allowed_questions": ["visual fidelity", "layout law", "component law"],
  "forbidden_questions": []
}
```

```json
{
  "case_mode": "FORENSIC",
  "agent_board": "forensic",
  "allowed_questions": ["why generation/write/capture failed"],
  "forbidden_questions": ["why visible UI is wrong in Chrome"]
}
```

#### Agent boards: SCREEN vs FORENSIC (согласовано 2026-06-19)

**Invariant:** один pipeline из 7 шагов, но **две разные agent board** — Run Gate выбирает board **до** recognise. Нельзя смешивать visual-fidelity шаги с forensic-pipeline шагами в одной доске: иначе агент снова «чинит UI» по призраку.

| Board | Когда | Главный вопрос |
|-------|-------|----------------|
| **`screen`** | Run Gate → `FRESH_OK`, `case_mode=SCREEN` | «Какой **law** compiler нарушен относительно Figma?» |
| **`forensic`** | `ROLLED_BACK`, `STALE_CAPTURE` (infra), `NO_SERVE` recovery path | «Почему **generate/write/capture** не стали truth?» |

**SCREEN board** — подблок **visual** (только при `capture.kind=verified`):

```text
┌─ SCREEN agent board ─────────────────────────────────────┐
│  ┌─ visual sub-board ────────────────────────────────┐  │
│  │ recognise (vision): four-pass vision bundle (below)  │  │
│  │ semantics hints (compact), not full semantics dump   │  │
│  │ skills: recognise-screen, inspect-screen           │  │
│  │ models: vision-capable (gemini/gpt-4o)             │  │
│  └────────────────────────────────────────────────────┘  │
│  ┌─ compiler sub-board (steps 2–7) ──────────────────┐  │
│  │ inspect → entity map (.debug + read-only src/)    │  │
│  │ diagnose → law inside entities from inspect       │  │
│  │ plan → repair → check → …                        │  │
│  │ forbidden: hand-edit generated Dart                │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Vision bundle (orchestrator preflight, 0 LLM)** — recognise-screen never receives a single overlay/diff as the primary UI source. The orchestrator builds a deterministic watermarked package under `.repair/vision/`:

```text
01_FIGMA_REFERENCE__{runId}.png      # baked top label bar: FIGMA_REFERENCE
02_FLUTTER_CAPTURE__{runId}.png      # baked top label bar: FLUTTER_CAPTURE
03_COMPARE_REF_CAPTURE__{runId}.png  # side-by-side strip: REF | CAPTURE
04_DIFF_HEATMAP__{runId}.png         # baked label: PIXEL_DIFF / changedRatio=…
05_COMPARE_GRID__{runId}.png         # optional: REF | CAPTURE | DIFF (three-panel)
```

Watermark rules: label is a **separate top bar** (solid background), not semi-transparent text over UI. Filename suffix `__{runId}` matches capture passport.

**Recognise pass order** (fixed in `recognise-screen/l5-actions.md`):

```text
1. Confirm case_mode=SCREEN and capture.kind=verified.
2. Pass A — FIGMA_REFERENCE only: expected UI inventory and hierarchy.
3. Pass B — FLUTTER_CAPTURE only: actual inventory and visible defects.
4. Pass C — REF|CAPTURE strip: semantic delta (presence, alignment, overlap, hierarchy).
5. Pass D — DIFF_HEATMAP only: global vs regional vs local severity; do not read UI text from heatmap.
6. Emit symptoms[] only — no law ids, repo paths, figmaIds, or root cause.
```

**Diff heatmap role:** localization and severity aid only (`changedRatio`, largest regions). Not for reading text, hierarchy, or element correctness. On screens with mass mismatch (e.g. login_version_1 ~13% changed), heatmap correctly signals `global layout/typography mismatch P0` without inventing emitter-level causes.

**L6 compact inputs** (orchestrator-computed; model must not eyeball diff math):

```json
{
  "vision_bundle": {
    "figma_reference": "01_FIGMA_REFERENCE__run-abc.png",
    "flutter_capture": "02_FLUTTER_CAPTURE__run-abc.png",
    "compare_strip": "03_COMPARE_REF_CAPTURE__run-abc.png",
    "diff_heatmap": "04_DIFF_HEATMAP__run-abc.png",
    "capture_kind": "verified",
    "captured_run_id": "run-abc",
    "served_build_run_id": "run-abc"
  },
  "diff": {
    "changedRatio": 0.13,
    "threshold": 0.05,
    "largestRegions": ["header", "form", "cta"]
  },
  "semantic_hints": {
    "buttons": 3,
    "inputs": 2,
    "text_blocks": 8,
    "has_primary_cta": true
  }
}
```

**Symptom output shape** (executive JSON): `id`, `severity`, `userVisible`, `regions[]`, `visualEvidence[]` (bundle filenames), `confidence`. Detail inventory per element lives in `recognise.detail.log`, not the executive file.

**FORENSIC board** — **без visual sub-board**:

```text
┌─ FORENSIC agent board ───────────────────────────────────┐
│  recognise: pipeline failure symptoms only               │
│  inspect: entity map — pipeline modules (write, analyze, capture) │
│  diagnose: infra/generation laws inside those modules             │
│  plan/repair: pipeline config, write gate, emit stamp  │
│  forbidden: figma.png diff, «Chrome UI wrong»          │
│  optional: read candidate from .debug if candidate_available │
└──────────────────────────────────────────────────────────┘
```

**Routing rule:** если Run Gate позже переводит дело `FORENSIC → SCREEN` (re-generate + `FRESH_OK`), orchestrator **переключает board** и **сбрасывает** visual-несовместимые outputs recognise/inspect (не reuse JSON про «UI кривой» из forensic pass).

**Planned config / code:**

```yaml
debug_pipeline:
  agent_boards:
    screen:
      visual_sub_board: true
      recognise_skill: recognise-screen
      inspect_skill: inspect-screen
      master_prompt: .opencode/prompts/repair-master-screen.md
      # plan, diagnose, repair, review, summarize: shared skills + master context
    forensic:
      visual_sub_board: false
      recognise_skill: recognise-forensic
      inspect_skill: inspect-forensic
      master_prompt: .opencode/prompts/repair-master-forensic.md
```

| Piece | Path | Prompts |
|-------|------|---------|
| Prompt assembler | `dev/opencode/prompt.py` | planned |
| Board router | `dev/opencode/board.py` | planned |
| SCREEN fork skills | `recognise-screen/`, `inspect-screen/` | done |
| FORENSIC fork skills | `recognise-forensic/`, `inspect-forensic/` | done |
| Shared step skills | `diagnose/`, `plan/`, `repair/`, `fix/`, `review/`, `summarize/` | done |
| JSON schemas | `dev/opencode/schemas/*.schema.json` | planned |
| Vision bundle | `prepare_recognise_vision_bundle()` | planned |
| Inspect preflight | `prepare_inspect_preflight()` | planned |
| Repo map loader | `dev/opencode/repo_map.py` + `.opencode/context/repo-map.yaml` | planned |

Product diagram: **Data Refresh → Run Gate → [screen board | forensic board]**; visual sub-block **only** inside screen board when `capture.kind=verified`.

#### Code locations (M0)

| Piece | Path |
|-------|------|
| Run Gate + shared classify | `src/figma_flutter_agent/dev/opencode/run_gate.py` |
| **`FailureClass` enum** | `src/figma_flutter_agent/dev/opencode/failure_class.py` (§8.0 — sole enum) |
| `runId` triple stamp | pipeline start + generator emit (`layout` shell) |
| Rollback + overlay | `stages/write.py`, preview serve |
| Probe backends | `validation/golden_capture.py`, web preview harness |

Wizard flow:

```text
Данные → Run Gate → [screen board | forensic board] → agent → check → capture → …
```

### 8.10 Unified failure / routing taxonomy (согласовано consilium 2026-06-19)

**One enum** for Run Gate **and** post-repair **check** classifier — not two parallel machines.

```text
checks failed → deterministic classify → root_hash budget → route
never: checks failed → full diagnose by default
```

#### FailureClass table

| Class | Where | Deterministic signal (0 LLM) | `case_mode` | Route | Agent? | Budget key |
|-------|-------|------------------------------|-------------|-------|--------|------------|
| **FRESH_OK** | Run Gate / check pass | write committed; runIds aligned; capture verified | SCREEN | → recognise… / **review** | yes | — |
| **ROLLED_BACK** | Run Gate / check | write rollback; `committed ≠ candidate`; `candidate_available` flag | FORENSIC | read candidate if available; **forbidden** Chrome-as-current | forensic only | `write:<stage>:<root_law>` |
| **STALE_CAPTURE** | Run Gate / check | capture missing or `captured_run_id ≠ served` | — | deterministic re-capture ×N | no until exhausted | `capture:stale:<reason>` |
| **NO_SERVE** | Run Gate | probe failed; no served runId | FORENSIC | stop / infra report | no | `serve:none:<reason>` |
| **PATCH_CODE_EMIT** | check | analyzer: undefined/type/import/syntax in **planned Dart** | — | **`fix`** → check | yes (fix loop) | `code:<error_code>:<file_region>` |
| **PATCH_CODE_COMPILER** | check | ruff/pytest fail on sandbox `src/` | — | **repair.retry** | yes (narrow) | per_plan |
| **PATCH_RUNTIME** | check | Flutter exception: ParentData, unbounded, never laid out | SCREEN/refine | same root → repair.retry; **novel root** → diagnose.refine | yes | `runtime:<exc>:<law>:<layer>` |
| **PATCH_VISUAL** | check | verified capture + diff / law not closed | SCREEN | diagnose.refine → plan.revise → repair | yes | `visual:<law>:<layer>` |
| **TOOLCHAIN_FLAKE** | gates | timeout, killed tree, non-diagnostic exit, lock (e.g. WinError 5) | — | deterministic retry (clean ws, kill analyzer, +timeout once) | **no** | `toolchain:<cmd>:<kind>` |
| **INFRA_HARD** | gates | missing SDK, sandbox locked after retries | — | stop / human | no | `infra:<component>:<reason>` |
| **REVIEW_REJECTED** | review | `decision=LOOP` + structured `reason_code` | per reason | route by code | yes | `review:<reason>:<law>` |
| **REVIEW_STOP** | review | `decision=STOP` (human / budget / risk) | — | summarize escalate | no | `review:stop:<reason>` |
| **UNKNOWN_BLOCKED** | any | missing stdout/manifest; cannot classify | — | stop / request evidence | no | `unknown:<stage>` |

**First check after repair:** Run Gate / write commit truth **before** PATCH_CODE/RUNTIME/VISUAL — do not diagnose screen on ghost.

**ROLLED_BACK ≡ WRITE_COMMIT_FAILURE** semantically (single class; consilium name `WRITE_COMMIT_FAILURE` maps here).

#### Route rules (compressed)

```text
FRESH_OK           → SCREEN pipeline / review
ROLLED_BACK        → FORENSIC generation; forbidden: Chrome screenshot as current UI
STALE_CAPTURE      → re-capture → else FORENSIC capture-infra
NO_SERVE           → stop
PATCH_CODE_EMIT    → fix → check (not diagnose)
PATCH_CODE_COMPILER→ repair.retry (not full diagnose)
PATCH_RUNTIME      → same root_hash → repair.retry; novel → diagnose.refine
PATCH_VISUAL       → diagnose.refine → plan.revise → repair
TOOLCHAIN_FLAKE    → deterministic retry only (no LLM from timeout alone)
INFRA_HARD         → stop
REVIEW_REJECTED    → by reason_code enum (review LOOP)
REVIEW_STOP        → summarize escalate (no more loops)
UNKNOWN_BLOCKED    → stop
```

#### `same_root_hash` (budget law — not symptom hash)

```text
same_root_hash = hash(
  failure_class,
  law_id,
  owning_layer,
  normalized_stage,
  normalized_component_kind   // e.g. stack_to_column | preview_shell | writeback
)
```

**Exclude from hash:** `node_id`, raw line number, message tail, screen name, asset filename, timestamp.

**Include when root identity:** `exception_type`, compiler error code, gate name, law id, layer.

Examples:

```text
hash(PATCH_VISUAL, preview_branch_must_preserve_scroll_contract, generated_shell)
hash(ROLLED_BACK, analyzer_timeout_must_not_trigger_writeback, write_stage)
hash(PATCH_RUNTIME, parent_data_widgets_must_not_cross_viewport, layout_emitter)
```

**Runtime novelty** (not vibes):

```text
runtime_root_hash = hash(exception_type, top_flutter_error_kind, generated_file, widget_family, parent_data_type, owning_layer)
```

Cascade errors (e.g. hit-test after ParentData) → same root, not novel.

#### State improvement (escape hatch before STOP)

Same `same_root_hash` twice → **STOP_HUMAN** unless deterministic **state improvement**:

- gate advanced further (e.g. validate ok where it failed before)
- class changed (e.g. PATCH_CODE_EMIT → PATCH_VISUAL)
- `served_build_run_id` became fresh / `fix_proven` true

#### Loop budget (by root)

```yaml
debug_pipeline:
  loops:
    max_fix_attempts: 2                    # emit / llm_repair
    max_repair_retries_per_plan: 2         # OpenCode per plan
    max_diagnose_refinements_per_root: 2
    max_attempts_per_root_law: 4           # across plans on same law
    max_total_candidate_patches: 4
    max_toolchain_retries: 2
    max_check_after_fix: 2
  escalation:
    same_root_hash_repeat_without_improvement: 2  # → STOP_HUMAN
```

#### Review decision routing (agent output → orchestrator)

Review **`reason_code`** maps to **`route`** when `decision=LOOP` (deterministic table — agent picks code, orchestrator validates route):

| `reason_code` | Typical `route` | `decision` when budget left |
|---------------|-----------------|-----------------------------|
| **REVIEW_OK** | `summarize` | **CONTINUE** only |
| **ANTI_PATCHING_VIOLATION** | `plan.revise` | **LOOP** |
| **LAW_NOT_CLOSED** | `diagnose.refine` \| `plan.revise` | **LOOP** |
| **REGRESSION_INTRODUCED** | `repair.retry` | **LOOP** |
| **TEST_COVERAGE_MISSING** | `repair.retry` (tests-only) | **LOOP** |
| **WRONG_LAYER_FIXED** | `plan.revise` | **LOOP** |
| **SCREEN_SPECIFIC_SHORTCUT** | `plan.revise` (reject patch) | **LOOP** |
| **RISK_TOO_HIGH** | — | **STOP** (human) |

When `decision=STOP`: orchestrator skips further loops, runs **summarize** with `escalate: true` and frozen reasoning chain.

When `decision=CONTINUE`: orchestrator verifies check passed + manifest consistent, then **summarize** (archive / handoff).

#### End-to-end state machine

```text
Данные (artifact refresh)
  ↓
Run Gate → FailureClass + case_mode
  ├─ not FRESH_OK / not SCREEN-eligible → FORENSIC or STOP
  └─ FRESH_OK → agent: recognise … repair
        ↓
      check (generate-equivalent stages)
        ↓
      deterministic classify → FailureClass
        ├─ PATCH_CODE_EMIT → fix → check
        ├─ PATCH_CODE_COMPILER → repair.retry
        ├─ PATCH_* / ROLLED_BACK / … → per table
        └─ pass → review
              ├─ decision=CONTINUE → summarize
              ├─ decision=LOOP → route (plan.revise | repair.retry | diagnose.refine | fix…) → budgets
              └─ decision=STOP → summarize (escalate)
```

Shared module: **`failure_class.py`** (§8.0) consumed by `run_gate.py`, `check.py`, `capture_gate.py`, `summarize.py`.

## 9. Два независимых debug/repair flow (doctrine)

| Flow | Entry | Scope |
|------|-------|-------|
| **Compiler / screen** | `/diagnose` → `/repair` | layout, IR, emitter, `.debug/<project>/<feature>/` |
| **Control panel / infra** | `/debug` → `/fix` | Discord, worker, Postgres, imports |

Wizard menu **debug** (OpenCode local) — **третий путь**: local agent repair для экрана, converging к 7-step pipeline.

OpenCode skills `debug`/`fix` в `.opencode/skills/` — для **infra**, не для screen layout.

---

## 10. Сравнение: legacy repair vs planned 7-step

| Legacy (control panel) | Planned 7-step |
|------------------------|----------------|
| CONTEXT → RepairTicket LLM | recognise + inspect → state |
| 5× parallel diagnose agents | **diagnose ×5 panel** (green-tier merge) |
| EVAL + consilium | absorbed into diagnose (+ deterministic gates) |
| plan, build, review | plan, repair, review |
| ticket markdown (CONTEXT) | **summarize:** ticket RU if completed; dev EN always; `data_context.json` if not |
| PUBLISH → GitLab MR | optional; wizard local may skip publish |

---

## 11. Configuration snapshot (local dev)

### `.control-panel.yml` (typical local)

```yaml
repair:
  enabled: false
discord:
  enabled: true
  sync_joined_guilds: true
```

### `.ai-figma-flutter.yml`

Agent behavior, LLM models, `use_screen_ir`, golden capture, etc.

### Secrets (`.env`, not committed)

- `FIGMA_ACCESS_TOKEN`
- `LLM_PROVIDER`, provider API keys
- `OPENROUTER_API_KEY` (OpenCode + optional LLM)
- `OPENCODE_SERVER_PASSWORD` (optional)
- Control panel: `DISCORD_BOT_TOKEN`, `FIGMA_CP_*`, …

---

## 12. Git / working tree notes (2026-06-19)

**Committed on `main`:** compiler fixes, observability, layout work (recent commits).

**Uncommitted / in progress (representative):**

- Wizard debug Phase 1: `debug_agent.py`, `debug/context.py`, `dev/opencode/*`, wizard/menu/check changes, tests
- Control panel: runner errors, generate command tests, config load changes
- `.opencode/skills/debug`, `.opencode/skills/fix` (untracked)
- Many `.debug/` artifact changes (local runs, not product code)

Before consilium: уточнить, merged ли wizard debug Phase 1 в `main` или всё ещё только local working tree.

---

## 13. Open decisions (need product/engineering sign-off)

| # | Question | Options |
|---|----------|---------|
| — | ~~Step outputs format~~ | **Resolved:** machine-readable JSON per step; md only summarize optional |
| — | ~~Post-repair loop~~ | **Resolved:** `check` → route by layer; optional **`fix`** = generate `llm_repair` |
| — | ~~Pre-agent gate~~ | **Resolved:** Run Gate M0 — four runIds, triple stamp, unified §8.10 taxonomy, `case_mode`, `fix_proven` |
| — | ~~Post-repair classifier~~ | **Resolved:** same enum as Run Gate; 0 LLM; `same_root_hash` budget |
| — | ~~Review step role~~ | **Resolved:** `review.decision` = CONTINUE \| LOOP \| STOP; summarize only after CONTINUE or STOP |
| — | ~~recognise vs inspect vs diagnose~~ | **Resolved:** what (recognise) → where/entities+repo (inspect) → why/law (diagnose) |
| — | ~~Agent board vs case_mode~~ | **Resolved:** separate `screen` / `forensic` boards; visual sub-board only on SCREEN when capture verified |
| — | ~~Reasoning chain scope~~ | **Resolved:** cumulative `1…N−1` + `run_context`; not previous-step-only |
| — | ~~Executive vs detail handoff~~ | **Resolved:** `state/<step>.json` in chain; `state/<step>.detail.log` grep-on-demand |
| — | ~~Prompt layout per board/step~~ | **Resolved:** 2 masters + 7 skills (+ board forks); not 14 full prompts |
| — | ~~Capture before review~~ | **Resolved:** explicit **capture** gate after check; visual success ≠ analyze pass |
| — | ~~Fix exhaustion routing~~ | **Resolved:** fix exhausted → **diagnose.refine**; STOP after refinements budget |
| — | ~~OpenCode Plan vs pipeline plan~~ | **Resolved:** Plan mode steps 1–4, 6–7; build only on repair |
| — | ~~Model policy / ensemble~~ | **Resolved:** ×5 recognise, diagnose, review (green-tier panel); ×1 inspect, plan, repair, summarize |
| 1 | **recognise** — vision on `figma.png` or text-only? | **Resolved:** Qwen-VL in panel + figma/capture inputs |
| — | ~~summarize output split~~ | **Resolved:** ticket RU (publish if completed) + dev EN (always); ¬completed → `data_context.json` + status event |
| — | ~~Phase order Run Gate vs Данные~~ | **Resolved:** Data Refresh → Run Gate → agents (§8.0) |
| — | ~~Ensemble at M1~~ | **Resolved:** `ensemble.enabled: false` until M5 (§8.5) |
| — | ~~FailureClass location~~ | **Resolved:** single `failure_class.py` (§8.0) |
| 2 | **Sandbox** implementation | git worktree (like CP) vs temp copy |
| 3 | **Unify** wizard local + control panel repair | shared `dev/opencode/pipeline.py` vs duplicate |
| 4 | **OpenCode session** | one session × 7 steps vs 7 sessions |

---

## 14. How to run (current)

```bash
# Wizard with debug menu
poetry run figma-flutter -i
# → 8. debug → ir-offline | full | offline

# Prerequisites for OpenCode stub
npm install -g opencode-ai   # or Docker profile repair
export OPENROUTER_API_KEY=...
export OPENCODE_BASE_URL=http://127.0.0.1:4096  # optional

# Control panel repair (when enabled)
# repair.enabled: true in .control-panel.yml
# docker compose -f docker-compose.control-panel.yml --profile repair up opencode
```

---

## 15. References

| Resource | URL / path |
|----------|------------|
| OpenRouter Fusion docs | https://openrouter.ai/docs/guides/features/plugins/fusion |
| OpenCode modes (Plan vs Build) | https://open-code.ai/en/docs/modes |
| OpenCode permissions | https://opencode.ai/docs/permissions/ |
| Agent repo layout | `src/README.md` (OpenCode submodule) |
| Repair CP README | `src/control_panel/repair/README.md` |
| Debug doctrine | `.cursor/rules/debug-context.mdc` |
| Wizard debug plan (Cursor) | `.cursor/plans/wizard_debug_menu_*.plan.md` |

---

## 16. Implementation milestones (M0–M6)

Sliced delivery — **do not** implement all 7 agent steps + ensemble in one PR.

| Milestone | Scope | Exit criteria |
|-----------|-------|---------------|
| **M0** | `runId` stamp, `served_run_id_probe`, `run_manifest.json`, Run Gate verdicts, no silent previous build | FORENSIC vs SCREEN routing; rollback overlay |
| **M1** | workspace + manifest + state schemas; recognise / inspect / diagnose **×1** read-only; cumulative `reasoning_chain` | JSON gates pass; `ensemble.enabled: false` |
| **M2** | plan ×1 + repair sandbox ×1; ruff/pytest gates | build mode only touches worktree |
| **M3** | **check** + **fix** loop; **`failure_class.py`** + `same_root_hash` budgets | fix invariants enforced; route to diagnose.refine |
| **M4** | **capture** gate + review **×1** | SCREEN: no CONTINUE without capture |
| **M5** | ensemble **×5** recognise / diagnose / review (`ensemble.enabled: true`) | panel merge → executive JSON |
| **M6** | summarize routing + `data_context` resume; CP refactor to shared pipeline | STOP → status + data_context; CONTINUE → ticket |

**First code files (M0):** `failure_class.py`, `run_gate.py` — before OpenCode agent wiring.

---

*End of state document. Update when Phase 2 (7-step pipeline + check/fix) lands or when control panel repair is enabled in production.*
