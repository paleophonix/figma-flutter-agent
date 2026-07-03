# Responsive Runtime Emit Epic

## Purpose

Ensure runtime Flutter screens emit **semantic responsive layout** (scroll/flex reflow) while
**fixed Figma artboard** coordinates remain available only for preview/golden capture paths.

## Laws

| ID | Law | Owner layer |
|----|-----|-------------|
| R-resp-1 | `screen_sections_emit_semantic_responsive_flow` | `generator/ir/passes/sectionize.py` |
| R-resp-2 | `fixed_artboard_allowed_only_in_preview_mode` | `generator/layout/widgets/position.py` |
| R-resp-3 | `runtime_screen_must_not_be_full_artboard_absolute_stack` | `generator/checks/layout.py` + debug |
| R-resp-4 | `bounded_visual_island_only` | sectionize band synthesis |
| R-resp-5 | `icon_metric_row_preserves_icon_slot` | `generator/layout/widgets/svg.py` |

## Tier model (LAW-RESPONSIVE-DEFN)

See `generator/checks/layout.py`:

- `preview` — artboard env vars lock dimensions for golden capture
- `scaled` — root `FittedBox(scaleDown)` around fixed artboard (legacy fallback)
- `reflowed` — `SingleChildScrollView` / `Column` with stretch (target for runtime)
- `fixed` — neither scroll nor scale

## Phased checklist

### Phase 1 — Recognition (done in this epic)

- [x] `classify_clean_tree_responsive_tier` on clean tree IR
- [x] `responsiveness_report.json` in `.debug/<project>/<feature>/`
- [x] Existing `validate_responsive_reflow_required` when `responsive.require_reflow: true`

### Phase 2 — Sectionize activation

- [x] Synthesize bounded STACK section for overlapping Y-bands without stack host
- [x] Synthetic `product_detail_vertical` fixture + tests

### Phase 3 — Emit fallback

- [x] Root STACK with geometry bottom-pin uses scroll viewport, not `FittedBox`

### Phase 4 — Icon metrics (P2)

- [x] Wide shallow SVG metric strips use `BoxFit.contain`

## Acceptance

1. `test_sectionize_emits_scroll_without_root_fitted_box` passes on product-detail fixture.
2. `classify_clean_tree_responsive_tier` returns `reflowed` after sectionize on vertical product screens.
3. `responsiveness_report.json` written on plan/materialize with `verdict` and `law` fields.
4. `responsive.require_reflow: true` blocks `scaled`/`fixed` tiers via existing gate.

## Non-goals

- Screen-specific node-id branches or food_details hacks
- Changing `preserve_placement` / `pixel_fidelity` defaults
- Golden PNG baseline updates
