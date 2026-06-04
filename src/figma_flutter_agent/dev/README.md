# dev

Local development workflows: one-screen run, wizard preflight, and Flutter launch helpers.

## Example

```bash
poetry run figma-flutter -i
# pick "view" (9) — deploy .figma_debug/dart or reference bundle + flutter run
# pick "run" — full / offline / ir-offline (cached dump + .figma_debug/ir) + flutter run
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
- `dev/import_figma.py` — import full Figma file or single frame into `screens.yaml` with add/overwrite manifest modes (wizard **fetch**). Interactive frame import prompts for a screen slug (Enter = Figma layer name in snake_case; numeric suffix when the slug is taken). Frame import exports SVG/PNG into `assets/` (full-file fetch uses the same asset pass).
- `dev/project.py` — `ensure_batch_manifest` writes an empty `screens.yaml` when you **switch** to a Flutter app that lacks one (inherits `file_key` from a sibling app in the workspace or from agent `.env`).
- `dev/flutter_sdk.py` — resolve `flutter`/`dart` from PATH, Windows registry PATH, or `FIGMA_FLUTTER_SDK`.
- `dev/run.py` — legacy `run` command; calls pipeline from dump then `launch_flutter_app`.
- `dev/wizard_prefs.py` — persists active screen per project (`wizard-state.yml`) and active app per workspace (`workspace-state.yml` under `FIGMA_FLUTTER_PROJECT_DIR`).
- `dev/project.py` — discovers Flutter apps under a workspace root; resolves persisted active project.
- Interactive menu lives in `cli_interactive.py` and delegates to these modules.
