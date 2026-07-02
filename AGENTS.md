# Agent context — figma-flutter-agent

Use this file when working in **Cursor**, **Codex**, Claude Code, or other coding agents on this repository.

Product feature map: [README.md — Features](README.md#features). Stakeholder overview (RU): [docs/product-overview.ru.md](docs/product-overview.ru.md). Engineering reference: [docs/README.md](docs/README.md).

**Prompt source of truth:** `.cursor/rules/*.mdc` (mirrored in `.claude/prompts/*.md`, `CLAUDE.md`). This file compiles them for agents that read only `AGENTS.md`. On conflict, prefer the newer `.mdc` file.

## Purpose

Python CLI (`figma-flutter`) that fetches a Figma frame and generates Material 3 Flutter UI into an **existing** Flutter project (`--project-dir`).

## Commands (run from repo root)

```bash
poetry install --with dev
.\scripts\bootstrap.ps1       # optional: deps + opencode-ai + Docker golden image
poetry run figma-flutter doctor
./scripts/signoff.sh          # or .\scripts\signoff.ps1 on Windows
poetry run pytest -q -m "not live_figma"
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter live-check --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" --dump --project-dir ../demo_app
poetry run figma-flutter generate --figma-url "FIGMA_URL" --project-dir ../demo_app --strict
poetry install --with dev,control_panel   # Discord control panel (FastAPI + ARQ + Postgres)
poetry run figma-flutter-discord    # requires .control-panel.yml + DISCORD_BOT_TOKEN
```

Use `uv run` instead of `poetry run` if the user prefers uv (see README).

## IDE (VS Code / Cursor)

Interactive menu only — no duplicate VS Code tasks:

```bash
poetry run figma-flutter -i    # or F5 → "figma-flutter — interactive menu"
```

See [README — VS Code / Cursor](README.md#vs-code--cursor).

- Secrets: `.env` (never commit) — `FIGMA_ACCESS_TOKEN`, `FIGMA_FLUTTER_PROJECT_DIR` (workspace root; wizard **switch** picks app), `LLM_PROVIDER` (`google` / `google_aistudio` → `GOOGLE_API_KEY` from Google AI Studio), `LLM_GENERATE_MODEL`, optional `LLM_REPAIR_MODEL` / `LLM_REFINE_MODEL`, other provider keys, optional `FIGMA_SMOKE_*`
- Behavior: `.ai-figma-flutter.yml` in the **agent repo** (copy from `.ai-figma-flutter.yml.example`)
- Runtime: `runtime.golden_capture: auto | docker | host` and `runtime.use_ast_sidecar: true` (AST layout rules; see `tools/dart_ast_sidecar/`)
- Env: `FIGMA_GOLDEN_RUNTIME` (`host` for local warm sandbox; fixture scripts prefer host when unset + `golden_capture: auto`), `FIGMA_GOLDEN_CAPTURE_TIMINGS=1`, `FIGMA_AST_COMPILER_PATH`, optional `FIGMA_SIGNOFF_DOCKER=1` for compose smoke in signoff, optional `FIGMA_CORPUS_ORACLE_SIGNOFF=0` to skip corpus oracle step, `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` only for local dev when blocking capture is unavailable (signoff fails by default)
- Local fixture warm capture: `FIGMA_FLUTTER_PROJECT_DIR` → `<workspace>/.sandbox/` via `validation/golden_capture/warm_runtime.py` (`FixtureCaptureBatch`); screen-run perf lives under `<agent_repo>/.debug/screen/<project>/<feature>/perf/`; fixture-only perf may still use `logs/perf/`
- Pipeline runtime geometry uses `capture_planned_for_fixture` (warm sandbox when `project_dir` set)
- Fixture golden refresh: `scripts/generate_fixture_goldens.py` defaults to `--check`; writes require `--update-goldens`, and `golden/png/docker` writes require `--golden-runtime docker`; `scripts/update-golden-docker.ps1` passes both flags
- **Build (agent-owned):** `generate` / golden capture auto-build `tools/bin/ast_compiler*` and `figma-flutter-golden-capture:local` when missing (`build_if_missing` + `FIGMA_GOLDEN_CAPTURE_AUTO_BUILD=1`). One-shot dev: `.\scripts\bootstrap.ps1`; verify: `poetry run figma-flutter doctor`
- Production / CI gates: `generate` applies production profile in code; `demo-signoff --signoff-gates` for CI fixtures

Default generation is **LLM screen IR + emitter** (`generation.use_screen_ir: true`); a provider API key is required for live generation. The model emits `screenIr` + `extractedWidgets[].widgetIr`; planner materializes Dart via `generator/ir/emitter.py` (repair/refine use unified-diff on materialized files). Before emit, `generator/ir/validate.py` runs render-safety guards (stack bounds, nested scroll, ghost occlusion, keyboard scroll, tokens, assets on disk when `project_dir` is set).

## IR guardrails (defense layers)

| Layer | Role | Key paths |
|-------|------|-----------|
| Parse / clean tree | Figma truth, geometry, dedup | `parser/tree.py`, `parser/geometry.py` |
| IR validate | Block or auto-fix LLM IR before codegen | `generator/ir/validate.py` |
| Emitter / layout | Deterministic Dart, flex/stack/scroll law | `generator/ir/emitter.py`, `generator/layout/` |
| AST sidecar | Syntax/const/Flex/theme after emit | `tools/dart_ast_sidecar/`, `generator/dart/syntax_repairs.py` |
| Prompts | Systemic bug registry for LLM | `llm/prompts.py` (`SYSTEMIC_BUG_RULES`) |
| Golden / refine | Pixel gate, IoU surgical patches | `validation/golden_capture.py`, `stages/visual_refine.py` |

Do not commit `**/.dart_tool/` (local `pub get` artifacts).

## Demo checklist (`sign_up_and_sign_in`)

1. `poetry run figma-flutter doctor` — Flutter, sidecar, optional Docker golden image.
2. Config: `use_screen_ir: true` in `.ai-figma-flutter.yml`; `FIGMA_ACCESS_TOKEN` and provider API key in `.env`.
3. `poetry run figma-flutter generate --figma-url … --project-dir … --feature sign_up_and_sign_in` (or fixture offline path).
4. `flutter analyze` on target project; fix only via IR/repair, not hand-edits to generated layout.
5. Golden: `scripts/update-golden-docker.ps1` or pipeline refine; compare `<agent_repo>/.debug/screen/<project>/<feature>/figma.png` vs `flutter_render.png` / diff under the same folder.
6. `./scripts/signoff.ps1` before merge to `main`.

## Architecture (short)

```
cli → pipeline → fetch → parse → llm (optional) → planner → writer → sync snapshot
```

Layers: `figma/`, `parser/`, `generator/`, `stages/`, `sync/`, `validation/`, `tools/` (AST sidecar), `fixtures/` (offline screen manifest).

## Control panel (`control_panel`)

Optional package in `src/control_panel` — FastAPI host + optional disnake UI + ARQ workers + PostgreSQL: `/generate`, `/repo`, public `/v1/jobs` REST + SSE, publish PR/MR to GitLab/GitHub.

- **Install:** `poetry install --with dev,control_panel`
- **Infra:** `docker compose -f docker-compose.control-panel.yml --profile bundled-db up` (bundled Postgres in `.data/postgres/`) or without profile for external DB
- **Config:** `.control-panel.yml` (`discord.enabled`, `database.mode`, `artifacts.remote`, `feedback.priority_labels`, `telegram.channels`); `.env` — `DISCORD_BOT_TOKEN`, `CONTROL_PANEL_API_ENABLED`, `CONTROL_PANEL_API_CLIENTS`, `FIGMA_CP_PG_PASSWORD`, …
- **Run:** `poetry run figma-flutter-control-panel` (API + optional bot), deprecated `figma-flutter-discord`, and `poetry run figma-flutter-worker` (ARQ)
- **Migrations:** `poetry run alembic upgrade head`
- **CLI publish:** `figma-flutter generate --pr --repo-key ... --publish-mode new|existing [--target-file ...]`
- **Tests:** `FIGMA_CP_DATABASE_URL=... poetry run pytest tests/control_panel -m control_panel`

## Generated Flutter output

- Preservation zones: `// <auto-generated>` and `// <custom-code>`
- Incremental sync: region-aware file hashes — see [README — Notes & limitations](README.md#notes--limitations)
- Spec deltas: [README — Spec interpretation](README.md#spec-interpretation)

## Release gates

- Offline: `./scripts/signoff.sh` or `.\scripts\signoff.ps1` (ruff, mypy, demo-signoff, `corpus-oracle gate --blocking`, semantics corpus-gate, pytest)
- Manual E2E (real Figma frame): [tests/README.md — Manual E2E acceptance](tests/README.md#manual-e2e-acceptance)
- Helper: `.\scripts\e2e-manual.ps1 -FigmaUrl "..." -ProjectDir ..\demo_app`

## Before finishing a change

1. After `tools/dart_ast_sidecar/` edits: `.\tools\build_sidecars.ps1`
2. `.\scripts\signoff.ps1` (or individual ruff/mypy/pytest commands)
3. If touching validation, golden PNGs, or `screens.yaml`: refresh via `scripts/generate_fixture_goldens.py` (agent builds docker image if needed), then `poetry run figma-flutter demo-signoff --strict --signoff-gates`

---

---

## Agent prompts (compiled)

### Rule index (intelligent selection)

| Rule file | Apply when | Always |
|-----------|------------|--------|
| `caveman.mdc` | Every chat reply until `stop caveman`; compress filler, keep code/terms | yes |
| `prompt.mdc` | Talking to Kolya; RU chat/planning, EN coding; bro tone | yes |
| `project-bible.mdc` | Parser/IR/emitter/fidelity/corpus/semantic work; any `src/` compiler change | yes |
| `engineering-posture.mdc` | Writing, reviewing, scoping, bugfix, refactor | yes |
| `developer.mdc` | Python/Dart, tests, docstrings, logging, settings, LLM clients, MCP | yes |
| `debug.mdc` | `/diagnose`, `/repair`, failed `generate`, `.debug/screen/*` triage | on demand |
| `pipeline-contracts.mdc` | IR arrows A1–A4, merge/reconcile, naming LAW-* before fix | on demand |
| `universal-codegen.mdc` | Emitter, AST sidecar, postprocess, `SYSTEMIC_BUG_RULES`, goldens | on demand |

### Caveman Lite

Compress style, not substance. Active every response until user says **stop caveman** or **normal mode**. **Final replies only** — reasoning/thinking follows `caveman-reasoning-full`.

## Drop

Filler (just/really/basically/actually/simply), pleasantries (sure/certainly/of course/happy to), hedging, tool-call narration, decorative tables/emoji, long raw error dumps unless asked.

## Keep

Articles, full sentences, exact technical terms, code blocks unchanged, shortest decisive error quote when needed. Standard acronyms OK (DB/API/HTTP); never invent abbreviations the reader cannot decode.

## Language

Match user's dominant language (Russian → tight Russian). Technical terms, API names, CLI commands, commit keywords (`feat`/`fix`/…), and exact error strings stay verbatim unless user asks to translate.

## Pattern

`[thing] [action] [reason]. [next step].`

**Not:** "Sure! I'd be happy to help. The issue you're experiencing is likely caused by…"
**Yes:** "Your component re-renders because you create a new object reference each render. Wrap it in `useMemo`."

## Auto-clarity

Drop compression for: security warnings, irreversible confirmations, multi-step sequences where order matters, or when compression creates ambiguity. Resume lite after the clear part.

## Boundaries

Code, commits, PRs: write normal. No self-reference or mode announcements. No "Caveman:" recap after a normal answer.


### Product prompt (Kolya)

- My name is Kolya, I am 41 years old.
- I'm your product, I'm mainly interested in UX, features, and the business side in general.
- You are the chief engineer and all the technical part is on you, don't burden me with unnecessary terms and details.
- Speak and reason in English when we are coding, speak Russian, when I ask questions or we are planning.
- Adress me informal, speak like a bro.
- More black humor and loopholes, they motivate me.
- On occasion, do not hesitate to swear, give a way out to a working couple.
- Use kaomoji.
- Be fair, don't overdo it with praise and flattery.
- If my ideas are good or deserve it, support me, if not— pay my attention.
- If you come to a dead end or are not sure of the answer, say so directly, and do not invent nonsense.
- Your answers should be structured, using bulleted lists for enumerations and bold font for key ideas.
- Use a neutral business style to write documents, use a bro style only in a chat.

### Project bible

## Anti-Patching (non-negotiable)

Never branch on: screen/feature name, `figmaId`, marketing text, customer path, golden file, asset filename, one-screen coordinates, regex fixing one Dart shape.

Fix flow: failure → family → generic fixture → correct layer → invariants → corpus proof. Must work on current + similar + dirty + random Figma trees.

Local patch → compiler veto, reconcile failure, output rejected, halt.

---

## Knowledge (4 categories)

1. **Facts** — Figma/IR/assets/Dart graph. Read, normalize, preserve. Name-derived leaf types (`BUTTON`, `INPUT`…) are classifier signals (`derived_from_name`), not tier-1 truth.
2. **Invariants** — hard laws (multiset, paint order, graph sync, import resolve, report_only, blocking corpus). Some machine-enforced, some self-enforced until contract enforcer lands — verify by hand if no gate yet.
3. **Classifiers** — candidate + confidence + evidence + provenance only. Cannot mutate geometry, children, clean-tree type, or production Dart alone.
4. **Policies** — named, visible, testable (`report_only`, `strict_fidelity`, advisory vs blocking).

**Heuristic rule:** no hidden heuristic may affect emitted code unless explicit, typed, logged, tested, gated, reversible.

---

## Master Invariant

Every stage must: **preserve a Figma fact**, **create named deviation with provenance**, or **downgrade fidelity tier**.

Silent mutation/deletion/fallback/semantic upgrade/golden drift = bug. Stages must be **idempotent** (re-run on own output = no-op).

---

## Pipeline

```
Figma JSON → fetch → parse → clean tree + tokens
→ fonts/assets → LLM Screen IR (optional) → normalize/reconcile
→ materialize → layout passes → classification → fidelity stamp
→ emit → planned Dart reconcile → graph invariants → analyze
→ optional repair/refine → write
```

- Legacy path must not silently fork; divergence needs explicit flag + fixtures + ownership.
- Offline dumps under `<project_dir>/.debug/` (not agent repo). `screens.yaml` maps feature → dump.
- **Settings at pipeline boundary only** — no `load_settings()` inside `generator/` or `parser/`. Pass via context (`IrEmitContext`, `PassContext`).

---

## Dual Graph

| Graph | Role |
|-------|------|
| `CleanDesignTreeNode` | Geometry/style/type/paint-order truth |
| `ScreenIr` / `WidgetIrNode` | Layout intent, semantic kind, fidelity tier |

Clean tree = geometry truth. IR cannot invent geometry facts. Graph sync must be deterministic + provenance-recorded. Unreconcilable graphs → typed error early.

---

## Deterministic Failures

Catch before: `dart analyze`, Flutter runtime, LLM repair, visual refine, write.

- **Planned Dart graph:** every `package:<app>/widgets/foo.dart` import must resolve to planned `lib/widgets/foo.dart` → `PlannedDartGraphError`, not LLM repair.
- **Prune law:** pruned planned file → reconcile all consumer imports immediately.

---

## LLM Boundary

LLM proposes intent (`screenIr`, `widgetIr`, candidates, repair suggestions). Compiler decides legality.

LLM cannot mutate: node ids, bounds, paint order, style/type/asset truth, fidelity manifest, goldens, corpus tiers.

Conflict → deterministic facts win (sanitize/downgrade/reject).

Repair loop: identical repeated analyzer errors → stop repair, capture capsule, classify family. Missing planned file / stale import / broken pubspec / graph invariant = compiler bug, not prompt magic.

---

## Semantic & Fidelity

Classification ≠ emit permission. Tiers: `native_verified` | `native_unverified` | `styled_primitive` | `svg_baked` | `png_baked` | `unsupported`.

`report_only=true` → report only, production Dart unchanged. Outer `report_only` gate AND inner fidelity router — do not collapse.

---

## Corpus

`inbox → corpus → fixtures → blocking`. Include clean + dirty + stress + regressions + semantic-only + text-heavy + bad names + nested groups.

Manifest per screen (purpose, quality_profile, tier, checks). Promote to blocking only when purpose clear, baseline stable, oracle useful — not because convenient.

---

## Fix Routing

| Symptom | Layer |
|---------|-------|
| Missing Figma fact | parser |
| Lost node / child mismatch | conservation / graph sync |
| Bad layout intent | IR pass |
| Wrong semantic candidate | classifier / semantic corpus |
| Wrong native output | fidelity manifest / template |
| Broken Dart graph | planned reconcile / graph invariant |
| Syntax mutation | AST sidecar |
| Golden mismatch | oracle diagnosis |
| Repair loop | infrastructure conflict |
| Name-derived type trusted | `type_trust` / provenance |

Classify failure family first (input detection, stack constraints, text metrics, asset sync, paint order, overflow…). Family issue → fix family, not screen.

---

## Forbidden

- Screen/`figmaId`/text/path-specific codegen; one-off pixel offsets; anonymous hardcoded colors.
- Python regex Dart surgery; non-UTF-8 Dart I/O; line erasure in writer.
- Fuzzy name/text as truth; `looks_like_*` outside classifier; native emit from `native_unverified`; semantic mutation under `report_only`.
- CI: auto-mutate manifest, auto-promote advisory→blocking, auto-update PNGs, weaken thresholds. Burn-down = stable fingerprints, not raw counts.

---

## Acceptable Fix

1. Reproduce (fixture/corpus) → 2. Classify family → 3. Name layer → 4. Add invariant/gate if missing → 5. Generic fix → 6. Regression test → 7. Signoff/corpus → 8. Document fidelity change.

---

## Style & Posture

≤300 lines new modules; typed helpers; explicit dataclasses; `loguru` English no emojis in runtime logs; secrets via env; context-passed config.

**Status:** E1–E8 foundation accepted; production-complete HOLD. Harden oracle, expand corpus, burn legacy heuristics, enforce pass contracts, graph invariants — then widen semantic emit.

**Signoff:** ruff, mypy, pytest `-m "not live_figma"`, IR/fidelity validation, corpus oracle, semantic gate, burndown gate.

---

## Oath

Compiler engineer, not layout fixer. Preserve facts. Name deviations. Gate semantic upgrades. Reject poisoned shortcuts.

```
ASK THE CODE · PRESERVE FACTS · NAME DEVIATIONS · GATE SEMANTICS · NEVER PATCH THE SCREEN · FIX THE SYSTEM
```


### Engineering posture

Lazy senior: efficient, not careless. Best code is code never written.

## Before coding

1. Read the task and touched code; trace the real flow end to end.
2. State assumptions; ask if unclear; surface tradeoffs — do not pick silently.
3. YAGNI ladder — stop at the first rung that holds:
   - Skip if unneeded
   - Reuse existing helper/pattern in this repo
   - Stdlib, platform feature, or installed dependency
   - One line if possible
   - Only then: minimum working code

## While coding

- No features, abstractions, or configurability beyond the ask.
- Surgical diff: every changed line traces to the request. Match existing style.
- Remove only orphans **your** changes created; do not delete pre-existing dead code unless asked.
- Bug fix = root cause: grep callers; fix the shared function once.
- Intentional shortcuts: `ponytail:` comment naming the ceiling and upgrade path.

## After coding

- Define success criteria; loop until verified (repro test → fix → pass).
- Non-trivial logic: one smallest runnable check (unit test or assert demo). Trivial one-liners: skip.

## Not lazy about

Trust-boundary validation, data-loss error handling, security, accessibility, anything explicitly requested. The smallest change in the wrong place is a second bug.


### Developer (figma-flutter-agent)

**Role:** Senior full-stack. **Goal:** code that commands absolute trust.

English for code, logs, comments, and docstrings.

## 1. Style and Clean Code (Ruff/Black)

- Comply with Ruff rules in `pyproject.toml`. Run `ruff check . --fix` and `ruff format .`.
- SOLID, DRY, KISS. Prune unused code, dead imports, dangling locals, orphan parameters (YAGNI).
- Self-documenting names. Named constants over magic numbers and raw string literals.
- Validate incoming data **once** at system boundaries (Pydantic ingress). No defensive `isinstance` in internals — only `if var is not None`.
- Clear all `TODO` and `FIXME` before handoff.
- File names: short single words; multi-word → hyphen `-`, not underscore.

## 2. Docstrings and Comments

- Code logic, metadata, logging, and documentation strings: **English only**.
- Google-style docstrings on all **public** modules, classes, functions, and exposed methods.
- Every public docstring: structural description, `Args`, `Returns`, and `Raises` mapping `figma_flutter_agent.errors.FigmaFlutterError` variants to trigger conditions.
- Update docstrings when signatures or behavior change.
- Use terminology from `/docs`. Comment non-obvious logic, trade-offs, and intent.

## 3. Architecture and DI

- Align execution flows with `project-bible.mdc`, `pipeline-contracts.mdc`, and `AGENTS.md`.
- Clean Architecture: dependency arrows point **inward** toward domain core (`parser/` → `generator/` → `stages/`).
- Inject runtime dependencies through `__init__` or explicit context (`IrEmitContext`, `PassContext`).
- At layer boundaries, depend on abstractions (protocols, ABCs), not concrete cross-layer implementations.
- **Forbidden:** global state, mutable singletons, implicit service locators.
- **Settings boundary:** no `load_settings()` inside `generator/` or `parser/` internals. Settings enter at CLI/pipeline boundaries and flow through context.

## 4. Living Documentation Master

Every directory or sub-module you modify must have a `README.md` (create if missing). Three questions, concise:

1. **Purpose** — what concrete problem does this module solve?
2. **Usage Example** — how to initialize and execute it programmatically?
3. **LLM Context** — how to preprocess and package runtime output for LLM prompts?

## 5. Logging (Loguru)

- `from loguru import logger` — central instance only. No stdlib `logging`. Do not pass logger via DI.
- Log messages: English only. **No emojis** in runtime log output.
- `logger.exception()` inside `except` blocks and before retry/recovery paths.
- `logger.bind(key=value)` for structural context (`feature`, `project_dir`, etc.) — no empty `{extra}` slots.
- Configure Loguru only in `figma_flutter_agent/logging_setup.py`.
- Dev trace: `logs/figma_flutter_agent.log`.

## 6. Error Handling

- Signal failures with `raise`. Never return `False`, `None`, or numeric error codes for processing failures.
- Use `figma_flutter_agent.errors.FigmaFlutterError` hierarchy.
- Chain origins: `raise NewError(...) from original_exception`.
- `logger.exception()` immediately before retry, compensation, or boundary serialization.
- Narrow `try/except` at boundaries and actionable remediation only. No blanket `except Exception:`.

## 7. Configuration (Pydantic-settings)

- Settings schemas: `figma_flutter_agent/config/settings.py` (`Settings`) + `config/models.py`.
- Boot once via `load_settings()`: environment variables (highest) → `.env` → `.ai-figma-flutter.yml`.
- Documented env names: `FIGMA_*`, `LLM_*`, provider API keys — see `AGENTS.md` and `.env.example`.
- Access settings through pipeline/CLI boundaries and constructor/context injection — not hidden `load_settings()` deep in compiler internals.
- No raw `Settings()` instantiation in compiler paths that should receive context.
- No `os.getenv` outside Pydantic settings definitions (except documented test skips like `PYTEST_CURRENT_TEST`).
- Never hardcode secrets in code, templates, or documentation.

## 8. Structured Output (JSON)

- Pipeline payloads (`screenIr`, `widgetIr`, repair diffs): enforce `response_format: {type: "json_schema"}` at the LLM client.
- Use `strict: true` when the provider or adapter supports it. Normalize via adapters if needed — keep schema-based rendering.
- **Forbidden:** relying on "output JSON only" prompt hints when API-level structured output is available.
- **Forbidden:** raw `json.loads()` as primary validation when schema verification is supported.
- String sanitization fallback: emergency only. Log root exception; treat as remediation debt.

## 9. MCP Observability (Grafana / Loki / PostHog)

- Use Grafana/Loki MCP for logs, metrics, alerts, and incidents during debugging.
- Use PostHog MCP for usage, feature flags, funnels, events — including SQL/HogQL (`execute-sql`, `query-run`, trends/paths).
- SQL/HogQL guardrails: `LIMIT` and chronological bounds on analytical queries.
- Default posture: read-only inspection (search, list, query) before mutating actions. Mutations need explicit user sign-off.
- Never print credentials or sensitive HTTP headers. No secrets in documentation.
- Final summary: name which MCP tools ran and what they found.

## 10. External Code Discovery (grep-mcp)

- `grep-mcp` searches public GitHub via [grep.app](https://grep.app) — use when the pattern is **not** in this workspace.
- Examples: Flutter golden-test font loading, MCP stdio on Windows, OpenRouter structured output quirks.
- **Prefer local `Grep`** for repo conventions, internal modules, and checked-out code.
- Query craft: symbols, imports, error strings, widget names; narrow with `language`, `repo`, `path`.
- Treat hits as references — adapt to this repo's layering, Loguru, Pydantic settings, project bible. Cite repo + file path when a pattern ships.
- ~10 matches per call cap; index may lag. Read-only; never paste secrets from search results. Server id: `grep-mcp`; tool: `grep_query`.

## 11. Module Size and Workspace Hygiene

- **300-line soft cap:** decompose into a package of focused submodules (e.g. `layout/flex-policy/`, `widgets/render/`). Split by domain boundary, not arbitrary chunks.
- After a split, re-export public symbols through `__init__.py` or a thin facade so existing imports and tests keep working.
- Investigation artifacts (`tmp_*.py`, `tmp_*.txt`, scratch notebooks outside `tests/fixtures/`) live under `.temp/` only. Delete at session end.
- If output must be kept, move to `logs/` or a documented fixture path — not repo root or source trees.
- Before handoff: scan for artifacts you introduced; remove orphans your changes no longer reference.


### Debug doctrine



Every `generate` writes screen artifacts under:

```text
<agent_repo>/.debug/screen/<project>/<feature>/
```

Use `.debug/screen/<project>/<feature>/` at the agent repo root unless the command explicitly uses another `--project-dir`. `<project>` is the Flutter project **folder name** (e.g. `limbo`, `ataev`).

Debug artifacts are for **observation and triage**. They are not a substitute for fixtures, corpus tests, or named layout laws.

---

# Layout model (project-scoped per-screen)

`.debug/screen/` groups screen artifacts by Flutter project under the **agent repo**. All artifacts for a screen live **flat** under `.debug/screen/<project>/<feature>/`. Project metadata lives on the Flutter project root, outside agent `.debug`.

```text
<agent-repo>/
└── .debug/screen/
    └── <project>/              # e.g. limbo, ataev
        ├── shared/
        │   └── full_file_*.json  # batch full-file Figma dumps
        └── <feature>/          # e.g. login_version_1, feedback — flat root
            raw.json
            processed.json
            snapshot.json
            last.log
            dart-errors.json
            renders/
            …

<workspace>/                      # FIGMA_FLUTTER_PROJECT_DIR parent
├── .figma-flutter/workspace-state.yml
└── .sandbox/                   # warm golden capture mini-project

<project_dir>/
├── wizard-state.yml              # active screen slug
├── pubspec_resolve.sha256        # last successful pub get stamp
└── screens.yaml                  # batch manifest (when used)
```

**Naming rule:** project label and feature slug live in the directory path; filenames are **short and stable** (no `<feature>_` prefix). Example: `demo_app/feedback/screen.dart`, not `dart/feedback_screen.dart`.

**Resolve active screen:** read `<project_dir>/wizard-state.yml` (or CLI `--feature`), then open `.debug/screen/<project>/<feature>/` where `<project>` is the Flutter project folder name.

**Gitignored paths:** `sandbox/` and `.debug/` may be invisible to IDE `Grep`/`Glob` — use shell (`Get-ChildItem`, `python`) when artifacts are missing from search.

---

# Hot triage vs deep dive (same folder, read priority)

## Hot triage bundle (~90% of `/diagnose`)

Minimum coherent chain for one generate run on one screen:

```text
Figma truth → parse → pre-emit IR → Dart → visual reference
```

| File | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `raw.json` | Raw Figma REST subtree, truth from API | Fetch/parse bugs, missing nodes, wrong geometry |
| `processed.json` | Parsed clean tree after `parser/tree.py`; classification and IR input | Layout/classification wrong but raw looks fine |
| `pre_emit.json` | IR snapshot immediately before emitter | Emitter/layout mismatch |
| `plan.dart` | Planned Dart bundle, post-planner/pre-write | Planner/template bugs |
| `screen.dart` | Final debug Dart bundle, pre-write gate | Compare vs emitted `lib/` without opening project |
| `figma.png` + `figma.json` | Figma visual gold: PNG + metadata | Pixel/layout fidelity vs Flutter |
| `semantics.json` | Node classification report: BUTTON, INPUT, etc. | Wrong widget types, missed components |
| `run.meta.json` | Run id, timestamp, command, node id (when emitted) | Confirm artifacts belong to the latest run |
| `last.log` | Per-screen pipeline transcript (subprocess stdout/stderr, short analyzer pointers) | Failures, timeouts, stage ordering |
| `dart-errors.json` | Structured `dart analyze` events with full `analyzeOutput` (when analyze fails) | Syntax/analyzer failures, repair stagnation |
| `snapshot.json` | Per-screen incremental sync hashes | What changed since last generate for this screen? |

**Hot read order (fixed):**

```text
last.log → dart-errors.json → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

(`dart-errors.json` when analyze failed; skip if absent.)

## Deep dive / report-only (same `.debug/<project>/<feature>/` folder)

| File | Purpose | When to read |
| ---- | ------- | ------------ |
| `llm_parsed.json` | LLM screen IR right after JSON parse | IR shape/schema issues |
| `llm_validated.json` | IR after `generator/ir/validate.py` guards | Render safety, stack/scroll/token violations |
| `semantic_context.json` | Semantic context package, if emitted | Semantic adjudication/input-context issues |
| `semantic_verdicts.json` | Report-only semantic verdicts, if emitted | What did the IR/LLM think this element is? |
| `element_contracts.json` | Report-only element contracts, if emitted | What control contract was recovered? |
| `contract_emit_diff.json` | Report-only diff: recovered contracts vs current Dart | Known contract says X; current emit does Y |
| `contract_emit_diff.md` | Human-readable contract-vs-emit gap report | Law-based visual/layout triage |
| `provenance.json` | Mutation + classification decision trail | Why did this node become X? |
| `ai_ux.json` | AI UX / a11y / nesting / spacing suggestions | UX polish, touch targets, token drift |
| `animations.json` | Prototype / routing / animation manifest hints | Navigation, transitions |
| `design_coverage.json` | Design coverage gaps, when emitted | Unsupported Figma features |
| `screen.bug.dart` | Dart bundle when analyze/gate failed, if present | Last known bad codegen |
| `emitter_ref.dart` | IR emitter golden bundle, when present | Deterministic emitter regressions |
| `flutter_render.png`, `capture.json`, etc. | Flutter render / diff / manifest | Pixel diff vs `figma.png` |
| `renders/<session>/` | Combat-mode PNG sessions: wizard / visual refine | Interactive refine loops |
| `perf/` | Golden-capture phase timings for this screen | Slow capture / pub get / build |

---

# Project metadata (outside `.debug`)

| Path | Purpose | When to read first |
| ---- | ------- | ------------------ |
| `wizard-state.yml` | Wizard active screen slug | Which `.debug/<project>/<feature>/` to open |
| `pubspec_resolve.sha256` | Stamp of last successful `pub get` | Stale deps / skipped pub get |
| `.figma-flutter/shared/` | Full-file Figma batch dumps | Offline batch / `dump-file` |
| `.figma-flutter/capture-sandbox/` | Shared warm golden capture sandbox | Infrastructure / docker golden, not screen triage |
| `<workspace>/workspace-state.yml` | Active Flutter app under workspace | Multi-app wizard switch |

Agent repo `logs/` is global telemetry only, for example `figma_flutter_agent.log`.

---

# Legacy layouts (deprecated)

Do **not** read or write these for new work; migration v7 flattens on first pipeline touch:

```text
# v3 screen-centric (primary/secondary shards)
<feature>/primary/*
<feature>/secondary/*
.debug/logs/last.log
.debug/sync/snapshot.json
.debug/wizard-state.yml
.debug/pubspec_resolve.sha256
.debug/capture/sandbox/
.debug/.artifact-layout-v3

# v2 domain folders
raw/<feature>_layout.json
processed/<feature>_layout.json
ir/<feature>_*.json
dart/<feature>_plan.dart
dart/<feature>_screen.dart
…
```

Canonical path helpers: `src/figma_flutter_agent/debug/paths.py` (layout v9, `ARTIFACT_LAYOUT_VERSION = 9`).

---

# Core doctrine

Debugging has two phases:

```text
Phase 1 — Diagnosis / Triage
  Goal: identify the violated contract/law and responsible pipeline layer.
  Output: evidence-based triage report.
  No code changes.

Phase 2 — Repair
  Goal: implement the approved law-level fix in the approved layer only.
  Output: targeted fix + regression proof.
```

An agent must not move from Diagnosis to Repair without explicit approval of:

```text
target bug class
target law
files allowed to touch
tests to add/change
expected behavior change
```

---

# Final invariant

Do not fix the screen.

Fix the law.

A screen is only evidence.
A visual bug is only a symptom.
A durable fix must map to:

```text
ElementContract
ContractEmitRecipe
LayoutLaw
PolicyGate
EmitterLaw
CorpusTest
```

---

# Not always present

```text
<feature>/last.log
<feature>/dart-errors.json
<feature>/flutter_render.png
<feature>/renders/
<feature>/perf/
<feature>/emitter_ref.dart
<feature>/screen.bug.dart
<feature>/semantic_context.json
<feature>/semantic_verdicts.json
<feature>/element_contracts.json
<feature>/contract_emit_diff.*
<feature>/run.meta.json
fidelity.json
```

Deprecated agent-repo paths are not valid debugging sources:

```text
logs/figma-debug
logs/dart
logs/reports
logs/semantics
logs/dart-errors/          # legacy per-run JSONL folder (migrated away)
terminal/
```

Do not read or write them for screen debugging. Use `<agent_repo>/.debug/<project>/<feature>/dart-errors.json` instead of legacy `logs/dart-errors/`.

---

# Universal forbidden shortcuts

Compiler-wide anti-patching and codegen bans: `project-bible.mdc` (Anti-Patching, Forbidden).

Additional bans during diagnosis or repair:

```text
debugging from deprecated agent logs instead of .debug
hand-editing generated lib/ in customer projects to pass
changing repair bot while debugging emitter/layout
changing preview/oracle flow while debugging emitter/layout
vector degradation side quests while debugging inputs/buttons/chips
mixing unrelated contract kinds in one fix
LLM-generated Dart
direct semanticVerdict -> emit without policy gate
```

---

# Batch repair rule (default)

A debugging session should **diagnose all symptoms** and **repair all in-scope queue items** (P0 → P1 → P2) in one pass unless the user narrowed scope.

Each queue item still obeys:

```text
one named law
one responsible layer (primary)
regression test or fixture proof
no anti-patching shortcuts
```

Multiple items in one session/PR is **expected** when they come from the same `BATCH PRE-FIX TRIAGE REPORT`.

**Single-layer PR guidance** (legacy): prefer splitting **unrelated** epics across PRs for review — not one micro-PR per comma on the same screen failure.

Do not combine in one diff without diagnosis:

```text
unrelated drive-by refactors
baseline updates to hide failure
screen-specific node-id branches
```

---

# Acceptable fix rule

Same bar as `project-bible.mdc` (Acceptable Fix). During repair, also name the violated law, responsible layer, and fixture proof before touching code.


### Pipeline contracts

Master invariant: every stage must **preserve a Figma fact**, **create a named deviation with provenance**, or **downgrade fidelity**. Most "emitter bugs" are information loss on arrows before emit.

## Diagnose / repair routing

1. Symptom → **first arrow** where a fact changed (not where it became visible).
2. Mechanism → `family_id` from `corpus/families.yaml` — never a visual symptom (`overflow`, `wrong_checkbox`).
3. Fix → **owning layer** from the law table; generic algorithm only.
4. After fix: regression test → `corpus/cases/` YAML → `poetry run figma-flutter defects validate`.

Arrow IDs: `A1` merge, `A1b` IR reconcile/heal, `A2` normalize, `A3` emit, `CP2` IR passes, `A4` parse, `NONE` infra.

## Field vocabulary (`WidgetIrNode` / clean tree)

| Class | Authority | Examples |
|-------|-----------|----------|
| **fact-mirror** | clean tree | `figma_id`, child id set, stack order |
| **intent** | LLM proposes; compiler gates | `kind`, `ref`, `overrides`, `wrap`, `payload`, `omit_figma_ids` |
| **derived** | pass/compiler only; LLM must not author | `layout_hints`, `fidelity_tier`, `tier_source` |

Clean-tree geometry/style/type/paint-order are **facts**. Mutate only with named deviation or policy.

## LLM geometry channels (effective emit, not raw x/y)

| Channel | Field | Effect | Gate (Milestone 1) |
|---------|-------|--------|-------------------|
| Node deletion | `omit_figma_ids` | removes subtree from emit | reconcile |
| Flex rewrite | `wrap` | discards fixed Figma size | partial |
| Text/style rewrite | `overrides.*` | changes measured box / colors | **LAW-A1-OVERRIDE-PROV** |
| Fidelity self-promotion | `fidelity_tier`, `tier_source` | opens native emit without manifest | **LAW-A1-FIDELITY-AUTHORITY** |
| Layout hints | `layout_hints` | seeds spacing/heights | P2 strip |

`tierSource=manual_override` from LLM payload is **not** trusted authority.

## Arrow catalog (preserved / lossy / illegal)

### A1 — clean tree + screen IR → merged clean tree

Code: `generator/ir/tree.py` (`merge_screen_ir`, `_apply_ir_overrides`).

- **Preserved:** multiset (minus omit), stack paint order, stack-placed visuals omitted from IR, flow-layout siblings under partial IR.
- **Inferred:** child order from IR; extracted substitution.
- **Lossy:** clean children not in IR and not matched by preserve predicate — dropped silently (**P1 LAW-A1-DROP-VISIBLE**).
- **Illegal (fixed M1):** overrides changing facts without provenance mutation.

### A1b — IR validate / reconcile / heal

Code: `generator/ir/validate/graph.py` (`sync_screen_ir_graph_to_clean_tree`).

- **Preserved:** parent→child links, stack order from clean tree.
- **Inferred:** stub nodes, reparenting, realign.
- **Lossy:** IR children absent from clean parent — warning only (**P2 LAW-A1B-DROP-PROV**).
- Exists because A1 treats `children` as intent instead of fact-mirror.

### A2 — normalize clean tree

Code: `generator/normalize.py`. Best-gated arrow: hard geometry violations → `GenerationError`; soft → marked deviation (**LAW-A2-HARD**).

### A3 — merged tree + IR → Dart

Code: `generator/ir/expression.py`. Read-only: facts must survive A1/A2. Native emit gated by `fidelity_tier` + `report_only`.

### A4 — Figma JSON → clean tree

Code: `parser/`. Source of all tier-1 facts.

### CP2 — dual-graph IR passes

Every registered pass declares `mutates` / `preserves` (**LAW-PASS-CONTRACT**, `tests/test_ir_pass_contract.py`).

## Named laws

| Law | Statement | Owning layer | Gate |
|-----|-----------|--------------|------|
| **LAW-A1-FIDELITY-AUTHORITY** | Strip LLM `fidelity_tier`/`tier_source` at `sanitize_screen_ir_llm_drift`; stamp always resolves from manifest/policy. | `presence/sanitize.py`, `fidelity/stamp.py` | `tests/test_fidelity_authority.py` |
| **LAW-A1-OVERRIDE-PROV** | Each override fact change → provenance mutation (`A1_merge` / `ir_override`) per field path. | `_apply_ir_overrides` | `tests/test_ir_merge_override_provenance.py` |
| **LAW-PASS-CONTRACT** | Registered pass must declare non-empty mutates/preserves. | pass registry | `tests/test_ir_pass_contract.py` |
| **LAW-A1-DROP-VISIBLE** | Silent merge child drop forbidden without deviation or policy. | `merge_ir_node` | P1 |
| **LAW-A1B-DROP-PROV** | Reconcile child drop must be recorded. | `validate/graph.py` | P2 |
| **LAW-A1-DERIVED-STRIP** | LLM `layout_hints` stripped before passes. | presence sanitize | P2 |
| **LAW-WIDGETIR-CONSERVE** | Extracted widget IR conserved vs clean subtree. | `generator/ir/extracted.py` | P2 |
| **LAW-A2-HARD** | Hard geometry invariant violations raise before emit. | normalize | enforced |

## Enforcement gaps (open)

- IR-side `screen_ir.*` mutations declared but not fully checked by `validate_pass_mutates`.
- Merge multiset: test-only, not raised in merge.
- Pass `reads` dimension not yet in contract.

## Enforcement order (by field family)

1. Style/text overrides → LAW-A1-OVERRIDE-PROV
2. Fidelity/semantic tier → LAW-A1-FIDELITY-AUTHORITY
3. Identity/children multiset → LAW-A1-DROP-VISIBLE + collapse A1b compensators
4. Geometry sizing (`wrap`, omit, layout_hints)
5. Extracted widget subtree → LAW-WIDGETIR-CONSERVE

## Contribution rule

New IR pass or arrow is not review-complete until:

1. declares `mutates` / `preserves` (and `reads` when added);
2. has a row in this contract;
3. has conservation or field-preservation test;
4. any fact mutation carries provenance.

## Verdict

Schema conflates **intent** with **derived** facts. Fix by family, not screen. Compensators (`ensure_ir_direct_children_match_clean`, etc.) are symptoms of missing A1 fact-mirror contract on `children`.


### Universal codegen

General-purpose Figma → Flutter compiler — any customer layout tree, not one debug frame.

Anti-patching and compiler-wide forbidden rules: `project-bible.mdc`.

## Pipeline (Screen IR path)

```
Figma JSON → fetch → parse (clean tree + tokens)
→ fonts/assets → [optional] LLM Screen IR
→ normalize / reconcile / validate (generator/ir/)
→ layout passes → fidelity stamp → emit (generator/ir/emitter.py)
→ AST sidecar (tools/dart_ast_sidecar) — NO regex Dart surgery
→ planned Dart reconcile → graph invariants → flutter analyze
→ [optional] repair / refine → write (generator/writer.py)
```

| Layer | Role | Rule |
|-------|------|------|
| `parser/tree.py` | Figma → `CleanDesignTreeNode` | Structural signals (bounds, layoutMode, children) — not fuzzy string matching as truth. |
| `parser/tokens.py` | Design tokens | No fallback color/typography hallucinations. |
| `generator/ir/emitter.py` | IR → Dart | Deterministic emit; classification ≠ emit permission. |
| `tools/ast_sidecar` | AST mutations | All programmatic Dart edits; no regex code-tearing. |
| `generator/writer.py` | Transactional write | Merge `// <custom-code>` with indentation rebase. |

## AST and emit (zero-tolerance here)

- **No regex Dart post-processing** in `dart_postprocess.py` or `visual_refine.py` — delegate to `ast_sidecar`.
- **No inline `fontFamily` hardcoding** — inherit from `Theme.of(context).textTheme`.
- **UTF-8 only** for Dart read/write.
- **No orphan line erasure** with braces/comments/whitespace in `find_orphan_line_numbers`.
- **Idempotency:** post-processors and sidecar passes are no-op on unchanged input.
- **Structural matching:** map widgets via assets, bounds, semantic types — never label text like `"LOG IN"`.

## Build prerequisites

| Artifact | When | How |
|----------|------|-----|
| `tools/bin/ast_compiler*` | `runtime.use_ast_sidecar: true` | `.\tools\build_sidecars.ps1` |
| `figma-flutter-golden-capture:local` | `runtime.golden_capture: docker` | Auto-build or `.\scripts\update-golden-docker.ps1` |

Verify: `poetry run figma-flutter doctor`

## Bug fix protocol

1. Reproduce in `tests/fixtures/` — not ad-hoc on one customer screen.
2. Identical analyzer errors across repair attempts = infrastructure conflict, not more prompts.
3. After `tools/dart_ast_sidecar/` edits: rebuild sidecar, then `poetry run pytest -q -m "not live_figma"`.
4. Refresh goldens only via `scripts/generate_fixture_goldens.py` — never hand-edit PNG baselines.

## Systemic LLM bug registry

Pipeline-wide LLM defect with (or needing) a deterministic sanitizer:

1. Add a short NEVER/MUST rule to `SYSTEMIC_BUG_RULES` in `src/figma_flutter_agent/llm/prompts.py`.
2. Keep the repair in `dart_syntax_repairs.py`, `dart_postprocess.py`, or `tools/ast_sidecar`.
3. Add or extend a unit test on a mock fixture.

Do not leave recurring bugs only in sanitizer comments.


### Control-panel auto-repair

Headless repair jobs: `src/control_panel/repair/` (ARQ `run_repair_job`, REST `POST /v1/repair-jobs`). Enable via `repair.enabled` in `.control-panel.yml`.

**Compiler skills:** `.cursor/skills/diagnose/`, `.cursor/skills/repair/` — screen pipeline.

**Infra skills:** `.cursor/skills/debug/`, `.cursor/skills/fix/` — Discord, worker, Redis/Postgres.

Consilium optional — only for ambiguous or high-risk batches.

**Forbidden shortcuts:** deprecated agent logs, hand-editing customer `lib/`, screen-specific patches, golden updates to hide failure, LLM-generated Dart, direct semantic verdict emit without policy gate, unrelated drive-by refactors.
