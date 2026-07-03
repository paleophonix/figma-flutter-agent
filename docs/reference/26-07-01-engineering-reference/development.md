# Development & quality

## Tests

```bash
poetry run pytest -v -ra -m "not live_figma"
./scripts/signoff.sh          # full release gate
```

### Signoff pipeline (`scripts/signoff.sh`)

1. **ruff** check + format
2. **Codex lint gates** — Dart-in-Python, settings purity, hardcoded colors, regex Dart surgery
3. **mypy** on `src` + `tests`
4. **`demo-signoff --strict --signoff-gates`** — offline §23 fixtures + `dart analyze`
5. **`fixture-ir-validate`**
6. **`fidelity validate`**
7. **`corpus-oracle gate --blocking`** — skip with `FIGMA_CORPUS_ORACLE_SIGNOFF=0`
8. **`semantics corpus-gate`** + legacy predicate burndown
9. **`fixture-geometry-check`** — skip with `FIGMA_GEOMETRY_SIGNOFF=0`
10. **AST sidecar build** + **pytest** (`not live_figma`)

Optional: `FIGMA_SIGNOFF_DOCKER=1` (Docker golden pytest), `FIGMA_CORPUS_ORACLE_ALLOW_SKIP=1` (local dev only).

See [scripts/README.md](../../../scripts/README.md). Manual E2E: [tests/README.md](../../../tests/README.md#manual-e2e-acceptance).

## Generation profiles

Production path: **LLM screen IR + emitter** (see [README Features §3](../../../README.md#3-code-generation-pipeline)).

| Profile | When |
|---------|------|
| **Production** | Default on `generate` (non-dry-run): analyze, preservation, spec9, fail-fast LLM |
| **Dev** | `run` default; or `generate --allow-dev-profile` |
| **Signoff** | `demo-signoff --strict --signoff-gates` |

Config: `.ai-figma-flutter.yml.example`, LLM keys in `.env` only.

## AST sidecar and golden runtime

| Piece | Purpose |
|-------|---------|
| `tools/dart_ast_sidecar/` | Compiled Dart transforms (unscale, unwrap `LayoutBuilder`) |
| `runtime.use_ast_sidecar` | Reconcile via AST + `apply_codegen_dart_fixes` |
| `runtime.golden_capture` | `auto` \| `docker` \| `host` |
| `poetry run figma-flutter doctor` | Poetry, Flutter, AST binary, Docker golden image |
| `FIGMA_SIGNOFF_DOCKER=1` | Optional signoff Docker pytest step |

```bash
poetry run figma-flutter doctor
poetry run figma-flutter generate --figma-url "..." --project-dir ../demo_app --golden-runtime host
```

## Widget matrix (§7.4)

| Category | Widgets |
|----------|---------|
| Layout | `Row`, `Column`, `Stack`, `Wrap`, `GridView` / `GridView.builder`, `ListView` / `ListView.builder`, nested scroll |
| Inputs | `TextField` / `CupertinoTextField`, `Checkbox`, `Switch`, `RadioListTile`, `DropdownButton`, `Slider` |
| Actions | `ElevatedButton`, `OutlinedButton`, `TextButton`, `CupertinoButton` |
| Surfaces | `Card`, `AlertDialog` |
| Carousel | `PageView` (carousel / pager / swiper names) |
| Navigation | `DefaultTabController`, `BottomNavigationBar` |
| Prototype | `showModalBottomSheet` / `showDialog` for `OVERLAY` links |

Figma component variants (`Type`, `State`, `Size`, `Checked`) map to `enabled`, `obscureText`, styles, selection.

## Live Figma CI

GitHub Actions job `live-figma` when secrets are set: `FIGMA_ACCESS_TOKEN`, `FIGMA_SMOKE_FILE_KEY`, `FIGMA_SMOKE_NODE_ID`.

```bash
poetry run figma-flutter live-check --dump --project-dir ../demo_app
poetry run pytest -v -ra -m live_figma
```

## Project layout

```
figma-flutter-agent/
├── src/figma_flutter_agent/
├── src/control_panel/         # optional extra
├── tests/
├── scripts/
├── tools/
├── .ai-figma-flutter.yml.example
└── .debug/screen/             # gitignored

demo_app/                      # your Flutter project
├── screens.yaml
├── wizard-state.yml
├── assets/
└── lib/features/
```
