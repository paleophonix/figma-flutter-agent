# Pipeline layer contracts

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
