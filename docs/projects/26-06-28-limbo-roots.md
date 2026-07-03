# Limbo Marathon — Consolidated Root-Level Diagnosis

Status: diagnosis only (no fixes applied). Source: ~13 `/diagnose` runs over the `limbo`
screen set (place_order, mobile_checkout, payment_history_1, my_orders_02, reminders,
gist_add_expenses_945, light_theme_06, sign_up_version_5, sign_up_version_9,
login_version_10, feedback). Date: 2026-06-28.

This document maps every observed failure to a **root family** with a named law, owning
compiler layer, evidence, proposed fix, and regression test. It is a handoff artifact for
whoever implements the repair — it does not contain fixes.

---

## 0. Meta-finding

The marathon produced 13 distinct crashes/visual breaks across screens. They are **not 13
bugs — they are ~6 root families plus 6 cross-cutting anti-patterns.** The single
structural cause:

> The compiler emits Dart and discovers breakage at `flutter run`. It has almost no
> **pre-flight invariants** at the plan/emit boundary. The same root surfaces three ways
> (StackOverflow, raw compile-fail, typed `PlannedDartGraphError`) depending only on which
> downstream tool happens to trip first.

The highest-leverage program is therefore a **pre-flight invariant layer** (Section 8) that
converts entire crash families into typed errors at plan time, plus the specific root fixes
below. Fix the engines, not the screens.

---

## 1. R-C — Planned-graph integrity / cluster-dedup generation  · **P0**

The cluster/component-dedup subsystem produces broken widget graphs in four distinct ways.

- **law:** `cluster_widget_graph_acyclic_nonempty_resolved` — the generated widget graph is
  acyclic; every widget class has real content; every `import` + ctor reference resolves to
  a generated planned file; pruning a widget reconciles all consumers.
- **layer:** `generator` component-dedup / `cluster_variants` + `generator/planned/reconcile`
  (`delegate_repair.repair_self_referential_widget_builds`, `widget_prune`, `sync_widget_imports`)
  + `subtree` render.
- **evidence (4 facets):**
  1. **Empty bodies** — `ImageCardWidget`, `SectionHeaderWidget` rendered
     `SizedBox.shrink()` (light_theme_06). Component content lost into an empty placeholder.
  2. **Mutual-reference cycle** — `Cluster10287Widget.build → Clusterd2e87d01Widget` and
     vice versa → `StackOverflowError` (light_theme_06,
     `clusterd2e87d01_widget.dart:15`). Self-ref guard catches `A→A`, not `A→B→A`.
  3. **Prune without consumer reconcile** — `clusterd2e87d01_widget.dart` pruned, but
     `section_header_widget.dart:7` still imports + instantiates it → compile fail
     (light_theme_06). The `pre_launch_stale_import_scan` did **not** catch it because it
     covers `lib/generated/*_layout.dart` consumers, not `lib/widgets/*` → `lib/widgets/*`.
  4. **Ref without def** — `feedback_layout.dart:15-16` imports + uses `StarFilledWidget`,
     `TagWidget`; neither file was generated → `PlannedDartGraphError:
     pre_launch_stale_import_scan` (feedback). Here the scan **did** fire (layout consumer).
- **proposed fix:**
  - cycle detection over the full widget-reference graph (not just direct self-ref);
  - plan-time invariant `ref ⟹ generated def` (every imported + instantiated widget exists
    as a planned file) — fail before analyze, not at pre-launch;
  - prune removes a widget only when no live reference remains, else reconciles the consumer
    (drop import + replace/inline reference);
  - extend `pre_launch_stale_import_scan` to **widget→widget** imports (closes facet 3 gap);
  - the analyze gate must validate the **committed on-disk** artifact, not a staged copy
    (the light_theme_06 cycle passed `dart analyze` exit 0, then failed at `flutter run`).
