# assets

## Purpose

Export Figma vector/image nodes into Flutter `assets/icons` and `assets/images` with a manifest.

## Example

```python
from figma_flutter_agent.assets.exporter import AssetExporter

async with FigmaConnector(token) as connector:
    manifest = await AssetExporter(connector).export_assets(file_key, root, project_dir)
```

## LLM Context

Map manifest entries to `vectorAssetKey` / `imageAssetKey` on tree nodes. Filenames include node id suffix to avoid collisions.

Screen-frame node ids (primary + prototype destinations) are never exported, never loaded from disk in dump mode, and are stripped from cleanTree before LLM codegen. See `assets/screen_frame.py`.
