# EPIC 0 — Foundation of fidelity

**Source:** [semantic-core.md](semantic-core.md) (lines 23–39)

**Principle:** pixel fidelity is law; semantics is an optimization on top of honest input.

## Wave checklist

### Wave 0a (serial)

- [x] **E0.6** — `load_fetch_result_from_dump` rejects processed dumps (`parserVersion`); pytest does not write to production log
- [x] **E0.5** — IR fallback `("llm_validated", "llm_parsed")` only; `pre_emit` write-only + `emitterVersion` marker

### Wave 0.0 (harness, before 0c/0b z-order tests on restored nodes)

- [x] **E0.0** — `tests/support/conservation.py`: `assert_node_multiset_preserved` + `assert_stack_z_order_preserved`

### Wave 0c then 0b (sequencing)

- [x] **E0.1** — top-level cluster dedup = same as subtree (`prune_duplicated_cluster_subtrees`); no sibling drop
- [x] **E0.2** — do **not** fold `render_bounds_expand` into `stack_placement`; keep field for `stack_needs_soft_clip`; **no emit Padding**

### Wave 0b

- [x] **E0.3** — `resolve_stack_child_order`: clean-tree authoritative; tests include pruned duplicate instances (after E0.1)
- [x] **E0.4** — `accessibility.auto_fix` provenance logging; `apply_pixel_perfect_profile` alias (default `auto_fix` unchanged — product decision)

## DoD notes

- E0.1/E0.2 tests run **deterministic** (`normalize_clean_tree` + `render_node_body`) **and** **IR** (`merge_screen_ir` + `emit_merged_root_expression`) paths.
- E0.1: `fail_duplicate_clusters` gate accepts K layout refs when K pruned instances remain (**OPEN** until manual `task_management` signoff).
- E0.2: placement stays `left/right/height` from Figma bbox; `Clip.none` from `render_bounds_expand` field.

## Manual acceptance

`task_management`: 6 icons, cards 331×94 @ (22,y), card 101:307 no text overlap, fonts 9/11px preserved.

## Verification

| Wave | Command |
|------|---------|
| 0a | `poetry run pytest tests/test_dump_hygiene.py tests/test_ir_load.py -q` |
| 0.0–0c | `poetry run pytest tests/test_conservation_harness.py tests/test_cluster_dedup_ref.py tests/test_render_bounds.py -q` |
| 0b | `poetry run pytest tests/test_ir_stack_order_merge.py tests/test_z_order_unstack_precondition.py tests/test_accessibility_provenance.py -q` |
| Final | `poetry run pytest -q -m "not live_figma"` |