- **tests:**
  - `test_cluster_widget_graph_no_cycles` — two dedup aliases of one component → no mutual
    reference; both render content.
  - `test_widget_ref_resolves_to_generated_def` — IR references widget X → planned file X
    exists, else typed error at plan.
  - `test_prune_reconciles_consumers` — prune widget with a live consumer → import/reference
    removed, graph compiles.
  - `test_stale_import_scan_covers_widget_to_widget` — `lib/widgets/a.dart` imports pruned
    `b.dart` → typed error.
- **depends_on:** none.

---

## 2. R-V — Root-viewport wrapper / presentation  · **P0 / P1**

One wrapper produces three opposite failure modes depending on root type and host.

- **law:** `root_wrapper_constraints_sound` — the root container receives constraints under
  which it can lay out: a Stack root gets a finite extent on the scroll axis; a Column root
  is not clamped below its content; a fixed-mode screen is presented at its artboard size
  (letterboxed), not stretched by the host.
- **layer:** `generator/layout` root-viewport wrapper + presentation host
  (`*_screen.dart` / `main.dart` wrapping).
- **evidence:**
  1. **Stack root no finite height** — root `Stack` with only `Positioned` children under a
     vertical `SingleChildScrollView` → `size.isFinite` assertion (login_version_10,
     `SizedBox(width:375)` with height dropped).
  2. **Column root over-clamp** — content Column wrapped in `SizedBox(height:844)` +
     `OverflowBox(maxHeight:844)` → `RenderFlex overflowed by 639px` when content > artboard
     (light_theme_06).
  3. **Fixed-width defeated by tight host constraints** — `SizedBox(width:375)` inside
     `Material → SingleChildScrollView` receives tight viewport width; `enforce()` clamps 375
     to the window width → content stretches; `width: double.infinity` children fill it
     (sign_up_version_5). The layout file is correctly 375; the **presentation wrapper**
     stretches it. Fixed mode is honored in config (`responsive_enabled:false`) but not in
     presentation.
- **proposed fix:** root Stack gets `height = max child extent / artboard height`; Column
  root is not height-clamped (scroll sizes to content); fixed-mode root presented via
  `Align`/`Center` (loose width) or a host that constrains the viewport to the artboard.
- **tests:**
  - `test_absolute_stack_root_has_finite_height` — Positioned-only Stack root in scroll → no
    `size.isFinite`.
  - `test_column_root_not_overclamped` — content taller than artboard → scrolls, no overflow.
  - `test_fixed_mode_presented_at_artboard_width` — fixed screen in wider host → 375 centered,
    not stretched.
- **depends_on:** none.

---

## 3. R-L — Layout-soundness invariant (proactive guard + flex-double-wrap fix)  · **P0**

A single emit-time theorem-checker catches a whole family of runtime layout crashes.

- **law:** `emitted_layout_is_renderable` — emitted constraints are satisfiable:
  - no nested flex parent-data widgets (`Expanded`/`Flexible` not stacked on the same child);
  - `contentPadding.vertical < box.height`;
  - every `Stack` has a determinable size;
  - no `BoxConstraints` forcing infinite width/height into a finite child.
- **layer:** `generator/layout` flex-wrap emit (`_wrap_sizing` + `_apply_layout_slot_wraps`
  double-application) + a new IR/emit invariant pass (ir_validate as theorem-checker).
- **evidence:**
  1. **Double flex-wrap** — `Flexible(child: Expanded(...))` writes competing `FlexParentData`
     → `Incorrect use of ParentDataWidget` + cascade (`infinite width`, `box.dart:2251`,
     `hit test never laid out`) (light_theme_06, `section_header_widget.dart`). Matches the
     known "two passes both wrap" note.
  2. **Padding exceeds box** — input `contentPadding: fromLTRB(14,27,14,27)` in `height:46`
     box (27+27 > 46) → value text + suffix icons pushed out of view (sign_up_version_9).
  3. (Catches retroactively) R-V's `size.isFinite` and the infinite-width cascade.
- **proposed fix:** remove the double flex-wrap (one flex source per child); add the
  layout-soundness pass that asserts the four properties pre-emit and fails with a typed
  error naming the node.
