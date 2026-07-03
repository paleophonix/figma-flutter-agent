# Geometry constraint algebra (contract)

**Track:** Program 06 · **Authority:** normative for constraint vocabulary after 06-P0-0b.

## Layers

| Layer | Owns | Must not |
|-------|------|----------|
| Parser | Figma placement facts (`StackPlacement`, sizing) | Invent emit slots |
| Planner | `ResolvedAxisSlot`, flex/stack intent | Silent absolute→flow without deviation |
| Emitter | Dart `Positioned` / flex children | Raw string pin branches without resolver |

## Constraint operations (`ConstraintOp`)

| Op | Figma axis value | Resolved slot |
|----|------------------|---------------|
| `PIN_START` | `LEFT` / `TOP` | fixed offset from start |
| `PIN_END` | `RIGHT` / `BOTTOM` | fixed offset from end |
| `PIN_BOTH` | `LEFT_RIGHT` / `TOP_BOTTOM` | stretch between edges |
| `CENTER` | `CENTER` | center delta |
| `SCALE` | `SCALE` | scale offset + size ratios |

## Typed model (`AxisConstraint`)

Additive model (06-P0-1a): `op`, `start_offset`, `end_offset`, `size`, `center_delta`, `scale_offset_ratio`, `scale_size_ratio`. Raw `horizontal`/`vertical` strings remain for audit; authoritative resolver: `resolve_constraint_axis()`.

## Consumer taxonomy (06-P0-0a)

| Category | Meaning |
|----------|---------|
| `parser_fact` | Reads Figma JSON into placement |
| `reconcile_transform` | Mutates placement during normalize |
| `planner_slot` | Maps placement → layout slot |
| `emit_positioned` | Emits Dart positioned/flex |
| `ir_guard` | IR validate graph checks |
| `schema_type` | Pydantic / enum definition |

Machine inventory: `docs/refactor/generated/constraint-consumers.json`. Ratchet baseline: `constraint-consumers-ratchet-baseline.json`.

## Laws (P0)

1. **Wrong pin/center** — resolver is single authority for pin semantics (06-P0-1).
2. **Absolute→flow slot loss** — named deviation on clamp (06-P0-2).
3. **Viewport/chrome partition** — region owner on clean tree (06-P0-3).

## Replan

`replan_geometry_after_layout_passes` is a compensator for double-truth until scoped replan (06-P1) proves equivalence.
