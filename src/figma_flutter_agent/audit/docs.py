"""Generate systemic audit markdown artifacts (phases 1–8)."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.audit.corpus import AUDIT_CORPUS
from figma_flutter_agent.audit.diff_triada import run_diff_triada
from figma_flutter_agent.llm.prompts.principles import SYSTEMIC_BUG_RULES


def write_all_audit_docs(docs_dir: Path) -> list[Path]:
    """Write phase deliverables under ``docs/audit/26-06-13-pipeline-audit/``.

    Args:
        docs_dir: Root audit documentation directory.

    Returns:
        Paths of markdown files written.
    """
    docs_dir.mkdir(parents=True, exist_ok=True)
    artifacts = docs_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, content in (
        ("parse-classification.md", _render_parse_classification()),
        ("interaction-predicates.md", _render_interaction_predicates()),
        ("reconcile-passes.md", _render_reconcile_passes()),
        ("geometry-emit-fidelity.md", _render_geometry_emit_fidelity()),
        ("gates-gap-analysis.md", _render_gates_gap_analysis()),
        ("test-conflicts.md", _render_test_conflicts()),
        ("remediation-backlog.md", _render_remediation_backlog()),
        ("pipeline-contracts.md", _render_pipeline_contracts()),
        ("README.md", _render_audit_readme()),
    ):
        path = docs_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path)
    triada_path = _write_diff_triada_summary(docs_dir, artifacts)
    written.append(triada_path)
    return written


def _write_diff_triada_summary(docs_dir: Path, artifacts_dir: Path) -> Path:
    records = run_diff_triada(output_dir=artifacts_dir)
    lines = [
        "# Diff-triada summary",
        "",
        "Per-corpus normalize → emit snapshot. Full JSON: `artifacts/diff_triada.json`.",
        "",
        "| Pattern class | Feature | Nodes pre→post | Geometry soft | FID-26 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        geom = ", ".join(record.geometry_soft_violations[:3]) or "—"
        fid = ", ".join(record.emit_fidelity_violations[:3]) or "—"
        lines.append(
            f"| {record.pattern_class} | {record.feature_name} | "
            f"{record.node_count_pre}→{record.node_count_post} | {geom} | {fid} |"
        )
    missing = [entry for entry in AUDIT_CORPUS if not entry.layout_path.is_file()]
    if missing:
        lines.extend(["", "## Skipped corpus entries", ""])
        for entry in missing:
            lines.append(f"- `{entry.pattern_class}`: missing `{entry.layout_path.name}`")
    path = docs_dir / "diff-triada-summary.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _render_parse_classification() -> str:
    return """# Parse and node classification audit

## Infer chain (priority order)

1. `parser/tree.py` — `_convert_node`: Figma type → provisional `NodeType`.
2. `parser/layout/grid.py` — `infer_container_type`: auto-layout axis → ROW/COLUMN/GRID.
3. `parser/components.py` — `resolve_semantic_node_type`: API component set → properties → overlay → **name** fallback.
4. `parser/tree_node.py` — `infer_leaf_type`: name tokens (`input`→INPUT, `button`→BUTTON).

## Audit findings

| Risk | Layer | Mitigation |
| --- | --- | --- |
| Name heuristic beats geometry | `tree_node.infer_leaf_type` | Prefer bbox + child structure in `interaction/forms.py` |
| Small square → INPUT not CHECKBOX | `forms.layout_fact_checkbox_control` | `_MIN_CHECKBOX_SIZE = 12`; `layout_fact_hosts_compact_checkbox_control` in emit |
| INSTANCE without components map | `components.py` | Falls through to CONTAINER; name fallback may mislabel |
| Checkbox label in STACK not TEXT | `forms.checkbox_label_text_host` | Unwraps wrapped label for `row_hosts_checkbox_label_pair` |

## Post-parse transforms (bisect order)

| Module | Risk |
| --- | --- |
| `parser/dedup/prune.py` | Prunes skip/checkbox controls before emit |
| `parser/boundaries/heuristics.py` | Boundary collapse vs interactive semantics |
| `parser/stack_paint.py` | Z-order vs checkbox at layout root |
| `promote_flex_hosts_with_absolute_children` | Absolute children inside flex host |

