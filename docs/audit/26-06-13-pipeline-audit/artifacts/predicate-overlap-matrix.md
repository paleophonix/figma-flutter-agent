# Predicate overlap matrix

Synthetic pattern fixtures × flex/interaction predicates. Multiple matches on one row signal archetype overlap risk.

| Predicate | spaceBetween_absolute_stacks | spaceBetween_plain_stacks | painted_pill_23px | unpainted_tight_row_64x17 | consent_checkbox_row | prefilled_flex_input |
| --- | --- | --- | --- | --- | --- | --- |
| `row_is_label_value_summary_row` | no | yes | no | no | no | no |
| `row_is_space_between_text_metric_row` | no | yes | no | no | no | no |
| `row_is_tight_horizontal_pill_label` | no | no | yes | no | no | no |
| `row_is_tight_overflow_guard_label_row` | no | no | no | yes | no | no |
| `row_is_status_pill_badge` | no | no | yes | no | no | no |
| `row_is_numeric_counter_badge` | no | no | no | no | no | no |
| `row_hosts_checkbox_label_pair` | no | no | no | no | yes | no |
| `hosts_compact_checkbox_control` | no | no | no | no | no | no |
| `looks_like_checkbox_control` | no | no | no | no | no | no |
| `looks_like_textarea_field` | no | no | no | no | no | no |

## Winning emit per pattern

- **spaceBetween_absolute_stacks**: `generic Row + SizedBox+Stack (overflow guard)`
- **spaceBetween_plain_stacks**: `try_render_space_between_text_metric_row flatten`
  - predicates: `row_is_label_value_summary_row`, `row_is_space_between_text_metric_row`
- **painted_pill_23px**: `row_is_tight_horizontal_pill_label + FittedBox`
  - predicates: `row_is_tight_horizontal_pill_label`, `row_is_status_pill_badge`
- **unpainted_tight_row_64x17**: `row_is_tight_overflow_guard_label_row + Expanded ellipsis`
  - predicates: `row_is_tight_overflow_guard_label_row`
- **consent_checkbox_row**: `_try_render_checkbox_label_row`
  - predicates: `row_hosts_checkbox_label_pair`
- **prefilled_flex_input**: `_render_stack_input / flex INPUT`
