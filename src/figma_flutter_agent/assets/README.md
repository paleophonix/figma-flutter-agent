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

Wizard **check → screen-assets** reuses wizard preflight parse (`dump_prefetch`) and a single `assets/` index scan. When icons are missing and `FIGMA_ACCESS_TOKEN` is set, the wizard offers to download them via `dev/wizard/asset_sync.py` (`skip_existing_assets=True`).

Failed exports log per-node warnings via `assets/reporting.py` and surface in the wizard console (never demoted by `quiet_expected_warnings`). Figma Images API batches retry on 429 before marking nodes failed.

Screen-frame node ids (primary + prototype destinations) are never exported, never loaded from disk in dump mode, and are stripped from cleanTree before LLM codegen. See `assets/screen_frame.py`.
