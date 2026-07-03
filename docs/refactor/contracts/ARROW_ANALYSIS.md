# ARROW_ANALYSIS — analysis phase (RAR program 01)

> **Agent instructive copy:** `.cursor/rules/pipeline-contracts.mdc` (keep in sync when analysis changes laws).

**Companion to** [`PIPELINE_ARROWS.md`](PIPELINE_ARROWS.md) (the matrix).
**Scope:** answers the three questions, adjudicates the two hypotheses, and resolves the
two doubts from `refactor/01_compiler-semantics-ir-contract.md`, with live-code evidence.

---

## 1. Questions

### Q1 — Where can the LLM rewrite geometry the clean tree already fixed?

The LLM authors the **full `ScreenIr`**, not a slim subset:
`FlutterGenerationResponse.screen_ir: ScreenIr | None` (`schemas/generation.py:41`) embeds
`ScreenIr.root: WidgetIrNode` (`schemas/ir.py:319`). Although `WidgetIrNode` uses
`extra="forbid"`, every declared field is LLM-authorable, and only
`classification_hint` is stripped before passes (`presence/semantics.py:55`,
`sanitize.py:331`). Nothing strips LLM-authored `layout_hints`, `wrap`, `overrides`, or
`fidelity_tier`. That opens five channels into geometry/emit:

| # | Channel | Field | Effect on geometry | Gate today |
|---|---------|-------|--------------------|-----------|
| 1 | **Node deletion** | `ScreenIr.omit_figma_ids` | node + its bounds removed from emit | none (merge respects omit unconditionally, `tree.py:156`) |
| 2 | **Fill/flex rewrite** | `WidgetIrNode.wrap` | fixed-size node becomes `Expanded`/`Flexible`, discarding Figma size | none (`apply_ir_wrap`, `expression.py:393`) |
| 3 | **Text-metric rewrite** | `overrides.font_size` (+ colors/text) | changes measured text box, rewrites `style.font_size` | none, no `DeviationRecord` (`_apply_ir_overrides`, `tree.py:74`) |
| 4 | **Fidelity self-promotion** | `fidelity_tier` / `tier_source` | LLM forces `native_verified` → native emit path, bypassing manifest | **trusted** by stamp (see below) |
| 5 | **Latent layout hint** | `layout_hints.min_height` / `flex_spacing` / `explicit_gaps` | seeds spacing/heights consumed by emit | overwritten **only if** the relevant pass touches that node; otherwise survives |

**Channel 4 is the sharpest.** `_stamp_node` (`fidelity/stamp.py:61-64`):

```python
elif node.fidelity_tier is not None:
    stamped = node                     # keeps the LLM-provided tier
    if node.tier_source is None:
        stamped = node.model_copy(update={"tier_source": TierSource.MANUAL_OVERRIDE})
```

The manifest is consulted **only** when `fidelity_tier is None`. An LLM-set tier is trusted
and merely relabelled `MANUAL_OVERRIDE`. The pipeline cannot distinguish a legitimate manual
override from an LLM self-promotion, because both arrive as `node.fidelity_tier`. This
violates the Bible rule "LLM cannot mutate fidelity manifest / cannot emit from an
unverified tier it assigned itself."

**Answer:** the LLM does not rewrite raw `x/y/width/height` on the clean tree (those stay in
`CleanDesignTreeNode`), but it rewrites **effective emitted geometry** through deletion (1),
sizing wrappers (2), text metrics (3), and fidelity routing (4), and can seed layout hints
(5). Only channel 3's colors and channel 4's tier are recorded; none are gated.

### Q2 — Which IR fields are intent, which are cache-of-facts?

Classification of every `WidgetIrNode` / `ScreenIr` field, with the authority that *should*
own it:

| Class | Fields | Note |
|-------|--------|------|
| **fact-mirror** (clean tree owns; LLM may not invent) | `figma_id`, `children` (id set), `is_selected` (visual state), stack order via `stack_child_order` | reconciled by `sync_screen_ir_graph_to_clean_tree` because the LLM value is untrusted |
| **intent** (LLM proposes, deterministic layer gates) | `kind`, `ref`, `overrides`, `wrap`, `hint_text`, `error_text`, `is_multiline`, `max_lines`, `payload`, `omit_figma_ids`, `adaptive_rules`, `semantic_verdicts` (report-only) | legality decided downstream |
| **derived** (a pass must own; LLM should NOT author) | `layout_hints`, `fidelity_tier`, `tier_source` | **mis-scoped today** — schema lets the LLM write them (Q1 channels 4–5) |

The key finding: the schema conflates **intent** and **derived**. `layout_hints`,
`fidelity_tier`, and `tier_source` are pass outputs, yet the LLM output schema accepts them
and nothing strips them. That is the structural cause of Q1 channels 4–5.

### Q3 — Do we need a `parse → emit → inspect` lens?

**Yes, a thin one.** The current provenance dump (`provenance.json`) records *mutations* but
not a per-node *fact survival* view (Figma value → merged value → emitted value). A lens that,
for a chosen field set (e.g. `text`, `font_size`, `fidelity_tier`, child id set), diffs
`raw.json → pre_emit.json → screen.dart` would make every Q1 channel observable per screen
and turn the matrix into a testable oracle. Recommendation: build it as a debug-only reader
over existing artifacts (no new pipeline stage), scoped to the family under repair — not a
full IR differ. Defer to program 09/10 for the general oracle; program 01 only needs the
field-survival slice for its three arrows.