- **tests:**
  - `test_no_nested_flex_parent_data` — child wrapped twice in flex → typed error / single
    wrap.
  - `test_content_padding_fits_box` — padding.vertical ≥ box height → typed error.
  - `test_layout_soundness_pass_on_corpus` — corpus emits 0 soundness violations.
- **depends_on:** none. **This is the keystone proactive guard.**

---

## 4. R-F — Mixed flow/absolute container emit  · **P1**

- **law:** `mixed_positioning_container_partitioned` — a container with both AUTO (flow) and
  ABSOLUTE children emits flow children inside their auto-layout Column and absolute children
  as `Positioned` overlays; no bare non-Positioned child in a Stack that has Positioned
  siblings.
- **layer:** `generator/layout` stack child emit / flow grouping.
- **evidence:**
  1. **Bare flow children in Stack** — `Content` container (4 AUTO sections + 1 ABSOLUTE
     pattern) emitted all 4 flow children bare in a `Stack(Clip.none)` → they pile at origin
     and overlap = "фарш" (sign_up_version_5, `42:2282`).
  2. **Absolute decoration as flow child** — decorative `Ellipse` (absolute `bottom:-130`,
     320px) emitted as a flow Column child → +320px → `RenderFlex overflow 297px`
     (login_version_10, `56:2126`).
- **proposed fix:** partition mixed containers; group consecutive AUTO children into a Column;
  ABSOLUTE children become Positioned overlays.
- **tests:** `test_mixed_flow_absolute_groups_flow_children` — AUTO siblings + ABSOLUTE overlay
  → `Stack[Column(auto), Positioned(absolute)]`, no bare overlapping children; negatives:
  all-AUTO → Column, all-ABSOLUTE → all Positioned.
- **depends_on:** none (overlaps R-L for the overflow facet).

---

## 5. R-N — Name-laundering of leaf semantic types  · **P1**

- **law:** `leaf_type_is_structural_not_name` — INPUT/BUTTON/SLIDER (and peers) are assigned
  from structure (track+thumb, single control, etc.), never from the layer name; a
  name-derived type carries `derived_from_name` provenance and is downgraded before any
  tier-1 classifier / emit decision. (Project-bible §3.2.1.)
- **layer:** `parser` type inference (`infer_leaf_type` / `type_trust`).
- **evidence:**
  1. **SLIDER** — INSTANCE named "Content row slider" → `NodeType.SLIDER` → Material
     `Slider`, carousel discarded (light_theme_06, `3212:20170`). Siblings named "Content
     row" → ROW (correct).
  2. **INPUT** — FRAME named "Input" (6 children, a form card) → `NodeType.INPUT` → lost card
     decoration (login_version_10, `55:2044`).
  3. **BUTTON** — FRAME named "Button" (social row of 4) → `NodeType.BUTTON` → single button
     with overlapping icon children (login_version_10, `56:2102`).
  4. **nav_bottom_bar** — footer typed `BOTTOM_NAV` from name/structure → emitted as
     `BottomNavigationBar` over a CTA footer (place_order, `_is_nav_bottom_bar` keys on
     `type == BOTTOM_NAV`).
- **proposed fix:** drop name-matching for interactive leaf types; structural-only assignment;
  provenance + downgrade. (Higher regression risk — touches the classifier; gate with
  negative tests on real controls.)
- **tests:** `test_named_frame_not_leaf_type` — FRAME with children named Input/Button/slider
  → not a leaf type, children preserved; negative: real single control → leaf type ok.
- **depends_on:** none.

---

## 6. R-I — InputField contract  · **EPIC (separate track)**

Carved out per product instruction: the input emit path is shared by every form; a wrong fix
regresses all forms. Two emit paths, both broken differently, plus a repair-loop misroute.

- **law:** `input_host_emits_functional_field` — an input host emits a functional
  `TextFormField` (value → `initialValue`, helper icons → `suffixIcon`) with
  `contentPadding` that fits the box; an extracted-widget call passes only named args the
  generated class declares.
