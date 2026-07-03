# Decorative primitive contract (Program 07 P0-1)

Report-only contract for plate ⊕ glyph routing. No emit changes in P0.

| Field | Meaning |
|-------|---------|
| `role` | `plate`, `glyph`, `stroke`, `substrate` |
| `tier` | fidelity tier stamp |
| `route` | consumer family (`collapse_boundary`, `svg_emit`, …) |
| `verdict` | `preserved`, `downgraded`, `collapsed`, `unknown` |

Implementation: `src/figma_flutter_agent/compiler/contracts/decorative.py`.
