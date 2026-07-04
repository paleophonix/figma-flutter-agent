# Pipeline contracts (compiler)

Master invariant: every stage must **preserve a Figma fact**, **create a named deviation with provenance**, or **downgrade fidelity**. Most "emitter bugs" are information loss on arrows before emit.

## Diagnose / repair routing

1. Symptom → **first arrow** where a fact changed (not where it became visible).
2. Mechanism → `family_id` from `corpus/families.yaml` — never a visual symptom (`overflow`, `wrong_checkbox`).
3. **Corpus lookup (read-only)** → `corpus/index/<family_id>.yaml` (scan rows; open one `corpus/cases/<case_id>.yaml`). Do not load every case file.
4. Fix → **owning layer** from the law table; generic algorithm only.

**Corpus writes:** `.claude/` agents **read** corpus only. Creating/updating
`corpus/cases/`, `status: OPEN`/`FIXED`, and `defects index --write` — **Cursor**
(`.cursor/skills/`, `.cursor/rules/`).

Arrow IDs: `A1` merge, `A1b` IR reconcile/heal, `A2` normalize, `A3` emit, `CP2` IR passes, `A4` parse, `NONE` infra.

## Field vocabulary (`WidgetIrNode` / clean tree)

| Class | Authority | Examples |
|-------|-----------|----------|
| **fact-mirror** | clean tree | `figma_id`, child id set, stack order |
| **intent** | LLM proposes; compiler gates | `kind`, `ref`, `overrides`, `wrap`, `payload`, `omit_figma_ids` |
| **derived** | pass/compiler only; LLM must not author | `layout_hints`, `fidelity_tier`, `tier_source` |

Clean-tree geometry/style/type/paint-order are **facts**. Mutate only with named deviation or policy.

## LLM geometry channels (effective emit, not raw x/y)

| Channel | Field | Effect | Gate (Milestone 1) |
|---------|-------|--------|-------------------|
| Node deletion | `omit_figma_ids` | removes subtree from emit | reconcile |
| Flex rewrite | `wrap` | discards fixed Figma size | partial |
| Text/style rewrite | `overrides.*` | changes measured box / colors | **LAW-A1-OVERRIDE-PROV** |
| Fidelity self-promotion | `fidelity_tier`, `tier_source` | opens native emit without manifest | **LAW-A1-FIDELITY-AUTHORITY** |
| Layout hints | `layout_hints` | seeds spacing/heights | P2 strip |

`tierSource=manual_override` from LLM payload is **not** trusted authority.

## Arrow catalog (preserved / lossy / illegal)

### A1 — clean tree + screen IR → merged clean tree

Code: `generator/ir/tree.py` (`merge_screen_ir`, `_apply_ir_overrides`).

- **Preserved:** multiset (minus omit), stack paint order, stack-placed visuals omitted from IR, flow-layout siblings under partial IR.
- **Inferred:** child order from IR; extracted substitution.
- **Lossy:** clean children not in IR and not matched by preserve predicate — dropped silently (**P1 LAW-A1-DROP-VISIBLE**).
- **Illegal (fixed M1):** overrides changing facts without provenance mutation.

### A1b — IR validate / reconcile / heal

Code: `generator/ir/validate/graph.py` (`sync_screen_ir_graph_to_clean_tree`).

- **Preserved:** parent→child links, stack order from clean tree.
- **Inferred:** stub nodes, reparenting, realign.
- **Lossy:** IR children absent from clean parent — warning only (**P2 LAW-A1B-DROP-PROV**).
- Exists because A1 treats `children` as intent instead of fact-mirror.

### A2 — normalize clean tree

Code: `generator/normalize.py`. Best-gated arrow: hard geometry violations → `GenerationError`; soft → marked deviation (**LAW-A2-HARD**).

### A3 — merged tree + IR → Dart

Code: `generator/ir/expression.py`. Read-only: facts must survive A1/A2. Native emit gated by `fidelity_tier` + `report_only`.

### A4 — Figma JSON → clean tree

Code: `parser/`. Source of all tier-1 facts.

### CP2 — dual-graph IR passes

Every registered pass declares `mutates` / `preserves` (**LAW-PASS-CONTRACT**, `tests/test_ir_pass_contract.py`).

## Named laws

| Law | Statement | Owning layer | Gate |
|-----|-----------|--------------|------|
| **LAW-A1-FIDELITY-AUTHORITY** | Strip LLM `fidelity_tier`/`tier_source` at `sanitize_screen_ir_llm_drift`; stamp always resolves from manifest/policy. | `presence/sanitize.py`, `fidelity/stamp.py` | `tests/test_fidelity_authority.py` |
| **LAW-A1-OVERRIDE-PROV** | Each override fact change → provenance mutation (`A1_merge` / `ir_override`) per field path. | `_apply_ir_overrides` | `tests/test_ir_merge_override_provenance.py` |
| **LAW-PASS-CONTRACT** | Registered pass must declare non-empty mutates/preserves. | pass registry | `tests/test_ir_pass_contract.py` |
| **LAW-A1-DROP-VISIBLE** | Silent merge child drop forbidden without deviation or policy. | `merge_ir_node` | P1 |
| **LAW-A1B-DROP-PROV** | Reconcile child drop must be recorded. | `validate/graph.py` | P2 |
| **LAW-A1-DERIVED-STRIP** | LLM `layout_hints` stripped before passes. | presence sanitize | P2 |
| **LAW-WIDGETIR-CONSERVE** | Extracted widget IR conserved vs clean subtree. | `generator/ir/extracted.py` | P2 |
| **LAW-A2-HARD** | Hard geometry invariant violations raise before emit. | normalize | enforced |

## Enforcement gaps (open)

- IR-side `screen_ir.*` mutations declared but not fully checked by `validate_pass_mutates`.
- Merge multiset: test-only, not raised in merge.
- Pass `reads` dimension not yet in contract.

## Enforcement order (by field family)

1. Style/text overrides → LAW-A1-OVERRIDE-PROV
2. Fidelity/semantic tier → LAW-A1-FIDELITY-AUTHORITY
3. Identity/children multiset → LAW-A1-DROP-VISIBLE + collapse A1b compensators
4. Geometry sizing (`wrap`, omit, layout_hints)
5. Extracted widget subtree → LAW-WIDGETIR-CONSERVE

## Contribution rule

New IR pass or arrow is not review-complete until:

1. declares `mutates` / `preserves` (and `reads` when added);
2. has a row in this contract;
3. has conservation or field-preservation test;
4. any fact mutation carries provenance.

## Verdict

Schema conflates **intent** with **derived** facts. Fix by family, not screen. Compensators (`ensure_ir_direct_children_match_clean`, etc.) are symptoms of missing A1 fact-mirror contract on `children`.