**Method:** disable passes one-by-one on synthetic corpus nodes when misclassification is observed; add generic fixture per fixed predicate.
"""


def _render_interaction_predicates() -> str:
    return """# Interaction predicates inventory

Registry of `looks_like_*` / `hosts_*` predicates and emit consumers.

| Predicate | Module | Thresholds (px) | Emit consumer | Reconcile consumer |
| --- | --- | --- | --- | --- |
| `layout_fact_checkbox_control` | `forms.py` | 12–28 square, border radius ≤10 | `dispatch`, `flex._try_render_checkbox_label_row` | `reconcile_consent_checkbox_rows_in_tree` |
| `layout_fact_hosts_compact_checkbox_control` | `forms.py` | delegates to checkbox | `inline_cluster_control` gate | — |
| `checkbox_label_text_host` | `forms.py` | STACK wrapping single TEXT | `row_hosts_checkbox_label_pair` | — |
| `layout_fact_textarea_field` | `forms.py` | tall multiline INPUT | `dispatch` early return | — |
| `layout_fact_password_field_stack` | `forms.py` | eye icon or dot mask | input decoration | — |
| `layout_fact_back_nav_stack` | `buttons.py` | chevron + compact stack | `dispatch` stack special | — |
| `layout_fact_play_pause_control_stack` | `buttons.py` | media control geometry | `hero` / playback emit | — |
| `layout_fact_compact_icon_action_stack` | `icons.py` | ≤48 hit, vector child | icon button emit | — |
| `layout_fact_hosts_payment_selection_indicator` | `selection.py` | radio/check overlay | payment row emit | `reconcile_payment_selection_state_in_tree` |
| `row_is_*` (flex) | `flex_policy/row.py` | per-predicate | `flex.py` ROW early returns | — |

## Gap

`forms.py` predicates are referenced in 10+ emit sites but only **consent checkbox reconcile** mutates the IR tree. Other mislabels must be fixed at parse or emit predicate level, not per-screen patches.
"""


def _render_reconcile_passes() -> str:
    return """# Reconcile pass coverage

Order in `generator/normalize.reconcile_layout_tree` (14 passes):

| # | Pass | Module | Dedicated test |
| --- | --- | --- | --- |
| 1 | `reconcile_stack_placements_in_tree` | `parser/layout/placement.py` | `test_single_reconcile_pass`, placement tests |
| 2 | `reconcile_render_bounds_expansion_in_tree` | `parser/render_bounds.py` | partial (`test_artboard_frame_growth`) |
| 3 | `reconcile_auth_button_icon_placements_in_tree` | `parser/layout/` | `test_interaction` |
| 4 | `reconcile_promo_card_row_tops_in_tree` | `parser/layout/` | — |
| 5 | `reconcile_grid_child_visual_order_in_tree` | `parser/layout/grid.py` | — |
| 6 | `reconcile_duplicate_product_card_grids_in_tree` | `parser/layout/` | — |
| 7 | `reconcile_cta_footer_surfaces_in_tree` | `reconcilers_ui.py` | `test_sign_up_footer_overlap` |
| 8 | `reconcile_logo_wordmark_top_in_tree` | `reconcilers_ui.py` | — |
| 9 | `reconcile_title_subtitle_stacks_in_tree` | `reconcilers_ui.py` | — |
| 10 | `reconcile_consent_checkbox_rows_in_tree` | `reconcilers_ui.py` | `test_consent_checkbox_row` |
| 11 | `reconcile_payment_selection_state_in_tree` | `reconcilers_ui.py` | — |
| 12 | `reconcile_weekday_chip_row_in_tree` | `reconcilers_ui.py` | chip tests |
| 13 | `reconcile_centered_text_placements_in_tree` | `reconcilers_align.py` | — |
| 14 | `reconcile_playback_timestamp_row_in_tree` | `reconcilers_media.py` | playback tests |

Post-reconcile in `normalize_clean_tree`: `plan_geometry_tree`, `validate_geometry_invariants`, optional `apply_ir_guards`, `reconcile_product_hero_photo_viewport_in_tree`.

