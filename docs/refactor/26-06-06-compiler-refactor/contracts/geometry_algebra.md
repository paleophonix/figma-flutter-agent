# Geometry constraint algebra (contract)

**Track:** Program 06 · **Authority:** normative after 06-P0-0b.  
**Path:** `docs/refactor/26-06-06-compiler-refactor/contracts/geometry_algebra.md`

## Layers (orthogonal — do not merge into one enum)

| Layer | Types | Examples |
|-------|-------|----------|
| **Positional constraint (per axis)** | `AxisConstraintOp` | `PIN_START`, `PIN_END`, `PIN_BOTH`, `CENTER`, `SCALE` |
| **Sizing** | `SizingMode`, explicit width/height | `HUG`, `FILL`, `FIXED` — see `Sizing` |
| **Layout backend** | `LayoutBackend`, flex participation | row/column/stack/scroll — separate from pin |
| **Viewport / region** | region owner field | chrome band, scroll host — Law 3; not a pin op |

**Forbidden:** `AxisConstraint(op=FLOW, center_delta=...)` — FLOW is not a positional operator.

Existing schema already separates: `StackPlacement`, `SizingMode`, `LayoutBackend`, `LayoutSlotIr`.

## Positional operations (`AxisConstraintOp`)

| Op | Figma axis value | Resolved slot |
|----|------------------|---------------|
| `PIN_START` | `LEFT` / `TOP` | fixed offset from start |
| `PIN_END` | `RIGHT` / `BOTTOM` | fixed offset from end |
| `PIN_BOTH` | `LEFT_RIGHT` / `TOP_BOTTOM` | stretch between edges |
| `CENTER` | `CENTER` | center delta |
| `SCALE` | `SCALE` | scale offset + size ratios |

## Typed model (`AxisConstraint`)

| Increment | Mode |
|-----------|------|
| **06-P0-1a** | Additive: `op`, offsets, size, center_delta, scale ratios; **no output change** |
| **06-P0-1b** | Pure `resolve_constraint_axis()` + metamorphic tests |
| **06-P0-1c** | Shadow parity vs legacy branches |
| **06-P0-1d** | Per-route authority (**post-M2 closure**) |

Raw `horizontal`/`vertical` strings remain for audit; legacy authoritative until 06-P0-1d.

## Consumer taxonomy (06-P0-0a)

| Category | Meaning |
|----------|---------|
| `parser_fact` | Reads Figma JSON into placement |
| `reconcile_transform` | Mutates placement during normalize |
| `planner_slot` | Maps placement → layout slot |
| `emit_positioned` | Emits Dart positioned/flex |
| `ir_guard` | IR validate graph checks |
| `schema_type` | Pydantic / enum definition |

Machine inventory: `docs/refactor/26-06-06-compiler-refactor/generated/constraint-consumers.json`  
Ratchet baseline: `docs/refactor/26-06-06-compiler-refactor/generated/constraint-consumers-ratchet-baseline.json`

## Laws (P0)

1. **Wrong pin/center** — resolver single authority after 06-P0-1d per route
2. **Absolute→flow slot loss** — named deviation on clamp (06-P0-2)
3. **Viewport/chrome partition** — region owner on clean tree (06-P0-3)

## Replan

`replan_geometry_after_layout_passes` is a compensator until scoped replan (06-P1) proves equivalence.
