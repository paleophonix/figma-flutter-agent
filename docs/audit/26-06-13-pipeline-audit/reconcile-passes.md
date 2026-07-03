# Reconcile pass coverage

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
