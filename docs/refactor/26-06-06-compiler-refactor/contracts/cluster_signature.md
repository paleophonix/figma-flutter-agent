# Cluster signature & extraction bijection (contract)

**Track:** Program 04 · **Authority:** normative after 04-P0-0.  
**Path:** `docs/refactor/26-06-06-compiler-refactor/contracts/cluster_signature.md`

## Signature fields (IN)

- Structural child multiset hash (typed, order-normalized where policy says so)
- Role band discriminator (chrome / icon-row / content) — **04-P0-4 shadow only**
- Asset ownership refs on prune/hydrate paths
- Topology variant key (reuse `variant_topology.py` — no second topology classifier)

## OUT of structural hash alone

- Marketing text, screen name, `figmaId`
- Absolute coordinates as identity
- **`ownership_role` from Program 05 overlay** — forbidden in P0 discriminator (cyclic dependency: 04 identity must not depend on 05 report-only overlay). P1 may revisit with explicit decision record if overlay promoted to source fact.

## P0 discriminator (`ClusterDiscriminator` shadow)

Allowed components (independent source facts only):

```text
viewport_region
anchor_role
interaction_role
role_band          # chrome | icon_row | content — from name/geometry, not ownership overlay
```

## Definition identity (`DefinitionKey`)

| Increment | Mode |
|-----------|------|
| **04-P0-2a** | Shadow parallel mapping; legacy `dict[cluster_id]` authoritative |
| **04-P0-2b** | Authority: `(cluster_id, topology_variant, representative_node_id)` — **post-M2 closure** |

## Bijection (`ClusterExtractionPlan`)

```python
definitions: tuple[DefinitionKey, ...]
callsite_to_definition: Mapping[str, DefinitionKey]
definition_to_class: Mapping[DefinitionKey, str]
dependencies: Mapping[DefinitionKey, frozenset[DefinitionKey]]  # required
```

| Invariant | Enforcement |
|-----------|-------------|
| Each callsite → exactly one definition | 04-P0-3a shadow → 04-P0-3b `ExtractionBijectionError` |
| Each definition → exactly one body source | plan-stage validation |
| Delegate dependency graph acyclic | `dependencies` + cycle check |
| No empty representative body | 04-P1-1 terminal invariant |

Single deterministic derivation API for `dependencies` — validators must not rebuild different graphs.

## Traversal (04-P0-1)

**Task name:** critical walk inventory + cycle-safe migration (primitive `walk_clean_tree` already exists).

| Walk site | Class |
|-----------|-------|
| `dedup/prune.py` | migrated |
| `dedup/hydrate.py` | migrated |
| `dedup/clusters.py` | migrated |
| `dedup/signatures.py` | migrated (signature subtree walks — separate inventory row) |
| `boundaries/assets.py` | migrated or explicit path guard |

DoD beyond one cyclic fixture:

- machine-readable walk inventory in contract or `generated/`
- `CleanTreeCycleError(node_id, path, phase)`
- unchanged-output test for valid trees

## Planned Dart graph

`PlannedDartGraph` — projection gate only (imports/classes/files). Not extraction bijection authority.
