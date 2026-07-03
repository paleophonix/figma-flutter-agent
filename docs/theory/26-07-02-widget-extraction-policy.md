# Widget extraction policy

## Layer annotation grammar

- Prefix: `@widget` (case-insensitive)
- Optional name separator: space or `:`
- Examples: `@widget ProductCard`, `@Widget:BottomNav`, `@widget` on layer `Bottom Nav`

## Policies

| Policy | Sources |
| --- | --- |
| `off` | None |
| `dedup` | Structural/component repetition (`min_count`) |
| `annotated` | `@widget` markers and single-use Figma components |
| `balanced` | Annotated + dedup (default) |
| `auto_reusable` / `aggressive` | Balanced + gated static inference scorer |
| `balanced` + `ai_reusable.enabled` | Balanced + optional LLM candidate provider |

## Inference channels

| Channel | Role |
| --- | --- |
| Static scorer | Shape/topology repetition scoring (`auto_reusable_min_score`) |
| `ai_reusable` | LLM proposes candidates; deterministic gates decide extraction |
| `enrich` | LLM suggests human-readable class names and param labels for clusters |

LLM is a **candidate provider**, not an emitter. Final authority: `WidgetExtractionPolicy` + validators.

## Configuration

```yaml
generation:
  widget_extraction:
    policy: balanced
    min_count: 2
    auto_reusable_min_score: 0.85
    annotation_prefixes: ["@widget"]
    extract_figma_components_single_use: true
    fail_on_unextracted_annotations: true
    parameterize_text: false
    ai_reusable:
      enabled: false
      mode: suggest
      min_confidence: 0.85
      max_candidates: 12
      require_static_gate: true
      require_evidence: true
    enrich:
      enabled: false
      cache_by_subtree_hash: true
```

- `ai_reusable.mode: suggest` — gated candidates become `widgetExtractionHints` only.
- `ai_reusable.mode: enforce` — gated candidates may become cluster widget files.
- `policy: auto_reusable` — enables static inference extraction without LLM.
- When `parameterize_text: true`, shape-only clusters may emit constructor parameters for differing text slots across structurally identical subtrees.

Debug artifacts: `.debug/screen/<project>/<feature>/reusable_candidates.json`, `widget_enrich.json`.
