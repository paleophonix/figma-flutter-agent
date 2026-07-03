# PIPELINE_ARROWS — field preservation contract (RAR program 01)

> **Agent instructive copy:** `.cursor/rules/pipeline-contracts.mdc` (keep in sync when laws change).

**Status:** draft v1 (arrows A1–A3 grounded in live code; A4 catalogued at fact level).
**Owner artifact for:** `refactor/01_compiler-semantics-ir-contract.md`.
**Rule of use:** this file is the contract matrix. Every registered IR pass and every
cross-graph arrow must declare what it `reads`, `writes`, and `must_preserve`. A pass or
arrow that mutates a field it did not declare is a contract violation, not a feature.

---

## 1. Purpose

The compiler loses or rewrites Figma facts on the arrows between stages, not inside a
single emitter. Most "emitter bugs" are information loss on `parse -> IR -> merge -> emit`.
This document names, per arrow, which fields must survive, which are inferred without a
Figma fact, which are dropped on purpose, and which mutations are illegal without a
provenance record.

It is the reference for the Master Invariant: **every stage must preserve a Figma fact,
create a named deviation with provenance, or downgrade a fidelity tier.**

---

## 2. Vocabulary

Three kinds of IR field (see `schemas/ir.py`):

| Class | Meaning | Authority | Examples |
|-------|---------|-----------|----------|
| **fact-mirror** | Copy of a clean-tree fact; the IR may not invent a value | `CleanDesignTreeNode` | `WidgetIrNode.figma_id`, `WidgetIrNode.children` (id set) |
| **intent** | LLM/pass proposal; deterministic layer decides legality | LLM / pass, gated | `kind`, `ref`, `overrides`, `wrap`, `is_selected`, `payload`, `semantic_verdicts` (report-only) |
| **derived** | Produced by a pass from facts; must carry provenance | pass output | `layout_hints`, `fidelity_tier`, `tier_source`, `layout_slot` (clean tree) |

Clean-tree fields are all **facts** (geometry, style, type, paint order, assets). They are
tier-1 truth; an arrow may transform them only with a named deviation.

---

## 3. Arrow catalog

### A1 — clean tree + screen IR -> merged clean tree

Code: `generator/ir/tree.py::merge_screen_ir` -> `merge_ir_node` -> `_apply_ir_overrides`,
`resolve_stack_child_order`.

| Cell | Fields / behaviour | Evidence |
|------|--------------------|----------|
| **preserved** | node id multiset (minus `omitFigmaIds`), STACK paint order, stack-placed visuals omitted from IR, component-instance children when IR empty, flow-layout siblings omitted from partial IR | `preserve_clean_child_without_ir`, `preserve_clean_child_omitted_from_partial_ir`, `resolve_stack_child_order`; tests `test_ir_merge_preserve.py` |
| **inferred** | child *ordering* from IR child order; extracted-widget substitution (`extracted_widget_ref`) | `merge_ir_node` loop over `ir.children`; `kind == EXTRACTED` branch |
| **lossy** | clean children present in IR-bearing parent, absent from `ir.children`, and NOT matched by a preserve predicate are dropped **silently** | `merge_ir_node` final loop only re-adds preserve-predicate children |
| **illegal (ungated)** | `_apply_ir_overrides` rewrites clean-tree `text`, `accessibility_label`, `style.text_color`, `style.background_color`, `style.font_size` with **no `DeviationRecord`** | `generator/ir/tree.py:74-96` |

**Counterexample (illegal cell):** an IR node with `overrides.textColor="#FF0000"` on a Figma
text node whose clean fill is `#111111` produces red Dart text, and nothing in
`provenance.json` records that a fact was overwritten. Violates "no record = no mutation"
(`debug/provenance.py::DeviationRecord`). Promote to program-00 corpus as `override-*`.

**Counterexample (lossy cell):** a `COLUMN` parent whose IR lists only 1 of 3 non-flow
children (e.g. a decorative `CONTAINER` that is not stack-placed) silently loses 2 nodes;
`assert_node_multiset_preserved` would catch it, but merge itself does not raise.

