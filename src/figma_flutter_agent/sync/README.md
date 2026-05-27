# sync

## Purpose

Incremental generation: snapshot previous runs and write only changed Dart/theme files (spec §16).

## Granularity

| Layer | Mechanism |
|-------|-----------|
| **Cluster widgets** | `cluster_hashes` — aggregated subtree hash per `cluster_id` / `component_*` |
| **Layout shell** | `layout_region_hash` — tree with cluster subtrees collapsed to refs |
| **Screen** | `screen_file_path(feature, architecture)` — primary feature screen only |
| **Theme** | Token group hashes + `lib/theme/*` paths |
| **Fallback** | Per-file `file_hashes` when snapshot has no region metadata (legacy) |

Changing text inside a repeated card updates `lib/widgets/product_card_widget.dart` only; `*_layout.dart` is skipped when the collapsed layout tree is unchanged.

## Example

```python
from figma_flutter_agent.sync import (
    RegionSyncState,
    build_incremental_bindings,
    load_snapshot,
    select_files_for_sync,
)
```

Snapshot path: `.figma-flutter/snapshot.json` in the Flutter project. Writes are atomic (temp file + `os.replace`) with optimistic `version` checks for parallel `generate` runs.

## Flags

- CLI `--no-sync` — full rewrite of planned files
- CLI `--regenerate-templates` — force all planned paths during incremental sync
- CLI `--force-llm-regen` — refresh LLM screen when tree hash unchanged
- YAML `generation.regen_llm_on_token_change` — regen LLM on token-only changes (production default: true)

## LLM Context

Pass `tree_hash`, token hashes, `RegionSyncState.from_tree(clean_tree)`, and `build_incremental_bindings(...)` into `select_files_for_sync` alongside `planned_files`.
