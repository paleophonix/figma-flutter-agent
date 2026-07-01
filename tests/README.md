# Tests

## Purpose

Pytest suite for the Figma→Flutter agent: parser, generator, pipeline stages, §23 acceptance, and optional live Figma smoke.

## Example

```bash
poetry run pytest -q -m "not live_figma"
poetry run mypy src tests
.\scripts\signoff.ps1
```

Full offline release gate (same as CI `signoff` job): `./scripts/signoff.sh` or `.\scripts\signoff.ps1` (includes `demo-signoff --signoff-gates`). Requires Flutter/dart on `PATH`. See [scripts/README.md](../scripts/README.md).

## Helpers

`tests/helpers.py`:

- `mock_fetch_*` — Figma API stubs
- `pipeline_test_dependencies()` — inject mock connector/LLM into `run_pipeline(..., deps=...)`
- `figma_connector_factory(connector)` — async context manager for tests

Prefer `deps=` over patching `FigmaConnector` or `create_llm_client` on modules.

## Markers

| Marker | Env | Command |
|--------|-----|---------|
| `live_figma` | `FIGMA_ACCESS_TOKEN`, `FIGMA_SMOKE_FILE_KEY`, `FIGMA_SMOKE_NODE_ID` | `pytest -m live_figma` |
| `repair_live` | `OPENCODE_SERVER_PASSWORD`, pinned `opencode serve`, `repair.enabled` | `pytest -m repair_live` |

## LLM context

- Pipeline DI tests: `tests/test_pipeline_dependencies.py`
- Incremental sync regions: `tests/test_sync_regions.py`
- Spec §23 acceptance: `tests/test_acceptance_spec23.py`, `tests/test_demo_signoff.py`

---

## Flutter test fixtures (IDE)

`tests/fixtures/flutter_skeleton` and `tests/fixtures/golden/*` are mini Flutter packages for golden/signoff tests. If the Dart analyzer reports missing `package:flutter/material.dart`, run `flutter pub get` in each fixture directory (paths in `.dart_tool/package_config.json` must match your local Flutter SDK). Do not commit `.dart_tool/` (see repo `.gitignore`).

---

## Manual E2E acceptance

Human checklist for a **real Figma frame** after offline gates are green (`.\scripts\signoff.ps1`).

**Prerequisites:** Poetry env, Flutter on `PATH`, `.env` with `FIGMA_ACCESS_TOKEN`, target Flutter app.

### 1. Figma connectivity

```bash
poetry run figma-flutter live-check --figma-url "<FIGMA_URL>" --dump --project-dir <PROJECT_DIR>
```

- Exit 0; dump under `<agent_repo>/.debug/screen/<project>/<feature>/raw.json`; no secrets in console.

### 2. Production generate

```bash
poetry run figma-flutter generate --figma-url "<FIGMA_URL>" --project-dir <PROJECT_DIR>
```

Production profile is default (no `--allow-dev-profile`). Expect files under `lib/features/`, `lib/generated/`, `lib/theme/`, `lib/widgets/`.

### 3. Dart / Flutter validation

```bash
cd <PROJECT_DIR>
dart format .
flutter analyze
flutter build web   # or apk
```

### 4. Runtime smoke

```bash
flutter run -d chrome
```

Check render at **320px** and **768px** width; navigation if routing enabled; text scaling.

### 5. Custom-code preservation

1. Edit only inside `// <custom-code>` … `// </custom-code>`.
2. Re-run `generate` — custom snippet preserved.
3. Edit outside zones + regenerate with production profile → error with line numbers (`strict_preservation`).

### 6. Incremental sync

1. First `generate` (creates per-screen `snapshot.json` under `.debug/screen/<project>/<feature>/`).
2. Change one repeated component in Figma.
3. Second `generate` — only expected widget/layout files rewritten; custom-code intact.

See [README — Notes & limitations](../README.md#notes--limitations) for sync semantics.