## Gaps

Passes 4–6, 8–9, 11, 13 lack dedicated before/after unit tests — add synthetic trees when touching those reconcilers.
"""


def _render_geometry_emit_fidelity() -> str:
    return """# Geometry and emit fidelity audit

## Invariant catalog (T2 / hard)

| Code | Severity | Emit linkage |
| --- | --- | --- |
| `t2_flex_conservation` | soft | `resolve_flex_wrap`, rigid children |
| `t2_bounded_slot_conservation` | soft | `column_bounded_slot_should_grow`, OverflowBox |
| `t2_artboard_extent_drift` | soft | `grow_then_gate`, minHeight vs SizedBox |
| `inv_flex_axis` | hard | Expanded on wrong axis |
| `inv_z` | hard | ghost occlusion |

Tests: `test_extent_conservation`, `test_bounded_slot_conservation`, `test_artboard_frame_growth`, `test_renderflex_overflow_gate`.

## Emit remediation ladder

1. Prefer `minHeight` over fixed `SizedBox(height)` for intrinsic buttons.
2. `OverflowBox` maxHeight uses full slot — padding not subtracted twice (`widgets/text.py`).
3. `flex_host_prefers_min_height_pin` on artboard shell.
4. `predict_typography_slack` included in T2b sums.

## Typography / input contract

- `decoration.py`: `omit_line_height` + line-box `contentPadding` when `vertical_center`.
- `geometry/flex.compute_input_metrics`: prefers value node over hint for metrics.

## FID-26 (`emit_fidelity_audit`)

Corpus diff-triada records `emit_fidelity_violations` per layout. Common codes:

- `layer_blur_missing_backdrop`
- `line_height_missing_strut`
- `bottom_pin_used_top`
- `opacity_missing_wrapper`

See `diff-triada-summary.md` for per-fixture results.
"""


def _render_gates_gap_analysis() -> str:
    return """# Gates gap analysis

| Gate | Source | Covers | Does not catch |
| --- | --- | --- | --- |
| ruff / mypy / pytest | `scripts/signoff.ps1` | style, unit contracts | predicate overlap |
| demo-signoff | `cli/live.py` | 5 Figma samples | structural misclassification |
| fixture-ir-validate | CLI | IR guards on fixtures | deterministic emit-only paths |
| fixture-geometry-check | `fixtures/geometry_check.py` | placements IoU | vertical text offset in inputs |
| spec23 | `validation/spec23/evaluate.py` | production readiness | archetype flatten regressions |
| `runtime_fail_renderflex_overflow` | production profile | golden RenderFlex logs | checkbox→TextField |

## Production vs dev profile

`config/profiles.py`: `strict_geometry_invariants`, `strict_contrast`, `analyze_scope: all_planned`.

**Recommendation:** run `figma-flutter generate` with production profile on customer dumps and compare soft invariant counts with dev baseline.
"""


def _render_test_conflicts() -> str:
    return """# Test conflict pairs

Explicit pairs to review when adding ROW archetypes or overflow guards.

| Test A | Test B | Contract |
| --- | --- | --- |
| `test_space_between_row_binds_fixed_stack_width_and_height` | `test_space_between_total_row_flattens_label_and_price` | absolute Stack slots vs metric-row flatten |
| `test_tight_chip_row_text_clips_with_expanded` | `test_column_status_pill_centers_discount_label` | Expanded+ellipsis vs FittedBox pill |
| overflow guard rows | `layout_fact_row_tight_horizontal_pill_label` | unpainted tight row vs painted pill |

## Fixture gaps (closed in this audit)

- `consent_checkbox_row.json`, `flex_summary_row.json`, `prefilled_input_field.json` — synthetic minimal trees.
- `bounded_order_card.json` — added to `screens.yaml`.
- `elastic_form_a11y.json`, `deep_nesting_8x.json`, `variant_topology.json` — in corpus; raw Figma skipped by diff-triada.

## `profile_edit_layout.json`

Tests `test_profile_edit_layout.py` and `test_view_renders.py` optionally load ataev dump; no committed fixture. **P3:** add generic profile-edit fixture or gate tests with `pytest.mark.skipif` when dump absent.
"""


def _render_remediation_backlog() -> str:
    return f"""# Remediation backlog (P0–P4)

