# Agent context — figma-flutter-agent

Use this file when working in **Cursor**, **Codex**, or other coding agents on this repository.

## Purpose

Python CLI (`figma-flutter`) that fetches a Figma frame and generates Material 3 Flutter UI into an **existing** Flutter project (`--project-dir`).

## Commands (run from repo root)

```bash
poetry install --with dev
.\scripts\bootstrap.ps1       # optional: deps + Docker golden image
poetry run figma-flutter doctor
./scripts/signoff.sh          # or .\scripts\signoff.ps1 on Windows
poetry run pytest -q -m "not live_figma"
poetry run figma-flutter demo-signoff --strict --signoff-gates
poetry run figma-flutter live-check --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" --dump --project-dir ../demo_app
poetry run figma-flutter generate --figma-url "FIGMA_URL" --project-dir ../demo_app --strict
poetry install --with dev,discord   # Discord control plane
poetry run figma-flutter-discord    # requires .discord-bot.yml + DISCORD_BOT_TOKEN
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
- Local fixture warm capture: `FIGMA_FLUTTER_PROJECT_DIR` → `<project>/.figma-flutter/capture-sandbox` via `validation/golden_capture/warm_runtime.py` (`FixtureCaptureBatch`); screen-run perf lives under `<agent_repo>/.debug/<project>/<feature>/perf/`; fixture-only perf may still use `logs/perf/`
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
5. Golden: `scripts/update-golden-docker.ps1` or pipeline refine; compare `<agent_repo>/.debug/<project>/<feature>/figma.png` vs `flutter_render.png` / diff under the same folder.
6. `./scripts/signoff.ps1` before merge to `main`.

## Architecture (short)

```
cli → pipeline → fetch → parse → llm (optional) → planner → writer → sync snapshot
```

Layers: `figma/`, `parser/`, `generator/`, `stages/`, `sync/`, `validation/`, `tools/` (AST sidecar), `fixtures/` (offline screen manifest).

## Code change rules

- **Universal codegen only** — no screen-specific copy, coordinates, colors, or asset filenames in `src/`; see `.cursor/rules/universal-codegen.mdc`
- Match existing style; run `./scripts/signoff.sh` (or `ruff check`, `ruff format --check`, `mypy src tests`)
- Structured LLM output must use JSON schema / strict mode where supported
- LLM: generate/refine use `LLM_REASONING_*` when set; repair never sends reasoning (widest model compatibility). On provider rejection or transport timeout, generate/refine retry once without reasoning for the session
- Log with `loguru` logger (English messages only)
- Config via Pydantic `Settings` in `src/figma_flutter_agent/config.py` (env + YAML)
- Do not hardcode secrets; do not read `.env` in tests (pytest skips dotenv via `PYTEST_CURRENT_TEST`)

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

## Cursor rules (authoritative)

These always-apply Cursor rules are authoritative agent context for this repo:

- `.cursor/rules/debug-context.mdc`
- `.cursor/rules/developer.mdc`
- `.cursor/rules/karpathy.mdc`
- `.cursor/rules/project-bible.mdc`
- `.cursor/rules/prompt.mdc`

When this `AGENTS.md` conflicts with those files, prefer the newer `.cursor/rules/*.mdc` rule. The project bible is the architectural authority; the debug context is the debugging authority.

### Project bible

- This is a general-purpose Figma → Flutter compiler, not a demo generator.
- Pixel fidelity is law; semantic upgrades are allowed only after explicit gates allow them.
- Do not optimize for clever guesses. Prefer verified transformations, named invariants, explicit policies, corpus evidence, and deterministic recovery.
- Ask the current code before making claims. Docs, memory, comments, and previous conclusions are leads, not facts.
- Never add screen-specific, feature-specific, `figmaId`-specific, text-value-specific, asset-filename-specific, golden-specific, customer-path-specific, or one-off coordinate/padding patches.
- Every compiler stage must either preserve a Figma fact, create a named deviation with provenance, or downgrade to a safer fidelity tier.
- Clean tree is geometry truth. Screen IR may express layout intent, but it cannot invent deterministic geometry, paint order, style, type, asset, or graph facts.
- Settings enter at pipeline boundaries and flow through context objects. Do not hide `load_settings()` calls inside compiler internals.
- Deterministic failures must be caught before `dart analyze`, Flutter runtime, LLM repair, visual refine, or write stage.
- Planned Dart graph invariants must fail deterministically when consumer imports/references do not resolve to planned files.
- LLM output is structured intent, not truth. It may propose IR, candidates, and repair suggestions; deterministic compiler facts win.
- Classification is not permission to emit. Semantic candidates need report-only, fidelity, manifest, and corpus/oracle gates before changing production Dart.
- Fix the lowest correct compiler layer: parser, conservation/graph sync, IR pass, classifier, fidelity manifest/template, planned reconcile, AST sidecar, or oracle diagnosis.
- A serious fix should reproduce the failure, classify the failure family, name the law/layer, implement a generic fix, add regression proof, and run relevant gates.
- Do not auto-update PNG baselines, weaken thresholds, mutate fidelity manifests in CI, or promote advisory corpus entries to blocking without explicit intent.

### Debug doctrine

Screen artifacts live under **`<agent_repo>/.debug/<project>/<feature>/`** (project-scoped per-screen layout v9). Project metadata stays on the Flutter project root.

```text
<agent-repo>/.debug/
  <project>/
    <feature>/
      raw.json
      processed.json
      pre_emit.json
      plan.dart
      screen.dart
      figma.png
      figma.json
      semantics.json
      snapshot.json
      last.log
      dart-errors.json          # when dart analyze failed
      llm_parsed.json
      llm_validated.json
      semantic_context.json
      semantic_verdicts.json
      element_contracts.json
      contract_emit_diff.json
      contract_emit_diff.md
      provenance.json
      ai_ux.json
      animations.json
      design_coverage.json
      screen.bug.dart
      emitter_ref.dart
      flutter_render.png
      capture.json
      renders/
      perf/

<project_dir>/
  wizard-state.yml            # active screen slug
  pubspec_resolve.sha256
  .figma-flutter/
    layout-version
    shared/full_file_*.json
    capture-sandbox/
```

Naming rule: project label and feature slug in the directory path; files use short stable names (no `<feature>_` prefix). Example: `demo_app/bank_home/screen.dart`.

Primary triage read order:

```text
last.log → dart-errors.json → raw.json → processed.json → pre_emit.json → screen.dart → figma.png → semantics.json
```

Project-level artifacts (outside agent `.debug`):

- `wizard-state.yml`: active screen slug → which `.debug/<project>/<feature>/` to open.
- `pubspec_resolve.sha256`: last successful `pub get` stamp.
- `.figma-flutter/capture-sandbox/`: shared warm golden capture sandbox.
- `logs/figma_flutter_agent.log`: global telemetry only (not screen triage).

Deprecated layouts are not canonical: project-root `.debug/`, `primary/`/`secondary/` shards, `raw/<feature>_layout.json`, `ir/<feature>_*.json`, `dart/<feature>_*.dart`, agent `logs/dart-errors/`, and `.artifact-layout-v2`/v3 markers under project `.debug/`.

Full artifact map and repair doctrine: `.cursor/rules/debug-context.mdc` and `.claude/prompts/debug-common.md`.

Debugging default workflow:

1. **Batch triage:** read `.debug/<project>/<feature>/`, map **all** symptoms to laws/layers, emit `BATCH PRE-FIX TRIAGE REPORT` with repair queue R1..Rn (P0–P3).
2. **Batch repair:** implement the full in-scope queue in one session (unless user scoped one item). Each item = one named law + test. No consilium per queue item.

`/diagnose` alone stops after the report. `/repair` or "чиним всё" runs triage (if needed) then fixes all P0→P1→P2 without per-item approval.

Consilium is optional — only for ambiguous or high-risk batches.

Universal debug shortcuts are forbidden: deprecated agent logs as source of truth, hand-editing `sandbox/limbo/lib` or `demo_app/lib`, screen-specific production patches, node-id branches, one-fixture magic numbers, golden updates to hide failure, production behavior from name/text regexes, LLM-generated Dart, direct semantic verdict emission without policy gate, and unrelated drive-by refactors in the same diff.

A batch may span multiple layer classes when each item has its own law and proof. Split unrelated epics across PRs for review — not one micro-fix per symptom on the same screen.

### Developer rules

- Role: senior full-stack developer responsible for trustworthy code.
- Follow Ruff/Black, SOLID, DRY, and KISS. Keep changes surgical.
- Validate data at system boundaries. Prefer domain exceptions and `raise ... from ...` over error-code returns.
- Use Loguru only. Runtime log messages must be English and contain no emojis.
- Keep code, metadata, logs, comments, and docstrings in English.
- Public APIs should use Google-style docstrings when adding or materially changing them.
- Use structured LLM output via provider-level JSON schema / strict mode where supported.
- Keep secrets in environment/config, never in code or docs.
- Prefer constructor/context dependency flow; avoid hidden globals, mutable singletons, implicit service locators, and hidden settings reads.
- Treat 300 lines as a soft module-size warning; split by responsibility only when the change adds meaningful logic.
- Remove temporary files and scratch artifacts introduced during the session.
- Prefer local repo search before external code discovery.

### Engineering posture

- Think before coding: state assumptions when they matter, surface tradeoffs, and ask when uncertainty is risky.
- Simplicity first: no speculative features, one-off abstractions, or unnecessary configurability.
- Surgical changes: touch only what the request requires; clean up only your own mess.
- Goal-driven execution: make success criteria verifiable and loop until checked.

### Communication

- User name: Коля.
- Speak Russian in chat, use `ты`, and keep low-level technical detail concise unless it matters.
- Treat the user as product owner focused on UX, features, and business value.
- Be fair: support good ideas, challenge weak ones, and say directly when blocked or uncertain.
- Use neutral business style in documents; keep casual style to chat.
