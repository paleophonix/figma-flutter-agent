# dev/wizard

## Purpose

Interactive wizard workflows: sync-preview, preflight, asset gap detection, and on-demand missing-asset export.

## Usage Example

```python
from figma_flutter_agent.dev.wizard.preflight import build_run_plan, collect_screen_preflight
from figma_flutter_agent.dev.wizard.asset_sync import run_export_missing_screen_assets

plan = build_run_plan(project_dir=project_dir, screen_name="bank_home")
preflight = collect_screen_preflight(plan)
if preflight.missing_asset_exports:
    run_export_missing_screen_assets(plan, settings)
```

## LLM Context

`collect_screen_preflight` returns `ScreenPreflight` with `dump_prefetch` for reuse in pipeline and `check → screen-assets`. Do not re-parse dumps when `dump_prefetch` is present.
