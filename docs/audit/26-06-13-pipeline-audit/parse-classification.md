# Parse and node classification audit

## Infer chain (priority order)

1. `parser/tree.py` — `_convert_node`: Figma type → provisional `NodeType`.
2. `parser/layout/grid.py` — `infer_container_type`: auto-layout axis → ROW/COLUMN/GRID.
3. `parser/components.py` — `resolve_semantic_node_type`: API component set → properties → overlay → **name** fallback.
4. `parser/tree_node.py` — `infer_leaf_type`: name tokens (`input`→INPUT, `button`→BUTTON).

## Audit findings

| Risk | Layer | Mitigation |
| --- | --- | --- |
| Name heuristic beats geometry | `tree_node.infer_leaf_type` | Prefer bbox + child structure in `interaction/forms.py` |
| Small square → INPUT not CHECKBOX | `forms.looks_like_checkbox_control` | `_MIN_CHECKBOX_SIZE = 12`; `hosts_compact_checkbox_control` in emit |
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
