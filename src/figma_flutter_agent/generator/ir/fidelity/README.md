# Fidelity subsystem (EPIC 4.5)

## Purpose

Assigns static `fidelityTier` labels from the verification manifest, routes semantic IR nodes to native templates, themed primitives, baked assets, or geometric layout, and records tier provenance for reports.

## Usage Example

```python
from figma_flutter_agent.generator.ir.fidelity import (
    load_fidelity_manifest,
    stamp_fidelity_tiers,
    route_by_fidelity_tier,
    EmitPath,
)
from figma_flutter_agent.generator.ir.context import IrEmitContext

manifest = load_fidelity_manifest()
stamped = stamp_fidelity_tiers(screen_ir, clean_tree=clean_tree)
path = route_by_fidelity_tier(stamped.root, ctx=IrEmitContext(), strict_fidelity=True)
if path == EmitPath.BAKED_ASSET:
    from figma_flutter_agent.generator.ir.fidelity import emit_baked_asset
    dart = emit_baked_asset(stamped.root, clean=clean_tree, ctx=IrEmitContext(uses_svg=True))
```

CLI (offline promotion only):

```bash
poetry run figma-flutter fidelity validate
poetry run figma-flutter fidelity promote --kind button_filled --tier native_verified \
  --fixture-id sign_up_and_sign_in --dry-run
```

## LLM Context

Do not infer tiers from screenshots during generate. Tiers are stamped from `generator/ir/data/fidelity_manifest.yaml` before emit. The router consumes `WidgetIrNode.fidelity_tier` and profile flags only.
