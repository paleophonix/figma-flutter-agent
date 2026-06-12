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

Local warm path: set `FIGMA_FLUTTER_PROJECT_DIR` to the target Flutter app. Fixture scripts
prefer host + `project/.figma-flutter/capture-sandbox` via `capture_planned_in_warm_sandbox`.

## LLM Context

Do not embed capture timings or sandbox paths in prompts. For perf debugging, read
`logs/perf/golden_capture_<feature>.json` (`GoldenCaptureTimings` schema: `mode`,
`workspace`, `timingsSec`).
