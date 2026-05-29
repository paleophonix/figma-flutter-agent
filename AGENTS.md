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
```

Use `uv run` instead of `poetry run` if the user prefers uv (see README).

## IDE (VS Code / Cursor)

Interactive menu only — no duplicate VS Code tasks:

```bash
poetry run figma-flutter -i    # or F5 → "figma-flutter — interactive menu"
```

See [README — VS Code / Cursor](README.md#vs-code--cursor).

- Secrets: `.env` (never commit) — `FIGMA_ACCESS_TOKEN`, `FIGMA_FLUTTER_PROJECT_DIR`, `LLM_PROVIDER` (`google` / `google_aistudio` → `GOOGLE_API_KEY` from Google AI Studio), `LLM_GENERATE_MODEL`, optional `LLM_REPAIR_MODEL` / `LLM_REFINE_MODEL`, other provider keys, optional `FIGMA_SMOKE_*`
- Behavior: `.ai-figma-flutter.yml` in the **agent repo** (copy from `.ai-figma-flutter.yml.example`)
- Runtime: `runtime.golden_capture: auto | docker | host` and `runtime.use_ast_sidecar: true` (AST layout rules; see `tools/dart_ast_sidecar/`)
- Env: `FIGMA_GOLDEN_RUNTIME`, `FIGMA_AST_COMPILER_PATH`, optional `FIGMA_SIGNOFF_DOCKER=1` for compose smoke in signoff
- **Build (agent-owned):** `generate` / golden capture auto-build `tools/bin/ast_compiler*` and `figma-flutter-golden-capture:local` when missing (`build_if_missing` + `FIGMA_GOLDEN_CAPTURE_AUTO_BUILD=1`). One-shot dev: `.\scripts\bootstrap.ps1`; verify: `poetry run figma-flutter doctor`
- Production / CI gates: `generate` applies production profile in code; `demo-signoff --signoff-gates` for CI fixtures

Default generation is **deterministic** (`use_deterministic_screen: true`); no LLM key required for layout.

Optional LLM **screen IR** path (`generation.use_screen_ir: true`, requires `use_deterministic_screen: false`): model emits `screenIr` + `extractedWidgets[].widgetIr`; planner materializes Dart via `generator/ir_emitter.py` (repair/refine use unified-diff on materialized files). Before emit, `generator/ir_validate.py` runs render-safety guards (stack bounds, nested scroll, ghost occlusion, keyboard scroll, tokens, assets on disk when `project_dir` is set).

## IR guardrails (defense layers)

| Layer | Role | Key paths |
|-------|------|-----------|
| Parse / clean tree | Figma truth, geometry, dedup | `parser/tree.py`, `parser/geometry.py` |
| IR validate | Block or auto-fix LLM IR before codegen | `generator/ir_validate.py` |
| Emitter / layout | Deterministic Dart, flex/stack/scroll law | `generator/ir_emitter.py`, `layout_*.py` |
| AST sidecar | Syntax/const/Flex/theme after emit | `tools/dart_ast_sidecar/`, `dart_syntax_repairs.py` |
| Prompts | Systemic bug registry for LLM | `llm/prompts.py` (`SYSTEMIC_BUG_RULES`) |
| Golden / refine | Pixel gate, IoU surgical patches | `validation/golden_capture.py`, `stages/visual_refine.py` |

Do not commit `**/.dart_tool/` (local `pub get` artifacts).

## Demo checklist (`sign_up_and_sign_in`)

1. `poetry run figma-flutter doctor` — Flutter, sidecar, optional Docker golden image.
2. Config: `use_deterministic_screen: false`, `use_screen_ir: true` in `.ai-figma-flutter.yml`; `FIGMA_ACCESS_TOKEN` in `.env`.
3. `poetry run figma-flutter generate --figma-url … --project-dir … --feature sign_up_and_sign_in` (or fixture offline path).
4. `flutter analyze` on target project; fix only via IR/repair, not hand-edits to generated layout.
5. Golden: `scripts/update-golden-docker.ps1` or pipeline refine; compare `logs/renders/*/figma_reference.png` vs `flutter_render.png`.
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

- Offline: `./scripts/signoff.sh` or `.\scripts\signoff.ps1` (ruff, mypy, demo-signoff, pytest)
- Manual E2E (real Figma frame): [tests/README.md — Manual E2E acceptance](tests/README.md#manual-e2e-acceptance)
- Helper: `.\scripts\e2e-manual.ps1 -FigmaUrl "..." -ProjectDir ..\demo_app`

## Before finishing a change

1. After `tools/dart_ast_sidecar/` edits: `.\tools\build_sidecars.ps1`
2. `.\scripts\signoff.ps1` (or individual ruff/mypy/pytest commands)
3. If touching validation, golden PNGs, or `screens.yaml`: refresh via `scripts/generate_fixture_goldens.py` (agent builds docker image if needed), then `poetry run figma-flutter demo-signoff --strict --signoff-gates`
