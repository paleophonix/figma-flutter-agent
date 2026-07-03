# Cluster signature & extraction bijection (contract)

**Track:** Program 04 · **Authority:** normative for cluster identity after 04-P0-0.

## Signature fields (IN)

- Structural child multiset hash (typed, order-normalized where policy says so)
- Role band discriminator (chrome / icon-row / content) — 04-P0-4 shadow
- Asset ownership refs on prune/hydrate paths
- Topology variant key component (reuse `variant_topology.py`)

## OUT of structural hash alone

- Marketing text, screen name, `figmaId`
- Absolute coordinates as identity

## Definition identity (`DefinitionKey`)

Authoritative key (post 04-P0-2b): `(cluster_id, topology_variant, representative_node_id)`. Pre-M2: shadow parallel mapping; legacy `dict[cluster_id]` stays authoritative.

## Bijection (`ClusterExtractionPlan`)

| Invariant | Enforcement |
|-----------|-------------|
| Each callsite → exactly one definition | 04-P0-3a shadow → 04-P0-3b `ExtractionBijectionError` |
| Each definition → exactly one body source | plan-stage validation |
| No empty representative body | terminal invariant 04-P1-1 |

## Traversal (04-P0-1)

All dedup/prune/hydrate/asset walks on clean tree **must** use `walk_clean_tree` or `walk_clean_tree_with_parent` from `parser/tree_walk.py`.

| Walk site | Status |
|-----------|--------|
| `dedup/prune.py` | migrated |
| `dedup/hydrate.py` | migrated |
| `dedup/clusters.py` | migrated |
| `dedup/signatures.py` | migrated |
| `boundaries/assets.py` | explicit path guard or migrated |

On cycle: `CleanTreeCycleError(node_id, path, phase)` — fail loud, no silent infinite recursion.

## Planned Dart graph

`PlannedDartGraph` remains import/class/file projection only — not extraction bijection authority.
