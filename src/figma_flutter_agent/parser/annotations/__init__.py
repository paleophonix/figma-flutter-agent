"""Figma layer annotation parsers."""

from figma_flutter_agent.parser.annotations.widget_marker import (
    WidgetAnnotation,
    apply_widget_layer_annotations,
    parse_widget_annotation,
    resolve_widget_class_name,
)

__all__ = [
    "WidgetAnnotation",
    "apply_widget_layer_annotations",
    "parse_widget_annotation",
    "resolve_widget_class_name",
]
