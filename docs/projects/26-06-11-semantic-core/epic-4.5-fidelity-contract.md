# EPIC 4.5 — Fidelity Contract

> Status: **implemented** (2026-06-11)

## Purpose

Industrial render contract between semantic classification and Dart emit: static `fidelityTier` labels, profile-aware fallback, baked text safety, and CI lint ratchet — without runtime screenshot loops during `generate`.

## Architecture

```text
classify → stamp_fidelity_tiers → route_by_fidelity_tier → emit
                ↑                          ↑
         fidelity_manifest.yaml      text_policy + profiles
```

`llm_visual_refine` runs **post-emit** and does **not** mutate fidelity tiers.

## Checklist

| Wave | Item | Status |
|------|------|--------|
| W1 | `styled_primitive` tier + router + styled emit | done |
| W1 | `strict_fidelity` in production profile | done |
| W2 | Composite manifest lookup + `tier_source` | done |
| W2 | Stamp provenance | done |
| W3 | Fingerprint lint baseline (`tests/fixtures/lint/emitter_baseline.txt`) | done |
| W3 | Burn-down artifact in signoff | done |
| W4 | Text policy + baked gate | done |
| W4 | Semantic shadow report schema | done |
| W5 | `figma-flutter fidelity promote/validate` | done |
| W5 | Signoff manifest validation | done |

## Usage

```bash
poetry run figma-flutter fidelity validate
poetry run figma-flutter fidelity promote --kind button_filled --tier native_verified \
  --fixture-id sign_up_and_sign_in --dry-run
```

## Terminology note (merge review, non-blocker)

`styled_primitive` in E4.5 is a **production-safe semantic fallback**, not a **pixel-safe** fallback.

Current emit (`fidelity/styled_emit.py`) maps semantic kinds to **theme tokens** (`Theme.of(context).colorScheme`, default radii/padding). It does not replay full Figma `NodeStyle` bounds.

| Tier / path | Safe for | Pixel fidelity |
|-------------|----------|----------------|
| `native_verified` | production native emit | goal of manifest + golden |
| `styled_primitive` | dev / non-strict semantic fallback | **no** — themed, not Figma-exact |
| geometric layout emit | layout truth from clean-tree | partial (geometry, not typography) |

**E4.5 contract:** production/release uses `strict_fidelity` → `native_unverified` hard-fails; `styled_primitive` is an explicit dev/annotation path, not a silent pixel substitute.

**Follow-up (future epic):** if we need a **pixel-preserving** non-native fallback, introduce a separate tier name (e.g. `geometry_primitive` or `figma_styled_primitive`) — do not overload `styled_primitive`.

## Non-goals

- Full `svg_baked` / `png_baked` raster emit (E5/T2)
- PassManager registration for fidelity stamp
- Auto webhook manifest updates