- **layer:** `generator/layout/widgets/input` (inline + extracted emit) +
  `parser/interaction/input_fields` + `stages/llm_repair` routing.
- **evidence:**
  1. **Extracted path — signature mismatch** — `InputFieldWidget(label:…, isSelected:…)` for
     every field, but the generated class declares neither → `undefined_named_parameter` →
     analyze hard-fail → write rollback (sign_up_version_5, `:73`).
  2. **Inline path — static text + padding clip** — input host inlined as
     `Container → Text('Lois')` (not `TextFormField`) with `contentPadding 27` in a 46px box
     → non-functional, values + eye/calendar icons clipped out of view (sign_up_version_9).
  3. **Repair-loop misroute** — the deterministic signature mismatch was sent to LLM repair
     (3 attempts, CPI escalation, stagnation, exhausted) instead of a deterministic fix
     (sign_up_version_5). Violates project-bible §8.
- **proposed fix (sequence):**
  - **S1:** extracted call args ⊆ generated def params (plan-time invariant); deterministic
    signature mismatches do **not** enter LLM repair.
  - **S2:** inline input → real `TextFormField`; `contentPadding = (boxH − glyphH)/2`.
  - **S3:** suffix icons (eye/calendar) → `IconButton`, not clipped static SVG.
- **tests:** `test_extracted_widget_call_args_match_def`; `test_inlined_input_is_textfield_padding_fits`;
  `test_input_suffix_icon_visible`; `test_deterministic_error_not_routed_to_llm`.
- **depends_on:** R-C (shares the ref/def conservation thread).

---

## 7. R-D — Fidelity tail  · **P2 (defer / spin-off)**

Visual/quality, non-crashing once the P0/P1 roots land. Listed for completeness.

| id | law | evidence |
|----|-----|----------|
| D1 | `icon_glyph_preserves_frame_padding` | glyph-only SVG rendered `BoxFit.contain` into 24×24 frame → upscaled/oversized arrow (light_theme_06, sign_up_9, login_10) |
| D2 | `missing_asset_degrades_with_provenance` | render-boundary SVG / gradient PNG missing offline → white bg or hard crash (sign_up_5, sign_up_9, login_10); resolver warns "placeholder" but doesn't degrade (see M2) |
| D3 | `image_clip_shape_matches_figma` | row avatars `ClipOval` (circle) where Figma is square; carousel cards unclipped (light_theme_06) |
| D4 | `render_boundary_excludes_text_content` | flatten bakes interactive/text content into one SVG/PNG (place_order links; sign_up_5 53-node bake) — partial guard landed (accent-text, color-specific) |
| D5 | `divider_matches_figma_source` | row separators emitted as ~15% gradient hairline, near-invisible (light_theme_06) — source unconfirmed |

---

## 8. Cross-cutting anti-patterns (meta)

These underlie multiple roots and are the highest-leverage preventive work.

- **M1 — Two-stage divergence (single source of truth).** Two stages independently recompute
  a "what's allowed / what's the shape" set and diverge. Confirmed 4×:
  - `zip(tree.children, methods, strict=True)` where `methods = plan_layout_methods(tree)` but
    composed against `render_tree` (wallpaper partition) → `ValueError: zip argument 2 longer`
    (sign_up_version_9);
  - sanitize allows `extractedWidgets ∪ subtree_specs`, validate checks only
    `extracted_widget_names` → `extracted widget not in extractedWidgets`
    (sign_up_version_9; same error surfaced at both `llm` and `plan` stages across runs —
    proves call-site inconsistency);
  - asset resolver soft-warn vs `_validate_asset_paths` hard-fail (sign_up_version_5);
  - analyze gate validates staged state ≠ committed disk (light_theme_06).
  **Fix:** compute allowed-sets / shapes once and share; all gates validate the final artifact.
