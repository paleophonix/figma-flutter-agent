"""Deterministic layout codegen (flex, stack, scroll, forms)."""

__all__ = [
    "body_needs_dart_ui",
    "body_needs_text_scaler",
    "render_layout_file",
    "render_node_body",
    "render_widget_file",
]


def __getattr__(name: str) -> object:
    """Load layout file assembly helpers only when callers request them."""
    if name == "render_widget_file":
        from figma_flutter_agent.generator.layout.widget_file import render_widget_file

        return render_widget_file
    if name in {
        "body_needs_dart_ui",
        "body_needs_text_scaler",
        "render_layout_file",
        "render_node_body",
    }:
        from figma_flutter_agent.generator.layout import file as layout_file

        return getattr(layout_file, name)
    raise AttributeError(name)
