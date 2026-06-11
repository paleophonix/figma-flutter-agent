# debug

## Purpose

Canonical paths and writers for `.figma_debug/raw/`, `.figma_debug/processed/`, `.figma_debug/ir/`, `.figma_debug/dart/`, `.figma_debug/dart.bug/`, and `.figma_debug/reference/` (IR emitter goldens). Filenames mirror generated layout/screen names.

Each write is also copied into the agent repo at `logs/figma-debug/<project_label>/…` (same subtree as under the Flutter project). A full sync runs at the end of `generate`.

## Example

```python
from pathlib import Path
from figma_flutter_agent.debug.dart_bundle import write_dart_debug_snapshot
from figma_flutter_agent.debug.dumps import write_processed_dump, write_raw_dump
from figma_flutter_agent.debug.paths import raw_dump_path

project = Path("../demo_app")
write_raw_dump(project, "sign_in", figma_root_dict)
path = raw_dump_path(project, "sign_in")  # .figma_debug/raw/sign_in_layout.json
write_dart_debug_snapshot(project, feature_name="sign_in", planned_files=planned, package_name="demo_app", snapshot="plan")
write_dart_debug_snapshot(project, feature_name="sign_in", planned_files=planned, package_name="demo_app", snapshot="final")
# On parse-gate / analyze failure the pipeline writes snapshot="bug" under dart.bug/
```

## LLM context

Use `processed/<feature>_layout.json` for the parsed tree without calling Figma. Use `raw/<feature>_layout.json` to reproduce fetch/parse locally. When `use_screen_ir` is enabled and LLM runs, `ir/<feature>_llm_parsed.json`, `ir/<feature>_llm_validated.json`, and `ir/<feature>_pre_emit.json` capture screen IR after parse, after validation, and before Dart emit. Regenerate Dart without calling the LLM: `figma-flutter generate --from-dump ... --from-ir --feature-name <feature>` (loads `llm_validated`, then `llm_parsed`; `pre_emit` is write-only unless `--from-ir-path` points at it). Dart bundles: `dart/<feature>_plan.dart` right after plan, `dart/<feature>_screen.dart` before write, and `dart.bug/<feature>_screen.dart` when emit parse gate or pre-write analyze fails (nothing written to `lib/`).

Emitter goldens: `reference/<feature>_screen.dart` is a single-file bundle (same shape as `dart/<feature>_screen.dart`) with layout + screen from committed `lib/`. Refresh after fixing generated output: `poetry run python scripts/refresh_reference_from_lib.py --project-dir <flutter_app> --feature <slug>`. `scripts/write_emitter_reference.py` dumps raw emitter output for diff only — do not use it as the golden.
