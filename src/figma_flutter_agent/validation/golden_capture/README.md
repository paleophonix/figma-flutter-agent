# Golden capture

## Purpose

Host and Docker runtimes that materialize planned Dart into a Flutter workspace, run
`flutter test`, and return PNG bytes plus optional `figma_keys` geometry payloads.

## Usage Example

```python
from figma_flutter_agent.config import Settings
from figma_flutter_agent.validation.golden_capture import (
    FixtureCaptureBatch,
    capture_planned_for_fixture,
)

batch = FixtureCaptureBatch(settings=Settings())
result = batch.capture_fixture_entry(entry)  # manifest screen
# or
result = capture_planned_for_fixture(batch, planned, feature_name="music_v2", layout_tree=tree)
```

Local warm path: set `FIGMA_FLUTTER_PROJECT_DIR` to the target Flutter app. Fixture scripts,
corpus oracle, and pipeline runtime geometry route through `capture_planned_for_fixture` →
`capture_planned_in_warm_sandbox` when host + `project_dir` are available.

Pipeline capture (repair geometry, optional visual refine timings):

```python
from figma_flutter_agent.validation.golden_capture import (
    capture_planned_for_fixture,
    persist_golden_capture_timings,
)

result = capture_planned_for_fixture(None, planned, feature_name="foo", project_dir=project_dir, settings=settings)
if result.timings is not None:
    persist_golden_capture_timings(result.timings, project_dir=project_dir)
```

## LLM Context

Do not embed capture timings or sandbox paths in prompts. For perf debugging, read
`<project>/.debug/perf/golden_capture_<screen_id>.json` or `logs/perf/` (fixture-only) or
`<project>/.debug/perf/golden_capture_<screen_id>.json` (`GoldenCaptureTimings`:
`mode`, `workspace`, `timingsSec`).
