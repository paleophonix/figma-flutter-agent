# Layout hypothesis & ownership (contract)

**Track:** Program 05 · **Blocked until:** 06-P0-0b geometry contract merged.

## Ownership edges

Sidecar `visual_ownership` on clean tree nodes (report-only P0):

| Edge | Meaning |
|------|---------|
| `surface_host` | Card/panel owns background + padding |
| `icon_plate` | Icon sits on decorative plate |
| `chrome_band` | Navbar/tab/status chrome |
| `field_host` | Input row host |
| `scroll_chrome` | Scroll viewport vs fixed chrome |

Provenance recorded; **on/off identical Dart** in P0.

## Scorecard (`LayoutCandidateScore`) — 05-P0-4

Breakdown struct (not a single float):

- `geometry_residual`
- `exceptional_offsets`
- `paint_order_penalty`
- `ownership_violations` (diagnostic-only in P0)
- `flutter_invalidity`
- `complexity_cost`
- `total`

P0 candidates: preserve-stack, row, column, wrap only. Ownership-derived candidates → 05-P1.

## Gates

| Stage | Requires |
|-------|----------|
| Scorer development | 06-P0-1b pure resolver |
| Scorer shadow merge | 06-P0-1c resolver parity |
| Scorer enforce per route | matching 06-P0-1d migration |

## Reconcile registry (05-P0-2)

Each pass declares `conflicts_with`, `priority`, `reads`, `writes`. Hero late-pass drift visible in conflict registry.

References [geometry_algebra.md](geometry_algebra.md) for pin/slot vocabulary.
