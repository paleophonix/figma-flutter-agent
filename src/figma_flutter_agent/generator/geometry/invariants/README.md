# Geometry invariants

## Purpose

Validates translation-theory geometry checks and EPIC 1 conservation laws (multiset, stack paint order, style truth, graph sync) at pipeline checkpoints.

## Usage Example

```python
from figma_flutter_agent.generator.geometry.invariants.checkpoints import run_cp0_parse_dedup
from figma_flutter_agent.parser.dedup.prune import prune_duplicated_cluster_subtrees

run_cp0_parse_dedup(tree, prune_fn=lambda: prune_duplicated_cluster_subtrees(tree))
```

## LLM Context

Conservation violations use the same `GeometryInvariantViolation` shape as emit geometry checks; include checkpoint id and `inv_*` code in repair prompts.
