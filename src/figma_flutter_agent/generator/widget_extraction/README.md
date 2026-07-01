# Widget extraction policy

## Purpose

Unifies reusable widget discovery from layer annotations, structural/component repetition, and gated semantic inference.

## Usage Example

```python
from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.widget_extraction import collect_widget_specs

config = WidgetExtractionConfig(policy="balanced")
specs = collect_widget_specs(clean_tree, cluster_summary, config=config, widget_suffix="Widget")
```

## LLM Context

When `policy` is `balanced` or `annotated`, layers named `@widget ProductCard` (case-insensitive, space or `:` separator) become `extracted_widget_ref` targets and `widgetExtractionHints` entries. The LLM must emit matching `extractedWidgets[].widgetIr` and `kind=extracted` refs.
