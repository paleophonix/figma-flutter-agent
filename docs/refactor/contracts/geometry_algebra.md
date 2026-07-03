# Contract: Geometry Constraint Algebra

**Status:** Commit 0 stub; normative vocabulary, implementation follows 06-P0.  
**Owner:** Program 06  
**Execution plan:** [../04-05-06-refactoring-spec-cursor.md](../04-05-06-refactoring-spec-cursor.md)

## Purpose

Define one typed per-axis vocabulary from Figma constraint facts through planner resolution and Flutter emit. Raw strings remain compatibility/audit fields during migration; new compiler decisions use typed APIs.

## Layers

| Layer | Authority | Examples |
|---|---|---|
| Raw facts | source-compatible Figma values | `horizontal`, `vertical`, frame offsets |
| Typed facts | compiler-owned resize intent | `AxisConstraint`, viewport region |
| Resolved slot | parent-size-specific plan output | pins/span/size in `LayoutSlotIr` |
| Emit | mechanical projection | `Positioned`, flex slot, viewport chrome |

## Required types

- `ConstraintOp`
- `AxisConstraint`
- `ResolvedAxisSlot`
- `LayoutRegion` / equivalent viewport owner
- named absolute→flow transform record

## Stable laws

### `LAW-GEOM-CONSTRAINT-SEMANTICS`

CENTER, PIN_END, PIN_BOTH and SCALE preserve their meaning across parent extents.

### `LAW-GEOM-ABSOLUTE-FLOW-SLOT`

Absolute→flow conversion cannot discard placement intent without a named transform, provenance and explicit residual/degraded reason.

### `LAW-GEOM-VIEWPORT-REGION`

Viewport chrome/insets retain a single region owner and cannot be reassigned to normal flow silently.

### `LAW-GEOM-SLOT-FRESH` — P1/RFC target

Committed slot fingerprint matches current structure, placement and ownership inputs.

## Responsive MVP

Stable topology + per-axis parent-relative constraints + explicit adaptive rules. Whole-screen uniform scale is not responsive constraint preservation. Automatic breakpoint topology rewrites are out of scope.

## Migration rules

1. Inventory direct raw-string consumers.
2. Ratchet prevents new consumers.
3. Add typed facts without output changes.
4. Migrate authoritative planner/validation/positioned routes.
5. Compare scoped replan with full-replan oracle before removal.

## TODO in 06-P0-0b

- [ ] Complete raw→typed mapping table.
- [ ] Define violation codes and severities.
- [ ] Define legal transforms and residual budgets.
- [ ] Link laws from `PIPELINE_ARROWS.md`.
