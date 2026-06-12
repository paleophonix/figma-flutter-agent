# dev

Local development workflows: one-screen run, wizard preflight, and Flutter launch helpers.

## Example

```bash
poetry run figma-flutter -i
# pick "view" (9) — preview bundle, or combat renders (ref/golden/diff → .debug/renders/)
# pick "launch" (default) or "run" → ir-offline — cached dump + .debug/ir, flutter run
```

Programmatic sync-preview:

```python
from pathlib import Path
import asyncio
from figma_flutter_agent.dev.wizard import sync_preview_workflow

asyncio.run(
    sync_preview_workflow(
        project_dir=Path("../demo_app"),
        screen_name="music_v2",
        prefer_live=True,
        device_id="chrome",
    )
)
```

## LLM context

- `dev/wizard.py` — doctor, screen preflight (dump + SVG coverage), `sync_preview_workflow`, device list, `flutter analyze`, agent sign-off.
- `dev/import_figma.py` — import full Figma file or single frame into `screens.yaml` with add/overwrite manifest modes (wizard **fetch**). Frame import always prompts for a screen slug (Enter = Figma layer name in snake_case; numeric suffix when the slug is taken). Full-file fetch derives slugs from Figma layer names — use wizard **list → rename** to adjust. Frame import exports SVG/PNG into `assets/` (full-file fetch uses the same asset pass).
- `dev/project.py` — `ensure_batch_manifest` writes an empty `screens.yaml` when you **switch** to a Flutter app that lacks one (inherits `file_key` from a sibling app in the workspace or from agent `.env`).
- `dev/flutter_sdk.py` — resolve `flutter`/`dart` from PATH, Windows registry PATH, or `FIGMA_FLUTTER_SDK`.
- `dev/run.py` — legacy `run` command; calls pipeline from dump then `launch_flutter_app`.
- `dev/preview_size.py` — wizard **launch** reads `responsive.preview_width` / `preview_height` from `.ai-figma-flutter.yml` (else layout dump), then passes `--window-size` and artboard dart-defines when `adaptive_render: false`. Capture stays artboard 1:1 always.
- `dev/view_renders.py` — wizard **view → renders**: read `.debug` bundle in-memory, capture Figma reference + Flutter PNG + diff heatmap into `.debug/renders/<session>/`.
- `dev.debug_capture` — after `generate`, write `<feature>_flutter_render.png`, `<feature>_diff_heatmap.png`, and `<feature>_capture.json` under `<project>/.debug/capture/` (Figma PNG only in `reference/figma/`).
- `dev/warm_capture.py` — persistent warm sandbox at `<project>/.debug/capture/sandbox` (minimal skeleton + planned screen only). Reuses `GoldenCaptureHostSession` across agent iterations so `flutter test` incremental builds apply after the first cold compile. Fixture/oracle scripts route through `validation/golden_capture/warm_runtime.py` (`FixtureCaptureBatch`). Call `reset_warm_capture_session(project_dir, feature)` after `flutter clean`.
- `dev/wizard_prefs.py` — persists active screen per project (`wizard-state.yml`) and active app per workspace (`workspace-state.yml` under `FIGMA_FLUTTER_PROJECT_DIR`).
- `dev/project.py` — discovers Flutter apps under a workspace root; resolves persisted active project.
- Interactive menu lives in `interactive_cli/wizard.py` and delegates to these modules.
