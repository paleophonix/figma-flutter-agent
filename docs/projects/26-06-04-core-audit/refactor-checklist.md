# Core emit fidelity checklist

Systemic Figma → Flutter gaps tracked as **FID-*** items. Fixes must stay universal (no screen-specific hacks).

## Tier 1 — visual fidelity

| ID | Symptom | Root | Status |
|----|---------|------|--------|
| FID-06 | Frosted headers/nav lose glass blur | `layerBlur` parsed but only applied to `VECTOR` emit | **In progress** — `BackdropFilter` on container hosts with `layer_blur` |
| FID-15 | Custom icons → faint Material glyphs | `_render_stroke_glyph_fallback` replaces stroke vectors without SVG | **In progress** — chevron scale from tight bounds; prefer SVG export |
| FID-19 | Edge bars bleed past artboard (`left: -20`, width > parent) | Absolute `LEFT_RIGHT` pins copied verbatim | **Fixed** — `clamp_stack_child_placement_to_parent` in `reconcile_stack_placements_in_tree` |
| FID-20 | Date/input rows lose pill `TextField` | Trailing icon detection used `_MAX_LOCAL_DEPTH=2` | **Fixed** — `_INPUT_TRAILING_ICON_DESCENDANT_DEPTH` |

## Case study: profile editor header (`background`)

- **Back chevron:** emitted but was 12px Material on white; now scaled (≥18px) until SVG export wins (FID-15).
- **Frosted bar:** `layerBlur: 24` on `362:324` → `BackdropFilter` wrapper (FID-06).
- **Placement:** `397×84` at `left: -20` clamped to `390` width (FID-19).
- **Date field:** `INPUT` with `COLUMN > STACK > VECTOR` calendar chrome compiles as single `TextField` (FID-20).

## Not layout bugs

- Title `TextAlign.left` in `*_layout.dart` — centered appearance is usually missing/clipped back affordance, not title alignment.
- `GeneratedScreenShell` adds horizontal padding only; no title centering.

## Verification

```bash
poetry run pytest -q tests/test_emit_fidelity_contracts.py tests/test_layout_form_controls.py -m "not live_figma"
.\tools\build_sidecars.ps1   # after dart_ast_sidecar edits
```
