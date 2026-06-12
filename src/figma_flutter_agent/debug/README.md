# Debug artifacts

## Purpose

Persists compiler artifacts, sync state, Figma PNG gold, and warm-capture sandboxes under `.debug/` for offline diagnosis.

Layout (relative to Flutter `project_dir`):

```text
.debug/
├── raw/ processed/ ir/ dart/ reports/ semantics/ perf/
├── logs/last.log        # latest subprocess + dart analyze transcript (cleared each run)
├── renders/             # combat-mode PNG sessions (visual refine / wizard view)
├── reference/
│   ├── figma/      # LLM visual gold PNG + JSON (was .figma-flutter/reference)
│   └── emitter/    # IR emitter single-file bundles (was flat reference/)
├── sync/snapshot.json
├── capture/
│   ├── sandbox/         # warm golden capture mini-project (persistent across runs)
│   └── <feature>_flutter_render.png, _diff_heatmap.png, …  # dev.debug_capture artifacts
└── wizard-state.yml
```

Legacy `.figma-flutter/` trees and agent-repo `logs/figma-debug`, `logs/dart-errors`, `logs/renders`
are migrated automatically on first read (`debug/migrate.py`). Each `generate` also deletes
deprecated agent `logs/{figma-debug,dart,reports,semantics,dart-errors}` shards
(`debug/agent_logs.py`). Agent `logs/figma_flutter_agent.log` stays global telemetry only.

## Usage Example

```python
from figma_flutter_agent.debug.provenance import activate_provenance_recorder, write_provenance_dump

activate_provenance_recorder(feature_name="sign_in", project_dir=project_dir)
write_provenance_dump()
```

## LLM Context

Feed `provenance/<feature>.json` and `ir/<feature>_pre_emit.json` together when explaining pre_emit vs clean-tree diffs.
