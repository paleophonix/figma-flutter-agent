# EPIC 6 W0 — Corpus oracle (first mergeable slice)

> Status: **accepted as W0 foundation** (2026-06-12). Hardening: [epic-6-1.md](epic-6-1.md).

Parent: [epic-6-corpus-oracle.md](epic-6-corpus-oracle.md).

## Purpose

Ship the minimum real-design corpus oracle infrastructure: manifest tiers, split pixel
metrics, blocking gate on four committed goldens, advisory report scaffold, and signoff
artifacts — without growing the corpus to 25 screens yet.

## Delivered

| Item | Location |
| --- | --- |
| Manifest tiers + thresholds | `tests/fixtures/screens.yaml`, `fixtures/screens_manifest.py` |
| Split pixel compare | `validation/pixel/split_compare.py` |
| Warm fixture capture | `fixtures/capture_context.py` |
| Oracle orchestrator | `validation/oracle/` |
| CLI | `figma-flutter corpus-oracle gate` |
| Signoff | `scripts/signoff.ps1`, `scripts/signoff.sh` |

## Blocking pilot (4 screens)

- `sign_up_and_sign_in`
- `reminders`
- `music_v2`
- `music_v2_ru_dirty`

## Gates

**Blocking** (`strict_pixel_blocking`):

- `non_text_pixel_diff <= threshold`
- `geometry_iou >= threshold` (when `strict_geometry` in `oracle_modes`)
- `text_bounds_delta <= threshold`

**Advisory** (pre-E7):

- `text_region_pixel_diff` — reported, does not fail release

## Signoff

```bash
poetry run figma-flutter corpus-oracle gate --blocking --write-report-dir logs/oracle
```

Artifacts:

- `logs/oracle/blocking_gate.json`
- `logs/oracle/advisory_pixel_report.json`
- `logs/oracle/fidelity_promotion_candidates.json`

Opt-out (no Flutter capture): `FIGMA_CORPUS_ORACLE_SIGNOFF=0`

## DoD checklist

- [x] Four goldens tagged `strict_pixel_blocking`
- [x] Split `non_text` / `text_region` pixel channels
- [x] `corpus-oracle gate --blocking` CLI
- [x] Signoff wires blocking gate + JSON artifacts
- [x] `generate_fixture_goldens.py` passes `project_dir` when configured
- [x] S5.W1 synthetic semantics gate unchanged
- [x] No CI mutation of `fidelity_manifest.yaml`

## Next (W1)

- Add 8–10 layouts + goldens
- Expand blocking subset toward 8–12 screens
- Enable full blocking golden CI with Docker warm capture