- **M2 — Soft-warn without actual degradation.** A pass logs "may use placeholder /
  fallback / degrade" but leaves the node in an unsafe state; a downstream hard guard trips.
  Confirmed: `resolve_render_boundary_asset_keys` warns placeholder but leaves a dangling
  `vector_asset_key` → `_validate_asset_paths` hard-fail (sign_up_version_5). **Fix:** every
  degrade/warn path mutates the node to satisfy downstream invariants (conservation:
  warn ⟹ safe state). Audit all `logger.warning(... placeholder/fallback/degrade ...)` sites.
- **M3 — Deterministic failures routed to LLM repair.** `undefined_named_parameter` on a
  generated widget, missing import, missing asset are deterministic graph/contract errors.
  Routing them to the LLM loop burns budget and ends in stagnation/abort (sign_up_version_5,
  §8 violation). **Fix:** a pre-analyze classifier intercepts known-deterministic signatures
  and routes to a deterministic fixer / typed error, bypassing LLM repair.
- **M4 — Conservation gaps at parser→IR→emit boundaries.** Node/text multiset is conserved
  only in geometry (CP1). Parser dropped link text nodes between `raw → processed`
  (place_order: "Select"/"Know More"/"Apply Coupon" present in raw, gone in processed) with
  no alarm. **Fix:** node/text-multiset conservation checkpoints at each boundary; a drop is a
  named deviation, not silent. (Verify scope first.)
- **M5 — Idempotency (verify).** `normalize_screen_ir_presence` logged `+13`, `+28`, `+71`
  nodes on repeated passes with differing counts. Project-bible requires stages idempotent
  (re-run = no-op). If presence-normalize drifts on its own output, it is a silent
  graph-desync source. **Fix:** assert second pass adds 0. (Hypothesis — verify against code.)
- **M6 — Magic-threshold silent classifiers.** Tuned constants flip behavior invisibly
  (`_MIN_CHECKOUT_FOOTER_CTA_WIDTH`, boundary-collapse thresholds, 48dp). **Fix:** registry +
  "decision taken by threshold X" provenance log.

---

## 9. Recommended batching / execution order

Principle: ship the **pre-flight invariant layer first** — it unblocks observation (crashing
screens render nothing) and converts future crash families into typed plan-time errors.

**Batch 1 — pre-flight guards (P0, narrow, highest leverage):**
- **R-C** planned-graph integrity (acyclic, ref⟹def, prune-reconcile, widget→widget scan,
  gate-on-disk)
- **R-V** root-viewport wrapper (finite Stack height, no Column over-clamp, fixed-mode Align)
- **R-L** layout-soundness invariant (no double flex-wrap, padding<height, Stack sizeable,
  no infinite extent)

These three guards retroactively cover: StackOverflow, dangling-import compile-fail,
PlannedDartGraphError, `size.isFinite`, overflow, ParentData crash, padding-clip.

**Batch 2 — structural emit (P1, after Batch 1 verified):**
- **R-F** mixed flow/absolute partitioning
- **R-N** name-laundering removal (higher risk — gate with classifier negative tests)

**Epic S — InputField contract (separate track):** S1 → S2 → S3.

**Backlog D — fidelity tail (P2):** spin-off / defer.

**Cross-cutting:** fold M1/M2/M3 into Batch 1 (they are the same guards expressed as
contracts); M4/M5/M6 require a code-survey spike before implementation.

---

## 10. Needs verification before fixing (do not implement blind)

- M4 scope: how many parser/IR/emit boundaries lack node/text conservation (grep + count).
- M5: is `normalize_screen_ir_presence` actually non-idempotent, or are the `+N` counts from
  distinct inputs per stage?
- M1: enumerate every place two stages recompute an allowed-set / shape (grep the
  `extracted` / `allowed` / `methods` / `render_tree` divergences).
- R-D5: identify the Figma source of the row separators (real node vs card shadow vs synthetic).

Confidence: R-C, R-V, R-L, R-F, R-N, R-I, M1, M2, M3 — directly observed (high). M4 partial
(observed the drop, not the full scope). M5, M6, D5 — hypotheses from logs, verify against
live code first (project-bible: ASK THE CODE).