### A1b — clean tree -> screen IR reconcile (compensator)

Code: `generator/ir/validate/graph.py::sync_screen_ir_graph_to_clean_tree`
(`realign_screen_ir_children_to_clean_tree`, `ensure_ir_direct_children_match_clean`,
`_align_ir_stack_children_to_clean_tree`, `_sync_chip_choice_selected_from_clean_tree`).

| Cell | Fields / behaviour |
|------|--------------------|
| **preserved** | clean-tree parent->child links become authoritative on the IR (`figma_id`, child id set, stack child order) |
| **inferred** | stub IR nodes (`WidgetIrKind` from clean `type`) inserted for missing clean children; misplaced IR children reparented |
| **lossy** | IR children whose `figma_id` is absent from the clean parent map are dropped with a `logger.warning` (no provenance record) |
| **illegal** | downgrading an `EXTRACTED` host to a structural kind is logged but not recorded as a deviation |

This arrow exists **because** A1 has no explicit fact-mirror contract on `children`.
It is the symptom the program predicted: reconciliation compensating for an absent contract.

### A2 — clean tree -> normalized clean tree

Code: `generator/normalize.py::normalize_clean_tree`.

| Cell | Fields / behaviour | Enforcement |
|------|--------------------|-------------|
| **preserved** | node multiset, geometry facts, paint order across reconcile + geometry planner | CP1 checkpoint `run_cp1_normalize`; `validate_geometry_invariants` |
| **inferred** | `layout_slot` (geometry planner), render-safety guards, resolved asset keys | `plan_geometry_tree`, `apply_ir_guards`, asset resolvers |
| **lossy** | oversized frame widths clamped to artboard; degraded nodes marked | `clamp_oversized_frame_widths_to_artboard`, `mark_degraded_nodes` (soft violations) |
| **illegal** | hard geometry-invariant violation -> `GenerationError` before emit | `raise_on_hard_geometry_violations` |

**This is the best-gated arrow.** It already raises on hard violations and marks soft
deviations. A2 is the enforcement model A1 should copy.

### A3 — merged clean tree + screen IR -> Dart expression

Code: `generator/ir/expression.py::emit_screen_body_from_ir` -> `emit_widget_expression`.

| Cell | Fields read / behaviour |
|------|-------------------------|
| **reads (facts)** | clean `type`, `children`, geometry, style, `layout_slot` (structure + leaf body) |
| **reads (intent)** | `ir.kind`, `ir.wrap`, `ir.fidelity_tier`, `ir.ref`, semantic payload |
| **preserved** | emit does not mutate the tree; overrides were already baked into `clean` at A1, so an A1 leak is invisible here |
| **gated** | semantic native emit only when `report_only=false` AND `tier_allows_native` (`route_by_fidelity_tier`) |
| **lossy** | `STUB_IR_KINDS` fall back to layout emit with a `logger.warning` (intent dropped, not fact) |

A3's contract is a **read** contract: every fact it reads must have been preserved by A1/A2.
The override leak proves the point — by A3 the fact is already gone.

### A4 — Figma JSON -> clean tree (fact level, catalogued)

Code: `parser/tree.py`, `parser/geometry.py`. Produces all tier-1 facts (geometry from
`relativeTransform`, paint order, style, type, assets). Full field matrix deferred to a
later increment; A4 is the source of every fact the arrows above must preserve.

---

## 4. Enforcement status

| Guarantee | Where enforced | State |
|-----------|----------------|-------|
| node multiset preserved (merge) | `conservation_node_multiset` / `assert_node_multiset_preserved` | test-only, not raised in merge |
| node multiset preserved (passes) | `validate_pass_preserves` + CP2 | **enforced** (Wave-1 + semantic) |
| stack paint order preserved | `check_stack_paint_order_preserved` | **enforced** in passes; authoritative in merge |
| graph sync (IR ids == clean ids) | `check_graph_sync` | **enforced** in passes |
| clean-tree fields unchanged by a pass | `validate_pass_mutates` (clean fields only) | **enforced** for clean-tree tokens |
| IR-side mutations (`screen_ir.*`) | declared by `classify_screen_ir_pass`, **not** checked by `validate_pass_mutates` | **GAP** |
| geometry invariants | `validate_geometry_invariants` + CP1 | **enforced** |
| IR override rewrites a fact -> deviation | none | **GAP (A1 illegal cell)** |
| new pass must declare a contract | none (convention) | **GAP** -> closed by `tests/test_ir_pass_contract.py` |

