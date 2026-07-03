# Test conflict pairs

Explicit pairs to review when adding ROW archetypes or overflow guards.

| Test A | Test B | Contract |
| --- | --- | --- |
| `test_space_between_row_binds_fixed_stack_width_and_height` | `test_space_between_total_row_flattens_label_and_price` | absolute Stack slots vs metric-row flatten |
| `test_tight_chip_row_text_clips_with_expanded` | `test_column_status_pill_centers_discount_label` | Expanded+ellipsis vs FittedBox pill |
| overflow guard rows | `row_is_tight_horizontal_pill_label` | unpainted tight row vs painted pill |

## Fixture gaps (closed in this audit)

- `consent_checkbox_row.json`, `flex_summary_row.json`, `prefilled_input_field.json` — synthetic minimal trees.
- `bounded_order_card.json` — added to `screens.yaml`.
- `elastic_form_a11y.json`, `deep_nesting_8x.json`, `variant_topology.json` — in corpus; raw Figma skipped by diff-triada.

## `profile_edit_layout.json`

Tests `test_profile_edit_layout.py` and `test_view_renders.py` optionally load ataev dump; no committed fixture. **P3:** add generic profile-edit fixture or gate tests with `pytest.mark.skipif` when dump absent.