---

## 2. Hypotheses

### H1 — "Most emitter bugs are information loss on arrows 1–2." — **Supported, with nuance.**

Evidence: a conservative sweep finds **43** reconcile/realign/sync/preserve compensator
functions in `src/` (`def (realign_|ensure_*match|reconcile_|sync_*clean|preserve_clean|_align_ir_)`).
The dominant cluster is **archetype family reconcilers** in `parser/layout/reconcilers_*.py`
(`promo_card`, `playback_timestamp`, `weekday_chip`, `cta_footer`, `checkout_footer`,
`consent_checkbox`, `product_hero`, …). These compensate for facts lost or under-specified
*before* emit — i.e. on parse→IR→normalize — matching the prior audit's "~18% compensator
layer." **Nuance:** many live on arrow A2 (normalize/reconcile) and A4 (parse), not only A1.
So the hypothesis holds if "arrows 1–2" is read as "everything upstream of the emitter,"
which is the practical claim. The emitter itself is comparatively thin.

### H2 — "`ensure_ir_direct_children_match_clean` and similar are symptoms of a missing contract." — **Confirmed.**

The A1b compensator chain (`sync_screen_ir_graph_to_clean_tree` →
`realign_screen_ir_children_to_clean_tree` + `ensure_ir_direct_children_match_clean` +
`_align_ir_stack_children_to_clean_tree`, `validate/graph.py`) exists **only** because the IR
`children` field is treated as intent when it must be a fact-mirror. Each helper maps to a
missing contract cell:

| Compensator | Missing contract it substitutes for |
|-------------|-------------------------------------|
| `ensure_ir_direct_children_match_clean` | `children` = fact-mirror of clean direct-child ids |
| `realign_screen_ir_children_to_clean_tree` | IR parent link = fact-mirror of clean parent map |
| `_align_ir_stack_children_to_clean_tree` | stack child order = fact-mirror of clean paint order |
| `_sync_chip_choice_selected_from_clean_tree` | `is_selected` = fact-mirror of clean visual state |

If `children`/order/selection were declared fact-mirror and validated once, these four
runtime-reconciling walks collapse into a single conservation check.

---

## 3. Doubts

### D1 — "Full formal contract on the whole IR at once is too heavy; incremental per family." — **Accepted; family order fixed.**

Decompose the IR contract into five field families and enforce in ROI order:

1. **Style/text facts** (`overrides.text/colors/font_size`) → LAW-A1-OVERRIDE-PROV. *(P0, additive)*
2. **Fidelity/semantic** (`fidelity_tier`, `tier_source`, `kind`) → strip LLM-authored tier before stamp; keep manifest authority → LAW-A1-FIDELITY-AUTHORITY. *(P0/P1, gates native emit)*
3. **Identity/structure** (`figma_id`, `children`, multiset) → guard merge, collapse A1b compensators → LAW-A1-DROP-VISIBLE. *(P1)*
4. **Geometry/sizing** (`wrap`, `omit_figma_ids`, `layout_hints`) → record/gate LLM sizing rewrites. *(P2)*
5. **Widget IR** (extracted subtrees) → apply conservation, see D2. *(P2)*

Rationale: families 1–2 are additive and close the two illegal cells; 3 removes the largest
compensator cluster; 4–5 are deeper structural work.

### D2 — "Screen IR and widget IR may need different preservation rules." — **Confirmed as a real gap.**

`ExtractedWidget.widget_ir: WidgetIrNode | None` (`schemas/generation.py:19`) proves widget IR
is a separate LLM-authored `WidgetIrNode` subtree. `generator/ir/extracted.py` references
**none** of the screen-IR conservation helpers (`sync_screen_ir_graph_to_clean_tree`,
`ensure_ir_direct_children_match_clean`, multiset/graph-sync checks). So extracted widget IR
currently has **weaker preservation than screen IR** — the same LLM channels (Q1) apply but
without the A1b reconcile safety net. The contract must state which invariants extend to
widget IR (identity, multiset against the extracted clean subtree) and which legitimately
differ (a widget defines its own local root, so screen-level `omit_figma_ids` and root-kind
rules do not apply).

---

## 4. Named-law updates for the matrix

Add to `PIPELINE_ARROWS.md` §5:

| Law | Statement | Owning layer | Priority |
|-----|-----------|--------------|----------|
| **LAW-A1-FIDELITY-AUTHORITY** | LLM-authored `fidelity_tier`/`tier_source` must be stripped before `fidelity_stamp`; only manifest/policy/manual-YAML may set a tier. | fidelity stamp / presence sanitize | P0/P1 |
| **LAW-A1-DERIVED-STRIP** | `layout_hints` authored by the LLM is stripped before IR passes (derived field, pass-owned). | presence sanitize | P2 |
| **LAW-WIDGETIR-CONSERVE** | Extracted widget IR is conserved against its extracted clean subtree (identity + multiset). | `generator/ir/extracted.py` | P2 |

---

## 5. One-line verdict

The IR schema **conflates intent with derived facts**, letting the LLM author
`fidelity_tier` and `layout_hints`; combined with the ungated override channel, that is the
mechanism behind the compensator layer. Fix by family (D1), starting with the two illegal
cells (override provenance, fidelity authority), then collapse the A1b reconcile chain.
