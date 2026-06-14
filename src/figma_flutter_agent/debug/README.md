# Debug artifacts

## Purpose

Persists compiler artifacts, sync state, Figma PNG gold, and warm-capture sandboxes. Screen dumps live under ``<agent_repo>/.debug/<feature>/`` as a **flat** directory. Flutter project roots keep wizard prefs, pubspec stamps, and ``.figma-flutter/`` metadata only.

## Layout

```text
<agent-repo>/
└── .debug/
    ├── <feature>/
    │   ├── raw.json
    │   ├── processed.json
    │   ├── pre_emit.json
    │   ├── semantics.json
    │   ├── plan.dart
    │   ├── screen.dart
    │   ├── snapshot.json
    │   ├── dart-errors.json
    │   ├── last.log
    │   └── …
    └── <other-feature>/

<flutter-project>/
├── wizard-state.yml
├── pubspec_resolve.sha256
└── .figma-flutter/
    ├── layout-version
    ├── shared/full_file_<key>.json
    └── capture-sandbox/
```

Legacy v2–v7 project ``.debug/`` trees are migrated automatically on first pipeline touch (`debug/migrate.py`).

## Usage Example

```python
from figma_flutter_agent.debug.paths import raw_dump_path, screen_ir_dump_path
from figma_flutter_agent.debug.provenance import activate_provenance_recorder, write_provenance_dump

activate_provenance_recorder(feature_name="sign_in", project_dir=project_dir)
write_provenance_dump()
```

## LLM Context

Feed `provenance.json` and `pre_emit.json` from the same `.debug/<feature>/` folder when explaining pre_emit vs clean-tree diffs.
