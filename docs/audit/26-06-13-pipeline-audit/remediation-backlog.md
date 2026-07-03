# Remediation backlog (P0–P4)

| Sev | Finding | Layer | Status |
| --- | --- | --- | --- |
| P0 | Checkbox mislabeled INPUT (13px square) | `forms.looks_like_checkbox_control` | **Fixed** — min size 12, label host unwrap |
| P0 | TextField vertical misalign | `input/decoration.py` | **Fixed** — line-box padding, omit line height |
| P1 | spaceBetween flatten vs absolute stack guard | `flex_policy/row.py` | **Fixed** — block flatten when absolute/fixed stack |
| P1 | Unpainted tight row → FittedBox pill | `row_is_tight_horizontal_pill_label` | **Fixed** — require `background_color` |
| P2 | Soft `t2_artboard_extent_drift` on large corpus | geometry planner | monitor via diff-triada |
| P3 | Orphan fixtures without golden | `screens.yaml` | partial — structural fixtures added |
| P3 | `profile_edit_layout` missing fixture | tests | open |
| P4 | Prompt-only systemic rules (52 total) | `llm/prompts` | see `ir-llm-coverage.md` |

## Proposed systemic improvements

1. `flex_policy/registry.py` — predicate registry with mutual-exclusion notes.
2. CI: `figma-flutter audit predicate-matrix` fails on new overlap without test.
3. Extend FID-26: `checkbox_mislabeled_input`, `flatten_dropped_absolute_slot`.
4. Reconcile pass unit tests for passes 4–6, 8–9, 11, 13.
