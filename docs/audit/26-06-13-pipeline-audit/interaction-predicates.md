# Interaction predicates inventory

Registry of `looks_like_*` / `hosts_*` predicates and emit consumers.

| Predicate | Module | Thresholds (px) | Emit consumer | Reconcile consumer |
| --- | --- | --- | --- | --- |
| `looks_like_checkbox_control` | `forms.py` | 12–28 square, border radius ≤10 | `dispatch`, `flex._try_render_checkbox_label_row` | `reconcile_consent_checkbox_rows_in_tree` |
| `hosts_compact_checkbox_control` | `forms.py` | delegates to checkbox | `inline_cluster_control` gate | — |
| `checkbox_label_text_host` | `forms.py` | STACK wrapping single TEXT | `row_hosts_checkbox_label_pair` | — |
| `looks_like_textarea_field` | `forms.py` | tall multiline INPUT | `dispatch` early return | — |
| `looks_like_password_field_stack` | `forms.py` | eye icon or dot mask | input decoration | — |
| `looks_like_back_nav_stack` | `buttons.py` | chevron + compact stack | `dispatch` stack special | — |
| `looks_like_play_pause_control_stack` | `buttons.py` | media control geometry | `hero` / playback emit | — |
| `looks_like_compact_icon_action_stack` | `icons.py` | ≤48 hit, vector child | icon button emit | — |
| `hosts_payment_selection_indicator` | `selection.py` | radio/check overlay | payment row emit | `reconcile_payment_selection_state_in_tree` |
| `row_is_*` (flex) | `flex_policy/row.py` | per-predicate | `flex.py` ROW early returns | — |

## Gap

`forms.py` predicates are referenced in 10+ emit sites but only **consent checkbox reconcile** mutates the IR tree. Other mislabels must be fixed at parse or emit predicate level, not per-screen patches.
