# EPIC 8 W1a — Pipeline warm reuse + timings

> Status: **implemented**. Parent: [semantic-core.md](semantic-core.md) EPIC 8. Prerequisite: [epic-8-w0.md](epic-8-w0.md).

## Purpose

Extend warm capture beyond fixture/oracle into the **generate pipeline** geometry path,
fix docker baseline refresh after W0 write guards, and dual-write capture timings to
agent + project perf directories.

## Delivered

| Item | Location |
| --- | --- |
| Docker baseline script fix | `scripts/update-golden-docker.ps1` (`--update-goldens`) |
| Pipeline geometry warm routing | `stages/runtime_geometry_check.py` → `capture_planned_for_fixture` |
| Dual timings sink | `warm_runtime.persist_golden_capture_timings` |
| Visual refine timings | `stages/visual_refine/loop.py` (post-capture persist) |

## Checklist

- [x] `update-golden-docker.ps1` passes `--update-goldens --golden-runtime docker`
- [x] `runtime_geometry_check` no longer calls `capture_planned_flutter_golden_png` directly
- [x] Timings JSON under `logs/perf/` and `<project>/.debug/perf/`
- [x] Visual refine persists timings when `capture.timings` present (in-project session unchanged)
- [x] Offline tests: `test_runtime_geometry_warm.py`, extended `test_warm_runtime.py`
- [x] Docker cold capture path unchanged (`capture_docker.py`)

## Perf paths

| Sink | Filename pattern |
| --- | --- |
| Agent repo | `logs/perf/golden_capture_<screen_id>.json` |
| Flutter project | `.debug/perf/golden_capture_<screen_id>.json` (falls back to `feature` when no screen id) |

## Follow-up (C′ sequence)

```text
E8.W1a (this) → E6.W1a (corpus advisory) → E8.W1b (docker warm volume + PNG cache)
```