---

## 5. Named laws (proposed)

| Law | Statement | Owning layer | Gate |
|-----|-----------|--------------|------|
| **LAW-A1-OVERRIDE-PROV** | Any `WidgetIrOverrides` field that changes a clean-tree fact must emit a provenance mutation (`checkpoint=A1_merge`, `transform=ir_override`) per changed field path. | `merge_ir_node` / `_apply_ir_overrides` | `tests/test_ir_merge_override_provenance.py` (P0, Milestone 1) |
| **LAW-A1-DROP-VISIBLE** | A clean child dropped by merge that is not covered by a preserve predicate must be recorded (deviation) or forbidden. | `merge_ir_node` | new (P1) |
| **LAW-PASS-CONTRACT** | Every registered `Pass` declares non-empty `mutates` and `preserves` from the known vocabulary; undeclared mutation is rejected. | pass registry | `test_ir_pass_contract.py` (P0, this increment) |
| **LAW-A1B-DROP-PROV** | IR children dropped by reconcile because they are absent from the clean parent map must be recorded, not only warned. | `validate/graph.py` | new (P2) |
| **LAW-A2-HARD** | Hard geometry-invariant violations raise before emit. | normalize | already enforced |
| **LAW-A1-FIDELITY-AUTHORITY** | LLM-authored `fidelity_tier`/`tier_source` is stripped at `sanitize_screen_ir_llm_drift`; `stamp_fidelity_tiers` always resolves semantic tiers from manifest/policy (never trusts payload tier or `tierSource=manual_override`). | `presence/sanitize.py`, `fidelity/stamp.py` | `tests/test_fidelity_authority.py` (P0, Milestone 1) |
| **LAW-A1-DERIVED-STRIP** | LLM-authored `layout_hints` (a pass-owned derived field) is stripped before IR passes. | presence sanitize | new (P2) |
| **LAW-WIDGETIR-CONSERVE** | Extracted widget IR is conserved (identity + multiset) against its extracted clean subtree. | `generator/ir/extracted.py` | new (P2) |

> Analysis backing these laws (LLM geometry-rewrite channels, intent-vs-derived split,
> hypothesis/doubt adjudication) is in [`ARROW_ANALYSIS.md`](ARROW_ANALYSIS.md).

---

## 6. Open enforcement gaps (prioritised)

- **P0** — `LAW-PASS-CONTRACT` self-test so a new pass without a contract entry fails CI
  (готовности criterion 3). Delivered with this increment.
- **P0** — `LAW-A1-FIDELITY-AUTHORITY`: strip LLM fidelity fields at sanitize ingress;
  stamp always re-resolves from manifest/policy. Delivered Milestone 1.
- **P0** — `LAW-A1-OVERRIDE-PROV`: route `_apply_ir_overrides` fact changes through
  `record_deviation`. Additive; does not change emitted Dart.
- **P1** — `LAW-A1-DROP-VISIBLE`: record silently dropped merge children.
- **P2** — extend `validate_pass_mutates` to check declared `screen_ir.*` IR-side tokens,
  closing the IR-side contract gap.
- **P2** — add a `reads` dimension to `Pass` and to this matrix (currently only
  `mutates`/`preserves` exist).

---

## 7. Contribution rule

A new IR pass or cross-graph arrow is not review-complete until:

1. it declares `mutates` / `preserves` (and, once added, `reads`);
2. its row exists in this matrix;
3. a conservation or field-preservation test asserts its `must_preserve` set;
4. any fact mutation carries a `DeviationRecord`.

`tests/test_ir_pass_contract.py` enforces (1) for registered passes today.