| Sev | Finding | Layer | Status |
| --- | --- | --- | --- |
| P0 | Checkbox mislabeled INPUT (13px square) | `forms.layout_fact_checkbox_control` | **Fixed** — min size 12, label host unwrap |
| P0 | TextField vertical misalign | `input/decoration.py` | **Fixed** — line-box padding, omit line height |
| P1 | spaceBetween flatten vs absolute stack guard | `flex_policy/row.py` | **Fixed** — block flatten when absolute/fixed stack |
| P1 | Unpainted tight row → FittedBox pill | `layout_fact_row_tight_horizontal_pill_label` | **Fixed** — require `background_color` |
| P2 | Soft `t2_artboard_extent_drift` on large corpus | geometry planner | monitor via diff-triada |
| P3 | Orphan fixtures without golden | `screens.yaml` | partial — structural fixtures added |
| P3 | `profile_edit_layout` missing fixture | tests | open |
| P4 | Prompt-only systemic rules ({len(SYSTEMIC_BUG_RULES)} total) | `llm/prompts` | see `ir-llm-coverage.md` |

## Proposed systemic improvements

1. `flex_policy/registry.py` — predicate registry with mutual-exclusion notes.
2. CI: `figma-flutter audit predicate-matrix` fails on new overlap without test.
3. Extend FID-26: `checkbox_mislabeled_input`, `flatten_dropped_absolute_slot`.
4. Reconcile pass unit tests for passes 4–6, 8–9, 11, 13.
"""


def _render_pipeline_contracts() -> str:
    return """# Pipeline layer contracts

Three independent reconcilers — do not mix diffs across layers.

```
Figma JSON → parse → reconcile_layout_tree (14) → normalize_clean_tree
  → render_layout_file (emit) → planned Dart reconcile → AST sidecar → analyze
```

| Layer | Entry | Contract |
| --- | --- | --- |
| IR tree | `normalize.py` | Types, placements, consent rows, grid order |
| Emit | `widgets/emit/` | Widget archetypes, flex wraps, early-return order |
| Planned Dart | `planned/reconcile/` | Must not undo intentional emit padding / flex |

## Dispatch early-return order (`dispatch.py`)

1. Logo wordmark stack
2. Consent checkbox row
3. Textarea field
4. Early stack special (hero, play-pause)
5. Payment selection indicator
6. `inline_cluster_control` (pill / badge / checkbox / icon)
7. Non-root stack specials (weekday, wheel, CTA footer)

## ROW early returns (`flex.py`)

1. Checkbox label row
2. Label/value summary
3. spaceBetween metric row (flatten)
4. Tight horizontal pill (painted)
5. Status pill badge
6. Overflow guard tight row (unpainted)

**Rule:** archetype predicates must be mutually exclusive with overflow guards on the same structural class; see `artifacts/predicate-overlap-matrix.md`.
"""


def _render_audit_readme() -> str:
    return """# Systemic pipeline audit

Automated artifacts for the Figma→Flutter compiler systemic review.

## Refresh

```bash
poetry run figma-flutter audit all
poetry run figma-flutter audit all --run-pytest   # include pytest summary in baseline
```

## Artifacts

| File | Phase |
| --- | --- |
| `baseline.md` | 0 — git SHA, pytest summary |
| `diff-triada-summary.md` | 0/4 — corpus normalize+emit |
| `artifacts/diff_triada.json` | 0 — machine-readable triada |
| `parse-classification.md` | 1 |
| `interaction-predicates.md` | 1 |
| `reconcile-passes.md` | 2 |
| `artifacts/predicate-overlap-matrix.md` | 3 |
| `geometry-emit-fidelity.md` | 4 |
| `ir-llm-coverage.md` | 5 |
| `gates-gap-analysis.md` | 6 |
| `test-conflicts.md` | 7 |
| `remediation-backlog.md` | 8 |
| `pipeline-contracts.md` | 8 |

## Source

Python package: `src/figma_flutter_agent/audit/`.
"""
