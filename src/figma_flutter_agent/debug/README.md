# debug

## Purpose

Canonical paths and writers for `.figma_debug/raw/`, `.figma_debug/processed/`, and `.figma_debug/dart/`. Filenames mirror generated layout/screen names.

## Example

```python
from pathlib import Path
from figma_flutter_agent.debug.dart_bundle import write_dart_debug_bundle
from figma_flutter_agent.debug.dumps import write_processed_dump, write_raw_dump
from figma_flutter_agent.debug.paths import raw_dump_path

project = Path("../demo_app")
write_raw_dump(project, "sign_in", figma_root_dict)
path = raw_dump_path(project, "sign_in")  # .figma_debug/raw/sign_in_layout.json
write_dart_debug_bundle(project, feature_name="sign_in", planned_files=planned, package_name="demo_app")
# -> .figma_debug/dart/sign_in_screen.dart (screen + widgets + layout inlined)
```

## LLM context

Use `processed/<feature>_layout.json` for the parsed tree without calling Figma. Use `raw/<feature>_layout.json` to reproduce fetch/parse locally. Use `dart/<feature>_screen.dart` to inspect the full screen implementation across split project files in one place.
