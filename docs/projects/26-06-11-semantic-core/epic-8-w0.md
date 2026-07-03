# EPIC 8 W0 — Warm capture runtime

> Status: **implemented** (2026-06-11). Parent: [semantic-core.md](semantic-core.md) EPIC 8.

## Purpose

Unify fixture golden capture behind a warm sandbox (`project/.figma-flutter/capture-sandbox`),
reuse host sessions across N screens, skip redundant `pub get`, and emit per-capture phase
timings — without changing CI Docker signoff defaults.

## Delivered

| Item | Location |
| --- | --- |
| Warm runtime orchestrator | `validation/golden_capture/warm_runtime.py` |
| Batch context | `FixtureCaptureBatch` |
| Fixture entry routing | `capture_planned_for_fixture()` |
| Local runtime preference (E8.6 lite) | `resolve_local_capture_mode()` |
| Phase timings (E8.1) | `GoldenCaptureTimings`, `logs/perf/golden_capture_<feature>.json` |
| Pub get fingerprint cache (E8.4) | `validation/golden_capture/project.py` |
| Caller wiring | `fixtures/golden_compare.py`, `geometry_check.py`, `oracle/`, `scripts/generate_fixture_goldens.py` |
| Single capture per oracle screen | `validation/oracle/evaluator.py` |

## Checklist

- [x] Local fixture capture uses `project/.figma-flutter/capture-sandbox` when `FIGMA_FLUTTER_PROJECT_DIR` is set
- [x] `generate_fixture_goldens.py` reuses one `FixtureCaptureBatch` across screens
- [x] `pub get skipped` log when pubspec fingerprint unchanged
- [x] Timing JSON under `logs/perf/` (batch default + `FIGMA_GOLDEN_CAPTURE_TIMINGS=1`)
- [x] Oracle: one capture per screen (pixel + geometry share PNG / figma_keys)
- [x] CI/signoff Docker path unchanged unless `FIGMA_GOLDEN_RUNTIME=docker` or compose signoff
- [x] Unit tests: `test_warm_runtime.py`, `test_fixture_capture_batch.py`, extended `test_warm_capture.py`

## Local dev

```bash
export FIGMA_FLUTTER_PROJECT_DIR=/path/to/demo_app
# compare only (default):
poetry run python scripts/generate_fixture_goldens.py --check
# refresh docker baselines (explicit runtime + flag):
poetry run python scripts/generate_fixture_goldens.py --update-goldens --golden-runtime docker
# local host baselines (separate dir):
poetry run python scripts/generate_fixture_goldens.py --update-goldens --golden-runtime host \
  --output-dir tests/fixtures/golden/png/host
```

Baseline writes require `--update-goldens`. Writing to `golden/png/docker` additionally
requires `--golden-runtime docker` so warm host captures cannot overwrite docker baselines.

When `FIGMA_GOLDEN_RUNTIME` is unset and YAML `golden_capture: auto`, fixture scripts prefer
**host** warm sandbox (logged as `fixture_local_prefer_host`).

## Deferred (E8.W1+)

- E8.7 Docker warm volume
- E8.8 PNG content-hash cache
- Full E8.6 mode enum (`local_fast`, `nightly_corpus`, …)

## Follow-up sequence

```text
E8.W0 → E6.W1a → E6.W1b → E7.W0 / E8.W1
```
