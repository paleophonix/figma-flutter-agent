# parser

Figma frame JSON to clean design tree, tokens, and semantic layout.

## Example

```python
from figma_flutter_agent.parser.tree import build_clean_tree

tree, ratio, dedup, clusters = build_clean_tree(figma_root, components=components)
```

`parser/geometry.py` promotes social auth rows from bbox layout (ignores layer names).

## LLM context

Clean tree nodes carry `stackPlacement`, `type`, and `text` for codegen. `build_clean_tree` assigns clusters, then **true subtree pruning**: drops top-level `cluster_id` duplicates entirely, clears nested duplicate cluster children, and (when subtree widgets are known) removes extracted subtree node ids from the pool. Enforces FIXED sizing on STACK/BUTTON (no HUG), then runs geometry enrichment. Flex hosts (`ROW`/`COLUMN`/…) that contain absolutely positioned children are promoted to `STACK` so `stackPlacement` always has a valid ancestor. `tokens.py` emits flat `DesignTokens` maps; monochrome palettes pick a frequent neutral primary (no purple default).

**Tree mutation contract (ROB-11):** the clean tree is **copy-on-write**. Parser and reconcile passes return new nodes via Pydantic `model_copy` / `deep_copy_clean_tree`; they must not mutate shared child references in place. Duplicate Figma node ids are rejected at normalize/index boundaries (`validate_unique_node_ids`).

## Numeric rounding (`numeric_rounding.py`)

At parse time, floats are normalized before clean-tree JSON and Dart codegen:

- **1 decimal** — geometry: `width`, `height`, `left`, `top`, `right`, `bottom`, `padding`, `spacing`
- **2 decimals** — micro-styles: `letterSpacing`, `lineHeight`, `opacity`, `rotation`

## Viewport top inset (`viewport_inset.py`)

Before codegen, `apply_viewport_top_inset_to_tree` subtracts status-bar / AppBar inset from TOP-pinned `stack_placement.top` values measured from the **artboard**. Children of a `STACK` are skipped: their `top` is stack-local (e.g. header `0` + panel `104`), and shifting each child independently collapses vertical gaps and breaks sequential stack → `Column` flow detection.
