# Figma → Flutter Adaptive Layout Agent

[![CI](https://github.com/paleophonix/figma-flutter-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/paleophonix/figma-flutter-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Flutter 3.44+](https://img.shields.io/badge/Flutter-3.44+-02569B?logo=flutter&logoColor=white)](https://flutter.dev)
[![Poetry](https://img.shields.io/badge/Poetry-managed-60A5FA?logo=poetry&logoColor=white)](https://python-poetry.org/)
[![Material 3](https://img.shields.io/badge/Material%203-6750A4)](https://m3.material.io/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pytest](https://img.shields.io/badge/tests-pytest-0A9EDC?logo=pytest&logoColor=white)](tests/)

**LLM-first CLI that converts Figma frames into Material 3 Flutter UI inside an existing Flutter project** — structured screen IR, deterministic emit, analyze repair, and optional visual refine.

Maintained by **[Celestial Agents](LICENSE)** · MIT licensed · offline-first batch pipeline · interactive dialog mode (Flutter-style CLI)

---

### Highlights

- **Figma → Flutter codegen** — theme tokens, assets, widgets, routing, and feature screens from Auto Layout frames
- **Offline-first batch workflow** — one API call to dump an entire file; regenerate all screens without touching Figma quota
- **Interactive CLI** — TTY wizard for project path, screen picker, and manifest selection (`figma-flutter` with no args)
- **LLM screen IR + emitter** — `screenIr` + `extractedWidgets[].widgetIr` via strict JSON schema, repair/refine loops, cluster and subtree widget guardrails
- **Fail-fast generation** — live generation requires an LLM key; cached IR and fixtures stay offline-friendly
- **Production gates** — `dart analyze`, spec §9/§23 validation, incremental sync, and structured LLM output
- **455+ automated tests** — offline fixtures, golden generation, batch pipeline, and optional live Figma smoke
- **Material 3 or Cupertino** — `theme.variant` in `.ai-figma-flutter.yml`; see [docs/cupertino-coverage.md](docs/cupertino-coverage.md) for the deterministic widget matrix

---

## Table of contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Setup](#setup)
- [Interactive CLI](#interactive-cli-dialog-mode)
- [VS Code / Cursor](#vs-code--cursor)
- [Quick start: multi-screen app](#quick-start-multi-screen-app-recommended-workflow)
- [Single-frame generation](#single-frame-generation)
- [Batch commands](#batch-commands-reference)
- [CLI reference](#cli-command-overview)
- [Tests & quality](#tests--quality)
- [Generation modes](#generation-modes)
- [Widget matrix](#deterministic-widget-support-74)
- [Live Figma CI](#live-figma-ci-optional)
- [Project layout](#project-layout-agent-repo)
- [Notes & limitations](#notes--limitations)
- [Spec interpretation](#spec-interpretation)
- [License](#license)

---

## Overview

The agent ingests Figma REST API data (or cached JSON dumps), normalizes design trees and tokens, asks an LLM for screen IR, validates that IR, and emits idiomatic Flutter into your app’s `lib/` tree. Theme, assets, routing, and reusable widgets are planned around that IR path. Built for real multi-screen products: download once, iterate offline, launch any screen with a single command.

```text
Figma file  →  fetch / dump  →  parse & plan  →  codegen  →  flutter run
                  ↑ offline path (.figma_debug/) skips live API
```

Typical commands:

| Goal | Command |
|------|---------|
| First-time setup for many screens | `batch dump-file` → `batch generate` |
| Preview one screen on device | `run sign_in --project-dir ./demo_app` |
| Single frame from live Figma | `generate --figma-url … --project-dir ./demo_app` |
| Verify credentials | `live-check` |
| CI / offline sign-off | `./scripts/signoff.sh` or `demo-signoff --strict --signoff-gates` |

Agent context for coding assistants: [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md).

---

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) (recommended) or [uv](https://github.com/astral-sh/uv)
- Flutter SDK 3.44+ (for running and validating generated apps)
- Figma Personal Access Token
- Anthropic / OpenAI / OpenRouter / Google API key (required for normal `generate` / batch workflows)

## Setup

```bash
poetry install --with dev
copy .env.example .env
```

Copy agent config once in this repo:

```bash
copy .ai-figma-flutter.yml.example .ai-figma-flutter.yml
```

Edit `.ai-figma-flutter.yml` here (codegen gates, LLM repair/refine, visual QA). It is **not** stored in the Flutter project.

The shipped config uses LLM screen IR by default:

```yaml
generation:
  use_screen_ir: true
  require_screen_ir: true
```

Set in `.env`:

```env
FIGMA_ACCESS_TOKEN=figd_...
FIGMA_FLUTTER_PROJECT_DIR=E:/@dev
ANTHROPIC_API_KEY=sk-ant-...
```

`FIGMA_FLUTTER_PROJECT_DIR` is optional: workspace root (parent of Flutter apps) when `--project-dir` is omitted. Use wizard **switch** to pick the active app; choice is stored in `<workspace>/.figma-flutter/workspace-state.yml`. Falls back to sibling `../demo_app`, then cwd. Not stored in YAML — agent `.env` only.

Create a Flutter project separately:

```bash
flutter create demo_app
```

Design frames in Figma with Auto Layout, named components, and SVG export settings for icons.

> **Note:** Throughout this document, `poetry run figma-flutter` is used. With uv, replace it with `uv run figma-flutter`.

---

## Interactive CLI (dialog mode)

When stdin and stdout are a TTY (normal terminal), the CLI **automatically prompts** for missing options — similar to `flutter create` or `flutter run` without a device selected.

### Launch the main menu

```bash
poetry run figma-flutter
```

You get a looping menu ordered by pipeline stage (setup → fetch → select → generate → run → validate). Default action: **sync & preview**.

| Stage | Option | What it does |
|-------|--------|----------------|
| Setup | **switch** | Pick active Flutter app under `FIGMA_FLUTTER_PROJECT_DIR` workspace |
| Setup | **doctor** | Check Figma token, Flutter/Dart SDK, project files |
| Setup | **live-check** | Verify `FIGMA_ACCESS_TOKEN` and optionally smoke-test fetch |
| Fetch | **import from Figma URL** | Paste any Figma link — auto-detects full file vs single frame (`node-id`) |
| Fetch | **batch dump-file** | Download the entire Figma file to `.figma_debug` (one API call) |
| Screens | **list screens** | View manifest + preflight for active screen |
| Screens | **select active screen** | Numbered list from `screens.yaml` → wire `main.dart` |
| Codegen | **batch generate** | Codegen all screens listed in `screens.yaml` |
| Codegen | **generate** | Codegen one frame (offline dump or live Figma URL) |
| Preview | **sync & preview** | Live/offline generate, SVG assets, device picker, `flutter run` |
| Preview | **run** | `flutter run` only (with device picker) |
| Validate | **flutter analyze** | Run `flutter analyze` on the Flutter project |
| Validate | **agent sign-off** | `demo-signoff --signoff-gates` + pytest (agent repo) |
| — | **quit** | Exit |

Header shows project and active screen between iterations.

### Flags

| Flag | Effect |
|------|--------|
| `-i` / `--interactive` | Force prompts even when auto-detection is unclear |
| `--no-interactive` | Never prompt (CI, scripts, pipes). Missing args → error or help |

### Examples (interactive)

```bash
# Main wizard (TTY only)
poetry run figma-flutter

# Run one screen — prompts for project and screen name if omitted
poetry run figma-flutter run --project-dir E:/@dev/demo_app

# Generate — prompts for Figma URL or offers offline dump from screens.yaml
poetry run figma-flutter generate --project-dir E:/@dev/demo_app
```

### Examples (non-interactive / CI)

```bash
poetry run figma-flutter --no-interactive run sign_in --project-dir E:/@dev/demo_app
poetry run figma-flutter --no-interactive generate \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir E:/@dev/demo_app
```

**PowerShell tip:** type only the command, not the prompt prefix. If you paste `PS E:\path> poetry run ...`, PowerShell may treat `PS` as `Get-Process` and fail.

---

## VS Code / Cursor

CLI-first IDE integration (spec §19). One entrypoint: the **interactive menu** (`-i`). A single VS Code task delegates to it; optional status-bar button via **Task Buttons**.

| File | Purpose |
|------|---------|
| [`.vscode/tasks.json`](.vscode/tasks.json) | Default build task → `poetry run figma-flutter -i` |
| [`.vscode/settings.json`](.vscode/settings.json) | Status bar **`▶ figma-flutter`** (Task Buttons extension) |
| [`.vscode/launch.json`](.vscode/launch.json) | Debug interactive CLI + Flutter `demo_app` |
| [`.vscode/extensions.json`](.vscode/extensions.json) | Recommended extensions incl. Task Buttons |

| How | Action |
|-----|--------|
| **Status bar** | Click **`▶ figma-flutter`** (needs [Task Buttons](https://marketplace.visualstudio.com/items?itemName=spencerwmiles.vscode-task-buttons)) |
| **`Ctrl+Shift+B`** | Same menu (default build task) |
| **Terminal** | `poetry run figma-flutter -i` |
| **`F5`** | Run and Debug → **figma-flutter — interactive menu** |

Recommended workflow:

```text
poetry run figma-flutter -i
  → batch dump-file → batch generate → select active screen → run
```

| Symptom | Fix |
|---------|-----|
| No menu / instant exit | Use integrated terminal only; not Output panel |
| Wrong project | Menu → **switch** |
| `flutter` not found | Install Flutter SDK; restart IDE |

Release sign-off is available from the wizard (**agent sign-off**) or run `./scripts/signoff.ps1` from the agent repo root for the full gate (ruff, mypy, demo-signoff, pytest).

### AST sidecar and golden runtime

| Piece | Purpose |
|-------|---------|
| `tools/dart_ast_sidecar/` | Compiled Dart transforms (unscale, unwrap `LayoutBuilder`) |
| `runtime.use_ast_sidecar` | Reconcile path uses AST + `apply_codegen_dart_fixes` (not legacy layout regex in reconcile) |
| `runtime.golden_capture` | `auto` (Docker if available) \| `docker` \| `host` for visual refine / golden PNG |
| `poetry run figma-flutter doctor` | Poetry, Flutter, AST binary (`ast_sidecar`), Docker + `golden_image` |
| `poetry run figma-flutter doctor --build-ast` | Compile `tools/bin/ast_compiler*` when missing |
| `poetry run figma-flutter doctor --build-golden` | Manual golden image build (normally `generate` / capture auto-build) |
| `FIGMA_SIGNOFF_DOCKER=1` | Optional signoff step: build `docker/render-capture` image |

```bash
poetry run figma-flutter doctor
poetry run figma-flutter generate --figma-url "..." --project-dir ../demo_app --golden-runtime host
# force host golden capture (no Docker):
poetry run figma-flutter generate ... --no-docker
```

Offline screen fixtures: `tests/fixtures/screens.yaml` and `docs/projects/ast-modernization/ast-modernization.md`.

---

## Quick start: multi-screen app (recommended workflow)

For a Figma file with many screens (e.g. 15–16 frames), use the **offline-first** pipeline to minimize API quota usage.

### 1. Download the whole file once (JSON + SVG + PNG)

```bash
poetry run figma-flutter batch dump-file \
  --project-dir E:/@dev/demo_app \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name"
```

One command:

- **1×** `GET /v1/files/:key` — full design tree JSON
- **batched** `GET /v1/images/:key` — every SVG icon + PNG raster (incl. blur fallbacks) for the **entire file**, not per screen

This writes:

- `demo_app/.figma_debug/raw/full_file_<FILE_KEY>.json` — full file snapshot
- `demo_app/.figma_debug/raw/<feature>_layout.json` — one raw dump per top-level frame
- `demo_app/screens.yaml` — batch manifest (feature slug → node id)
- `demo_app/assets/icons/*.svg` and `demo_app/assets/images/*.png` — all media

Tree JSON only (no media): add `--json-only`.

### 2. Generate all screens offline

```bash
poetry run figma-flutter batch generate --manifest E:/@dev/demo_app/screens.yaml
```

Uses cached dumps only — **no live Figma calls** when dumps exist.

### 3. Run one screen on a device

```bash
poetry run figma-flutter run sign_in --project-dir E:/@dev/demo_app
```

What `run` does automatically:

1. Loads agent config from this repo (`.ai-figma-flutter.yml`)
2. Generates Dart from the matching `.figma_debug/raw/<feature>_layout.json` dump (`--from-dump` path internally)
3. Wires `lib/main.dart` to the selected screen
4. Runs `flutter pub get` and `flutter run`

List available screens:

```bash
poetry run figma-flutter run --list --project-dir E:/@dev/demo_app
```

Skip regeneration if code is already up to date:

```bash
poetry run figma-flutter run sign_in --project-dir E:/@dev/demo_app --skip-generate
```

---

## Single-frame generation

### Dry run

```bash
poetry run figma-flutter generate ^
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" ^
  --project-dir ../demo_app ^
  --dry-run
```

### Full generation (live Figma)

```bash
poetry run figma-flutter generate ^
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" ^
  --project-dir ../demo_app
```

### Offline from a cached dump

```bash
poetry run figma-flutter generate ^
  --from-dump ../demo_app/.figma_debug/raw/home_layout.json ^
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" ^
  --project-dir ../demo_app ^
  --feature-name sign_in
```

The `--figma-url` is still required for metadata (file key, node id) even when loading from dump; in interactive mode the agent can pick a screen from `screens.yaml` instead.

Production-style runs use **LLM screen IR + emitter** (`generation.use_screen_ir: true` in `.ai-figma-flutter.yml` plus an API key in `.env`). Cached dumps avoid repeated Figma fetches, but live generation still requires the provider key.

### Generated output inside the Flutter project

- `lib/theme/app_colors.dart`
- `lib/theme/app_spacing.dart`
- `lib/theme/app_theme.dart`
- `lib/main.dart` (wired to theme and routing)
- `lib/features/<feature>/<feature>_screen.dart`
- `lib/widgets/*.dart`
- `assets/icons/`, `assets/images/`

Optional visual QA (off by default in `.ai-figma-flutter.yml`):

```yaml
validation:
  export_figma_reference: true   # saves .figma-flutter/reference/{feature}_figma.png
  generate_golden_test: true     # emits test/golden/{feature}_screen_test.dart
```

Then run:

```bash
cd ../demo_app
dart format .
flutter analyze
flutter run -d chrome
```

---

## Batch commands reference

| Command | API calls | Purpose |
|---------|-----------|---------|
| `batch dump-file` | **1 file + batched images** | Full JSON tree, all SVG/PNG assets, `screens.yaml`, per-screen dumps |
| `batch dump-file --json-only` | **1** per run | JSON tree + manifest only (no media) |
| `batch dump` | **1 per screen** | Refresh individual screen JSON (avoid if quota is tight) |
| `batch generate` | **0** (offline) | Codegen every entry in `screens.yaml` from dumps |

### `screens.yaml` manifest

Example structure (auto-generated by `batch dump-file`):

```yaml
file_key: F7D3hhz7vdcIYSCFzTurz6
project_dir: E:/@dev/demo_app
screens:
  - feature: sign_in
    node_id: "1:234"
  - feature: home
    node_id: "1:567"
```

- `feature` — folder name under `lib/features/` and CLI screen slug for `run`
- `node_id` — Figma node id (`:` separator, e.g. `1:234`)

### Per-screen dump (alternative to dump-file)

If you already have `screens.yaml` and only need to refresh individual dumps:

```bash
poetry run figma-flutter batch dump --manifest E:/@dev/demo_app/screens.yaml
```

---

## CLI command overview

| Command | Description |
|---------|-------------|
| `figma-flutter` | Interactive menu (TTY) or help |
| `run [screen]` | Generate one screen from dump + `flutter run` |
| `generate` | Single-frame codegen |
| `batch dump-file` | One-call full file download + manifest |
| `batch dump` | Per-screen Figma fetch into `.figma_debug/` |
| `batch generate` | Offline batch codegen |
| `live-check` | Token + optional smoke fetch |
| `demo-signoff` | Offline spec §23 fixture validation |
| `validate-spec23` | Run §23 checks on a fixture |
| `visual-qa` | Pixel diff and typography specimens |
| `version` | Print package version |

Global options: `-i` / `--interactive`, `--no-interactive`.

---

## Tests & quality

```bash
poetry run pytest -v -ra
./scripts/signoff.sh          # ruff, mypy, demo-signoff --signoff-gates, pytest
# or: poetry run figma-flutter demo-signoff --strict --signoff-gates
```

`demo-signoff` validates five local Figma fixtures against spec §23 without network access. Use `--signoff-gates` for the same CI quality/validation profile as `./scripts/signoff.sh`. CI: jobs `lint` + `signoff` (see [scripts/README.md](scripts/README.md)).

Manual end-to-end QA on a real Figma frame: [tests/README.md — Manual E2E acceptance](tests/README.md#manual-e2e-acceptance). Helper script: `.\scripts\e2e-manual.ps1 -FigmaUrl "..." -ProjectDir ..\demo_app`.

Optional visual QA: `./scripts/visual-qa-signoff.sh` or `demo-signoff --strict --signoff-gates --visual-qa` (enables dark theme, reference PNG, golden scaffolds in code). Refresh planner goldens: `UPDATE_GOLDEN=1 poetry run pytest tests/test_golden_generation.py -q`.

---

## Generation

The production path is **LLM screen IR + emitter**:

| Step | Role |
|------|------|
| LLM screen IR | Provider returns `screenIr` plus `extractedWidgets[].widgetIr` through structured output |
| IR validation | Guardrails enforce stack bounds, nested scroll rules, ghost occlusion, tokens, and asset references |
| Emitter / planner | Materializes Dart screens, widgets, theme, assets, and routing from validated IR |
| Repair / refine | Analyzer repair and optional visual refine patch the materialized IR-owned files |

Live `generate` and batch workflows require a configured provider API key. Cached IR, fixture planning, and golden fixture utilities remain offline-friendly, but there is no keyless full-screen layout fallback product mode.

**Cluster widgets** (`enforce_cluster_widgets`) and **subtree widgets** (vector-heavy subtrees the LLM must not reimplement) are part of the IR pipeline.

See `.ai-figma-flutter.yml.example` for all options.

**Production gates** (spec §9 / §23 — analyze, preservation, spec9, fail-fast LLM) apply **by default** on `generate` (non-dry-run):

```bash
poetry run figma-flutter generate --figma-url "..." --project-dir ../demo_app
```

**Local dev only** (soft gates): add `--allow-dev-profile`. The `run` command uses dev profile by default; pass `--strict` for production gates.

Release sign-off: `./scripts/signoff.sh` or `.\scripts\signoff.ps1`.

Large scrollable lists (≥ 8 children) use `ListView.builder` / `GridView.builder` where the emitter can prove the structure. Scrollable and heavy widgets are wrapped in `RepaintBoundary`. Enable `accessibility.auto_fix` to bump small fonts and low-contrast text before codegen.

---

## Deterministic widget support (§7.4)

Rule-based layout helpers map Figma structure and names to Flutter widget expressions used by the IR emitter, cluster widgets, subtree widgets, and fixture/golden infrastructure.

| Category | Widgets |
|----------|---------|
| Layout | `Row`, `Column`, `Stack`, `Wrap`, `GridView` / `GridView.builder`, `ListView` / `ListView.builder`, nested scroll for `BOTH` overflow |
| Inputs | `TextField` / `CupertinoTextField`, `Checkbox`, `Switch`, `RadioListTile`, `DropdownButton`, `Slider` |
| Actions | `ElevatedButton`, `OutlinedButton`, `TextButton`, `CupertinoButton` |
| Surfaces | `Card`, `AlertDialog` |
| Carousel | `PageView` (semantic name: carousel / pager / swiper) |
| Navigation | `DefaultTabController`, `BottomNavigationBar` |
| Prototype | `showModalBottomSheet` or `showDialog` for `OVERLAY` links (dialog-like destinations) |

Component **variants** (`Type`, `State`, `Size`, `Checked`) drive `enabled`, `obscureText`, button style, and selection state.

---

## Live Figma CI (optional)

GitHub Actions job `live-figma` runs when repository secrets are set:

- `FIGMA_ACCESS_TOKEN`
- `FIGMA_SMOKE_FILE_KEY`
- `FIGMA_SMOKE_NODE_ID`

Local credential + fetch smoke:

```bash
set FIGMA_ACCESS_TOKEN=figd_...
set FIGMA_SMOKE_FILE_KEY=...
set FIGMA_SMOKE_NODE_ID=1:2
poetry run figma-flutter live-check --dump --project-dir ../demo_app
poetry run pytest -v -ra -m live_figma
```

---

## Project layout (agent repo)

```
figma-flutter-agent/
├── src/figma_flutter_agent/   # CLI, pipeline, codegen, Figma connector
├── tests/                     # pytest suite (offline-first)
├── scripts/                   # signoff, E2E helper, maintainer tools — see scripts/README.md
├── .ai-figma-flutter.yml.example
├── .ai-figma-flutter.yml      # local agent config (gitignored; copy from .example)
├── .env.example
```

Cache and batch artifacts live **inside the Flutter project**, not the agent repo:

```
demo_app/
├── screens.yaml               # batch manifest
├── .figma_debug/
│   ├── raw/
│   │   ├── full_file_*.json
│   │   └── *_layout.json
│   ├── processed/
│   │   └── *_layout.json
│   └── dart/
│       └── *_screen.dart          # screen + widgets + layout inlined for debugging
└── lib/features/              # generated screens
```

---

## Notes & limitations

### Style metadata (“Dev Mode”)

The agent does **not** call the separate Figma Dev Mode API. Style metadata is **synthesized from REST** nodes + Styles API (`rest_css_synthesis` in spec23). Expect gaps: no plugin handoff URLs, some enterprise-only fields absent, `SCALE` constraints approximated in codegen.

**Optional Dev Mode enrichment (Phase 1–2 — config only, plugin stub)**

A two-layer opt-in is available for values the REST API cannot surface (e.g. `clip-path`, `mix-blend-mode`, composite gradients):

```yaml
figma:
  style_metadata:
    source: hybrid          # rest_synthesis (default) | hybrid | dev_mode_inspect
  dev_mode:
    enabled: true
    inspect_css:
      mode: plugin_dump
      dump_path: dumps/my_screen.json   # v1 JSON from tools/figma_css_inspect/
```

| `source` | REST synthesis | Plugin dump |
|---|---|---|
| `rest_synthesis` | ✅ (default) | ❌ ignored |
| `hybrid` | ✅ base | fills gaps only |
| `dev_mode_inspect` | ✅ typed fields | overrides `css_properties` |

The plugin that produces the dump is a Phase 3 stub — see `tools/figma_css_inspect/README.md`. The `rest_css_synthesis` spec§23 criterion is never removed.

### Incremental sync

File-hash sync with `layout_region_hash` + `cluster_hashes`. Edits inside repeated clusters rewrite `lib/widgets/<widget>.dart`; non-cluster layout changes rewrite the full `*_layout.dart`. Corrupt `.figma-flutter/snapshot.json` is quarantined to `snapshot.json.corrupt` (production: `sync.fail_on_corrupt_snapshot: true` fails fast).

When the design tree hash is unchanged, LLM screen generation is skipped (theme-only updates). Use `--force-llm-regen` after prompt/model changes. Production sets `regen_llm_on_token_change: true` for token-only Figma changes.

### LLM codegen

Use API keys in `.env` (`LLM_PROVIDER`, `LLM_GENERATE_MODEL`, provider key). Production `generate` requires `anthropic` or `openai` when `require_strict_json_schema: true`. Dev providers (`openrouter`, `google`) may log `structured_output_fallback`. Optional loops: `llm_repair_after_analyze`, `llm_visual_refine` (see `.ai-figma-flutter.yml.example`).

### Other

- **Figma quota:** prefer `batch dump-file` + `batch generate` + `run` over repeated live `generate` during iteration.
- **Sync:** `--no-sync` forces full rewrite. `--allow-stubs` only for placeholder destination screens on LLM failure.
- **Variables API:** optional fetch; on HTTP 403, tokens fall back to paints + published styles.
- **Responsive:** breakpoints in `lib/theme/app_layout.dart` — mobile-small ≤480, mobile-large ≤768, tablet ≤1024; `AppBreakpoints.isWideLayout` reflows columns to rows above 480px.
- **Animations (MVP):** prototype navigation transitions only (`DISSOLVE`, `SLIDE_IN`, etc.); Lottie and layer micro-animations are post-MVP.
- **Visual QA:** golden tests compare Flutter renders, not Figma pixels directly. Reference PNG export requires live fetch + token.
- **WebP:** `assets.webp` defaults to `false`; requires Pillow when enabled.
- Secrets are masked in verbose logs.

---

## Spec interpretation

Production signoff follows these MVP deltas (formal spec is not shipped in this repo):

| Topic | Production behavior |
|-------|---------------------|
| **§5.1 styles** | REST/CSS synthesis, not Dev Mode API (`rest_css_synthesis` criterion) |
| **§7.3 responsive** | `LayoutBuilder` reflow, four-band grids, sidebar chrome, `max_web_width: 1200` |
| **§10 AI codegen** | LLM screen IR + emitter primary; cached IR / fixtures cover offline validation |
| **§16–17 preservation** | `// <custom-code>` zones + `strict_preservation`; region-aware sync (not per-node Dart inside layout files) |
| **§9 quality** | Optional `quality.enforce_spec9_gates`; production profile enables depth/contrast/preservation gates |
| **§19 IDE** | CLI wizard + `.vscode/*` launch/tasks (no marketplace plugins) |
| **§21.2 animation** | Prototype link transitions (DISSOLVE/SLIDE_IN → fade/slide); manifest in `.figma_debug/reports/*_animations.json` |
| **§21.4 AI UX** | Heuristic suggestions in pipeline warnings + `.figma_debug/reports/*_ai_ux.json` |
| **§3 state management** | `none` default; `riverpod` / `bloc` / `provider` via `state_management.type` in YAML |
| **§7.6 variables** | Best-effort fetch; 403 → paints/styles fallback |
| **§9 / §23 production profile** | Applied on `generate` (non-dry-run) via `apply_production_profile()` unless `--allow-dev-profile` |

CI fixture gates: `demo-signoff --strict --signoff-gates` (`apply_signoff_profile()`). Visual QA profile: `--visual-qa` flag or YAML `dark_mode` / `validation` flags.

---

## License

Copyright © 2026 [Celestial Agents](LICENSE).

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
