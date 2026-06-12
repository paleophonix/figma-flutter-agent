# batch

## Purpose

Multi-screen Figma workflows: manifest I/O, dumps, batch generate, and per-screen artifact lifecycle (purge/copy).

## Usage Example

```python
from pathlib import Path

from figma_flutter_agent.batch.manifest import load_batch_manifest
from figma_flutter_agent.batch.screen_lifecycle import purge_screen_artifacts, copy_screen_to_project

manifest = load_batch_manifest(Path("demo_app/screens.yaml"))
purge_screen_artifacts(manifest, "sign_in")
copy_screen_to_project(manifest, "home", Path("../other_app"))
```

## LLM Context

`screens.yaml` maps feature slugs to Figma node ids and dump paths. `screen_lifecycle` resolves lib, widgets, assets (by dump node ids), `.debug`, and golden tests per slug; shared assets are kept when other manifest screens still reference the same node id.
