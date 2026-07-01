# dev

Local development workflows: wizard preflight, sync-preview, and Flutter launch helpers.

## Example

```bash
poetry run figma-flutter -i
# launch (default) — cached dump + screen IR, flutter run (no LLM)
# check — fonts, assets, doctor, live-check, flutter analyze
# fetch — import frame or full file
# generate / run / debug / view — see wizard/menus.py
```

Programmatic sync-preview (used by wizard **run → full**):

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

- `dev/wizard/` — doctor, screen preflight (dump + asset gap), `sync_preview_workflow`, `run_export_missing_screen_assets`, `flutter analyze`.
- `dev/import_figma.py` — import full Figma file or single frame into `screens.yaml` with add/overwrite manifest modes (wizard **fetch**). Frame import always prompts for a screen slug (Enter = Figma layer name in snake_case; numeric suffix when the slug is taken). Full-file fetch derives slugs from Figma layer names — use wizard **list → rename** to adjust. Frame import exports SVG/PNG into `assets/` (full-file fetch uses the same asset pass).
- `dev/project.py` — `ensure_batch_manifest` writes an empty `screens.yaml` when you **switch** to a Flutter app that lacks one (inherits `file_key` from a sibling app in the workspace or from agent `.env`).
- `dev/flutter_sdk.py` — resolve `flutter`/`dart` from PATH, Windows registry PATH, or `FIGMA_FLUTTER_SDK`.
- `dev/run.py` — legacy `run` command; calls pipeline from dump then `launch_flutter_app`.
- `dev/preview_size.py` — wizard **launch** reads the layout dump size first, falling back to `responsive.preview_width` / `preview_height` from `.ai-figma-flutter.yml` only when no dump is available. `responsive.mode` selects preview: `static` (fixed Figma artboard dart-defines), `responsive` (wide adaptive preview), or `both` (static `web-server` on port 7357 with auto-open browser, plus responsive Chrome on 7358; terminal and render-error logs attach to the responsive instance only).
- `dev/view_renders.py` — wizard **view → renders**: read `.debug/screen/<project>/<feature>/` bundle in-memory, capture Figma reference + Flutter PNG + diff heatmap into `renders/<session>/` under the same screen folder.
- `dev/debug_capture.py` — after `generate`, writes `capture.png`, `diff_heatmap.png`, and `capture.json` flat under `.debug/screen/<project>/<feature>/` (alongside `figma.png`).
- `dev/warm_capture.py` — persistent warm sandbox at `<workspace>/.sandbox/` (minimal skeleton + planned screen only). Reuses `GoldenCaptureHostSession` across agent iterations. Fixture/oracle scripts route through `validation/golden_capture/warm_runtime.py` (`FixtureCaptureBatch`). Call `reset_warm_capture_session(project_dir, feature)` after `flutter clean`.
- `dev/wizard_prefs.py` — persists active screen per project (`wizard-state.yml`) and active app per workspace (`workspace-state.yml` under `FIGMA_FLUTTER_PROJECT_DIR`).
- Interactive menu lives in `wizard/` (`run_main_wizard` in `wizard/__init__.py`) and delegates to these modules.
