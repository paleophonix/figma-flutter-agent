# parser

## Purpose

Convert raw Figma node JSON into a `CleanDesignTreeNode` and `DesignTokens`, including **synthesized** CSS-like properties (from REST fills/effects, not the Dev Mode API), classic frame `constraints`, effects, gradients, and component variant metadata. Figma `SECTION` → layout as `FRAME`; `GROUP` → `STACK`. Semantic types for `INSTANCE` nodes prefer **Components API** metadata (set name, published name/description, variant axes) over layer names; overlay frames use Figma `overlayPositionType` / `overlayBackground`. Repeated component instances share `component_*` cluster ids for widget extraction.

## Example

```python
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.parser.tokens import build_design_tokens

tokens = build_design_tokens(root, variables_payload)
clean_tree, absolute_ratio, dedup, cluster_summary = build_clean_tree(
    root,
    published_styles=styles_payload,
    components=components_payload,
)
```

## LLM Context

When `accessibility.auto_fix` is enabled in config, run `apply_accessibility_fixes(clean_tree)` before codegen.

Pass `clean_tree.model_dump(mode="json", by_alias=True)` and `tokens.model_dump(mode="json", by_alias=True)` to the LLM. Each node may include `style.cssProperties`, `style.effects`, `style.gradient`, `scrollAxis` (from Figma `overflowDirection`), `gridColumnCount` / gaps for `layoutMode: GRID`, and `variant` for component instances. When nodes reference published styles without inline paints, pass `style_paint_index` from fetched style definition nodes. Use `collect_ux_suggestions()` for non-fatal spacing, touch-target, and layout-depth hints.
