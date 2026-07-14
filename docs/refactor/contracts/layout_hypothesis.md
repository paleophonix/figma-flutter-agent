# Contract: Visual Ownership and Layout Hypothesis Selection

**Status:** Commit 0 stub; ownership P0 is report-only.  
**Owner:** Program 05  
**Dependency:** [geometry_algebra.md](geometry_algebra.md)  
**Execution plan:** [../04-05-06-refactoring-spec-cursor.md](../04-05-06-refactoring-spec-cursor.md)

## Purpose

Represent visual ownership as an immutable overlay and select layout only for ambiguous subtrees using typed geometry evaluation, hard vetoes, explainable score components and abstain.

## P0 boundary

Ownership P0:

- writes sidecar/debug diagnostics only;
- does not mutate clean tree or IR;
- does not influence candidate ranking;
- does not change emit or Dart output.

Chooser scoring merges only after the Program 06 authoritative resolver exists.

## Required concepts

- `VisualOwnershipEdge`;
- stable ownership relations and evidence;
- reconcile pass conflict metadata;
- ambiguous subtree predicate;
- candidate generation budget;
- `LayoutCandidateScore` breakdown;
- hard veto;
- winner margin;
- explicit abstain.

## Stable laws

### `LAW-OWNERSHIP-UNIQUE`

A node cannot have conflicting structural owners in one relation family.

### `LAW-OWNERSHIP-ACYCLIC`

Ownership overlay contains no cycles.

### `LAW-OWNERSHIP-BOUNDARY`

Ownership cannot cross extraction/render boundaries without an explicit permit.

### `LAW-OWNERSHIP-PAINT-ORDER`

Ownership grouping preserves canonical paint order unless a named transform says otherwise.

### `LAW-OWNERSHIP-NO-REPARENT`

Building the overlay never reparents canonical nodes.

### `LAW-RECONCILE-CONFLICT-DECLARED`

Overlapping reconcile writes are declared with phase, priority and conflicts.

### `LAW-LAYOUT-CANDIDATE-EXPLAINED`

Each selected/rejected candidate records score components, vetoes and evidence.

### `LAW-LAYOUT-ABSTAIN-LOW-CONFIDENCE`

No candidate is committed when feasibility, residual or confidence margin is insufficient.

## Candidate budget

```text
generated candidates ≤ 4
scored finalists ≤ 3
result = one winner or abstain
```

## TODO in 05-P0-0

- [ ] Define ownership relation enum.
- [ ] Define ambiguous subtree predicate.
- [ ] Define hard veto list.
- [ ] Define score normalization/weights and residual budget.
- [ ] Define confidence margin and abstain threshold.
- [ ] Define violation codes and provenance schema.
