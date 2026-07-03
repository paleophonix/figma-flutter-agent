# Contract: Cluster Signature, Definition Identity and Bijection

**Status:** Commit 0 stub; normative vocabulary, implementation follows 04-P0.  
**Owner:** Program 04  
**Execution plan:** [../04-05-06-refactoring-spec-cursor.md](../04-05-06-refactoring-spec-cursor.md)

## Purpose

Separate structural equivalence, role discrimination, topology variant identity and pre-render call-site mapping.

## Required concepts

- structural signature;
- `ClusterDiscriminator` outside the structural hash;
- `DefinitionKey` for topology variants;
- `ClusterExtractionPlan(definitions, call_sites)`;
- cycle-safe traversal;
- canonical asset index;
- planned Dart graph as final projection gate only.

## Field classification

Every relevant clean-node field must be classified as:

| Class | Meaning |
|---|---|
| `identity` | difference requires another definition |
| `parameter` | difference belongs to call-site props |
| `ignored` | safe to omit from equivalence |
| `discriminator` | role/context partitions structurally equal buckets |
| `forbidden_to_collapse` | nodes may never share a definition |

## Stable laws

### `LAW-CLUSTER-DEFINITION-KEY`

Topology variants cannot overwrite each other through a `cluster_id`-only mapping.

### `LAW-CLUSTER-BIJECTION`

Before Dart render, every call-site resolves to exactly one definition and every definition has at least one call-site.

### `LAW-CLUSTER-DISCRIMINATOR`

Role/context partitions false structural merges without arbitrary coordinates or screen-specific data.

### `LAW-CLUSTER-WALK-ACYCLIC`

Critical dedup/prune/hydrate/asset traversal terminates with a typed cycle error.

### `LAW-CLUSTER-ASSET-INDEX`

Normal plan paths use canonical indexed asset lookup rather than repeated per-node scans/globs.

### `LAW-CLUSTER-PLANNED-PROJECTION`

Planned Dart graph validates files/imports/classes after extraction correctness has already been established.

## TODO in 04-P0-0

- [ ] Complete signature IN/OUT table.
- [ ] Define discriminator taxonomy.
- [ ] Define `DefinitionKey` serialization/versioning.
- [ ] Define prune/hydrate asset ownership.
- [ ] Define violation codes and corpus linkage.
