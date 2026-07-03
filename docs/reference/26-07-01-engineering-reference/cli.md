# CLI reference

Command overview for `figma-flutter`. Product-oriented menu guide: [README — Features §2](../../../README.md#2-interactive-wizard-figma-flutter--i).

Global options: `-i` / `--interactive`, `--no-interactive`.

## Commands

| Command | Description |
|---------|-------------|
| `figma-flutter` | Interactive menu (TTY) or help |
| `doctor` | Poetry, Flutter, AST sidecar, Docker golden image, OpenCode CLI |
| `run [screen]` | Generate one screen from dump + `flutter run` |
| `generate` | Single-frame codegen; `--pr` publishes MR/PR (control panel extra) |
| `import-tokens` | Import design tokens from Figma Variables |
| `batch dump-file` | One-call full file download + manifest |
| `batch dump` | Per-screen Figma fetch into `.debug/screen/` |
| `batch generate` | Offline batch codegen from `screens.yaml` |
| `live-check` | Token + optional smoke fetch |
| `demo-signoff` | Offline spec §23 fixture validation |
| `validate-spec23` | Run §23 checks on a fixture |
| `fixture-ir-validate` | Validate fixture screen IR snapshots |
| `fixture-golden-check` | Check fixture golden PNGs |
| `fixture-geometry-check` | Geometry invariant checks on fixtures |
| `profile-refine-ready` | Report which fixtures are refine-ready |
| `preview-capture` | Warm golden capture for a screen |
| `visual-qa` | Pixel diff and typography specimens (subcommands) |
| `corpus-oracle gate` | Corpus oracle blocking/advisory pixel gate |
| `semantics corpus-gate` | W1 semantics precision/recall gate |
| `fidelity validate` / `fidelity promote` | Fidelity manifest validation and promotion |
| `audit` | Systemic pipeline audit docs (maintainer) |
| `version` | Print package version |

Control-plane CLIs (separate install): `figma-flutter-control-panel`, `figma-flutter-worker`, `figma-flutter-discord` (deprecated alias).

## Batch

| Command | API calls | Purpose |
|---------|-----------|---------|
| `batch dump-file` | **1 file + batched images** | Full JSON tree, all SVG/PNG assets, `screens.yaml`, per-screen dumps |
| `batch dump-file --json-only` | **1** per run | JSON tree + manifest only (no media) |
| `batch dump` | **1 per screen** | Refresh individual screen JSON (avoid if quota is tight) |
| `batch generate` | **0** (offline) | Codegen every entry in `screens.yaml` from dumps |

### Dump scopes (wizard **fetch → advanced**)

| Scope | Downloads | Best when |
|-------|-----------|-----------|
| **all** | JSON + SVG + PNG/blur raster | First import of a file |
| **json only** | Layout tree, no Images API | Structure changed; assets still valid |
| **media only** | SVG + raster from **cached** JSON | Assets changed; layout dump still valid |
| **vector only** | SVG icons from cache | Icon swap only |
| **raster only** | PNG fills + blur fallbacks from cache | Photo/raster refresh only |

### Write policy

| Policy | Behavior |
|--------|----------|
| **rewrite all** | Overwrite existing dumps and assets (default for **fetch → quick**) |
| **skip existing** | Only download missing files — checks disk first |

### `screens.yaml` manifest

```yaml
file_key: F7D3hhz7vdcIYSCFzTurz6
project_dir: .
screens:
  - feature: sign_in
    node_id: "1:234"
    dump: .debug/screen/demo_app/sign_in/raw.json
  - feature: home
    node_id: "1:567"
    dump: .debug/screen/demo_app/home/raw.json
```

- `feature` — folder under `lib/features/` and CLI slug for `run`
- `node_id` — Figma node id (`:` separator, e.g. `1:234`)

## Common flags

| Flag | Effect |
|------|--------|
| `--project-dir` | Target Flutter project root |
| `--figma-url` | Frame URL with `node-id` |
| `--from-dump` | Offline raw JSON path (agent repo relative) |
| `--feature-name` / `--feature` | Screen slug |
| `--dry-run` | Plan without writes |
| `--allow-dev-profile` | Soft production gates (local dev) |
| `--strict` | Production gates on `run` |
| `--skip-generate` | `run` without regen |
| `--force-llm-regen` | Regen IR even when tree hash unchanged |
| `--no-sync` | Force full file rewrite |
| `--golden-runtime` | `auto` \| `docker` \| `host` |

## Examples

```bash
# Interactive wizard
poetry run figma-flutter

# Non-interactive generate
poetry run figma-flutter --no-interactive generate \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir ../demo_app

# Offline from dump
poetry run figma-flutter generate \
  --from-dump .debug/screen/demo_app/sign_in/raw.json \
  --figma-url "https://www.figma.com/design/FILE_KEY/Name?node-id=1-2" \
  --project-dir ../demo_app \
  --feature-name sign_in

# Publish PR after generate (control_panel extra)
poetry run figma-flutter generate --figma-url "..." --project-dir ../demo_app \
  --pr --repo-key mobile-app --publish-mode new
```
