# dev

Local development workflows: one-screen run, wizard preflight, and Flutter launch helpers.

## Example

```bash
poetry run figma-flutter -i
# pick "sync & preview" — live/offline generate + flutter run
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
- `dev/import_figma.py` — import full Figma file or single frame into `screens.yaml` with add/overwrite manifest modes (wizard **fetch**).
- `dev/flutter_sdk.py` — resolve `flutter`/`dart` from PATH, Windows registry PATH, or `FIGMA_FLUTTER_SDK`.
- `dev/run.py` — legacy `run` command; calls pipeline from dump then `launch_flutter_app`.
- `dev/wizard_prefs.py` — persists active screen to `{project}/.figma-flutter/wizard-state.yml` (loaded on wizard start).
- Interactive menu lives in `cli_interactive.py` and delegates to these modules.
