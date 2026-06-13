# Debug artifacts

## Purpose

Persists compiler artifacts, sync state, Figma PNG gold, and warm-capture sandboxes under `.debug/` for offline diagnosis.

Layout (relative to Flutter `project_dir`):

```text
.debug/
├── <feature>/
│   ├── primary/          # hot triage: raw, processed, pre_emit, plan/screen.dart, figma.png/json, semantics
│   └── secondary/        # llm stages, reports, capture, renders, perf, emitter_ref.dart
├── logs/last.log
├── sync/snapshot.json
├── capture/sandbox/      # warm golden capture mini-project
├── shared/               # full_file_<key>.json batch dumps
└── wizard-state.yml
```

Legacy v2 domain folders (`raw/`, `ir/`, `dart/`, …) are migrated automatically on first pipeline touch (`debug/migrate.py`).

## Usage Example

```python
from figma_flutter_agent.debug.paths import raw_dump_path, screen_ir_dump_path
from figma_flutter_agent.debug.provenance import activate_provenance_recorder, write_provenance_dump

activate_provenance_recorder(feature_name="sign_in", project_dir=project_dir)
write_provenance_dump()
```

## LLM Context

Feed `secondary/provenance.json` and `primary/pre_emit.json` together when explaining pre_emit vs clean-tree diffs.
