# Debug artifacts

## Purpose

Persists IR snapshots, provenance mutations, and reference bundles under `.figma_debug/` for offline diagnosis.

## Usage Example

```python
from figma_flutter_agent.debug.provenance import activate_provenance_recorder, write_provenance_dump

activate_provenance_recorder(feature_name="sign_in", project_dir=project_dir)
write_provenance_dump()
```

## LLM Context

Feed `provenance/<feature>.json` and `ir/<feature>_pre_emit.json` together when explaining pre_emit vs clean-tree diffs.
