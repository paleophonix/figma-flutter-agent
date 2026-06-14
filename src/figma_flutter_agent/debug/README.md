# Debug artifacts

## Purpose

Persists compiler artifacts, sync state, Figma PNG gold, and warm-capture sandboxes. Screen dumps live under ``<project>/.debug/<feature>/`` as a **flat** directory; project metadata lives outside ``.debug``.

## Layout

```text
<flutter-project>/
├── wizard-state.yml
├── pubspec_resolve.sha256
├── .figma-flutter/
│   ├── layout-version
│   ├── shared/full_file_<key>.json
│   └── capture-sandbox/
└── .debug/
    ├── <feature>/
    │   ├── raw.json
    │   ├── processed.json
    │   ├── pre_emit.json
    │   ├── semantics.json
    │   ├── plan.dart
    │   ├── screen.dart
    │   ├── snapshot.json
    │   ├── last.log
    │   └── …
    └── <other-feature>/
```

Legacy v2/v3 shards (``primary/``, ``secondary/``, ``sync/``, ``logs/``) are migrated automatically on first pipeline touch (`debug/migrate.py`).

## Usage Example

```python
from figma_flutter_agent.debug.paths import raw_dump_path, screen_ir_dump_path
from figma_flutter_agent.debug.provenance import activate_provenance_recorder, write_provenance_dump

activate_provenance_recorder(feature_name="sign_in", project_dir=project_dir)
write_provenance_dump()
```

## LLM Context

Feed `provenance.json` and `pre_emit.json` from the same `.debug/<feature>/` folder when explaining pre_emit vs clean-tree diffs.
