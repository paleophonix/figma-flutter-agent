# Architecture RFC: Programs 04–06 North Star

**Status:** non-normative for Milestone 3; target architecture and P2+ direction.  
**Normative M3 execution plan:** [04-05-06-refactoring-spec-cursor.md](04-05-06-refactoring-spec-cursor.md)  
**Origin:** demoted and consolidated from PR #6 architecture draft.

---

## 1. Thesis

The compiler currently carries several partially independent graphs:

- Figma/canonical parenthood;
- structural cluster equivalence;
- extraction definition/call-site dependencies;
- paint order;
- visual ownership;
- geometry constraints and resolved slots;
- emit dispatch.

When graph contracts are absent or decisions are typed late, reconcile passes and emitter branches become compensators. The target architecture types facts early, makes each decision once and treats emit as a projection.

```text
Canonical facts
→ extraction identity + plan
→ ownership overlay
→ layout candidates
→ constraint evaluation
→ deterministic winner or abstain
→ geometry commit
→ mechanical emit
→ final projection validation
```

## 2. Architectural boundaries

### Program 04

Owns reusable-definition identity and extraction graph correctness:

- versioned identity;
- topology-aware keys;
- call-site/definition bijection;
- dependency DAG;
- source and asset closure;
- stable traversal/indexing.

### Program 05

Owns visual ownership and explainable layout choice:

- immutable ownership overlay;
- bounded candidates on ambiguous subtrees;
- hard vetoes;
- score breakdown;
- abstain;
- reconcile conflict orchestration.

### Program 06

Owns constraint meaning and geometry commitment:

- typed per-axis operators;
- one authoritative resolver;
- viewport ownership;
- named absolute→flow transforms;
- slot freshness;
- commit barrier.

## 3. Target data models

Illustrative, not an M3 mandate:

```python
@dataclass(frozen=True)
class ExtractionPlan:
    definitions: Mapping[str, ExtractionDefinition]
    call_sites: Mapping[str, ExtractionCallSite]
    dependencies: Mapping[str, frozenset[str]]
    source_ids: frozenset[str]
    asset_keys: frozenset[str]


@dataclass(frozen=True)
class VisualOwnershipEdge:
    owner_id: str
    owned_id: str
    relation: str
    evidence: Mapping[str, object]
    confidence: float


@dataclass(frozen=True)
class GeometryCommit:
    source_fingerprint: str
    slots: Mapping[str, LayoutSlotIr]
    selected_candidate_id: str
```

## 4. Long-term laws

### Extraction

- stable definition identity;
- bijection;
- dependency DAG;
- source/asset closure;
- no post-Dart repair as normal authority.

### Ownership/layout

- unique/acyclic ownership;
- no hidden reparenting;
- explained candidates;
- low-confidence abstain;
- bounded search.

### Geometry

- preserved constraint semantics;
- complete/fresh slots;
- one viewport owner;
- named absolute→flow transforms;
- no geometry guessing in emitter;
- no structural/placement mutation after commit.

## 5. Target geometry algebra

Per axis, the target vocabulary includes:

```text
FixedStart
FixedEnd
Stretch
Center
Scale
Intrinsic
Fill
FlowSlot
ViewportPin
```

A static rectangle is a snapshot; it is not a replacement for resize intent. CENTER and SCALE remain operators until resolved against a parent extent.

## 6. Target candidate selection

Candidate score is a structured object, not a magic float. Possible components:

- geometry residual;
- hard fact loss;
- ownership violations;
- exceptional offsets;
- Flutter validity;
- wrapper complexity;
- responsive instability;
- paint-order deviation.

Hard-fact loss and invalid Flutter topology are vetoes, not compensable penalties.

Search remains local and bounded. Full-tree combinatorial search is not a target.

## 7. Geometry commit barrier

After a future `geometry_commit`:

- parenthood;
- child order;
- layout backend;
- sizing;
- placement constraints;
- ownership/layout role

must not mutate silently. A mutation either occurs before commit or invalidates a known planning root and triggers a centralized replan with provenance.

`LayoutSlotIr` should eventually carry a source fingerprint covering structure, placement, ownership role and ordered child IDs.

## 8. Rollout model

```text
off → report_only → shadow → enforce
```

Every degraded fallback records:

- reason code;
- affected IDs;
- failed law;
- selected fallback;
- provenance.

Silent fallback is not part of the target architecture.

## 9. Observability target

Per-screen audit artifacts may include:

```text
extraction_plan.json
ownership_overlay.json
layout_candidates.json
geometry_evaluation.json
geometry_commit.json
```

These are diagnostics/cache candidates, not automatically a new source of truth.

## 10. P2+ burn-down direction

- post-hoc cluster delegate materialization becomes diagnostic-only;
- full extractor paths join the bijection contract;
- ownership-derived candidates subsume archetype-specific ordering;
- scoped replan replaces full replan only after equivalence proof;
- emitter raw-placement fallbacks disappear behind committed slots;
- flex-policy branch count ratchets downward where chooser coverage exists;
- screen-specific coordinates and asset-pair exceptions are removed through corpus evidence.

## 11. Non-goals

- CSS compatibility;
- arbitrary responsive redesign;
- LLM authority over geometry/identity/ownership;
- global optimization over the complete screen;
- architectural purity without measurable defect-family closure.

## 12. North-star acceptance

The architecture is reached when:

- reuse identity is stable and versioned;
- extraction graph is valid before emit;
- ownership is explicit and tested;
- ambiguous layouts have explainable alternatives and abstain;
- constraints preserve resize semantics;
- geometry has one commit point;
- slots are fresh at emit;
- emitter does not decide layout;
- remaining fallbacks are typed, observable and scheduled for burn-down.

This RFC guides future milestones. It must not expand M3 scope beyond the normative execution plan.
