"""Stateful toggle checkbox helpers for deterministic layout."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.layout.style import dart_color_expr
from figma_flutter_agent.generator.variant.state import variant_is_checked
from figma_flutter_agent.parser.interaction.forms import (
    _stack_hosts_stroked_outline_checkbox_glyph,
    checkbox_option_border_container,
    checkbox_option_stack_is_checked,
)
from figma_flutter_agent.parser.numeric_rounding import format_geometry_literal
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_MATERIAL_CHECKBOX_DEFAULT_EXTENT = 18.0


def _stroked_checkbox_visual_scale(node: CleanDesignTreeNode) -> float | None:
    """Scale native checkbox chrome to match a stroked vector glyph inside the slot."""
    if not _stack_hosts_stroked_outline_checkbox_glyph(node):
        return None
    vectors = [child for child in node.children if child.type == NodeType.VECTOR]
    if len(vectors) != 1:
        return None
    vector = vectors[0]
    inner_extent = max(
        float(vector.sizing.width or 0.0),
        float(vector.sizing.height or 0.0),
    )
    if inner_extent <= 0:
        return None
    scale = inner_extent / _MATERIAL_CHECKBOX_DEFAULT_EXTENT
    if scale >= 0.98:
        return None
    return scale


def _checkbox_theme_wrapper(
    widget: str,
    border: CleanDesignTreeNode,
    *,
    checked: bool = False,
) -> str:
    """Apply Figma stroke color and corner radius to Material checkbox chrome."""
    from figma_flutter_agent.generator.layout.style.colors import _border_color_expr

    radius = border.style.border_radius if border.style.border_radius is not None else 3.0
    width = border.style.border_width if border.style.border_width is not None else 1.0
    radius_lit = format_geometry_literal(float(radius))
    width_lit = format_geometry_literal(float(width))
    color_expr = _border_color_expr(border.style) or dart_color_expr(
        border.style,
        css_key="border-color",
        fallback="AppColors.primary",
    )
    unchecked_fill = dart_color_expr(
        border.style,
        css_key="background-color",
        fallback="const Color(0xFFFFFFFF)",
    )
    if checked:
        fill_fields = (
            f"fillColor: MaterialStateProperty.resolveWith((states) => "
            f"states.contains(MaterialState.selected) ? {color_expr} : {unchecked_fill}), "
            "checkColor: MaterialStateProperty.all(const Color(0xFFFFFFFF)), "
        )
    elif border.style.background_color:
        fill_fields = f"fillColor: MaterialStateProperty.all({unchecked_fill}), "
    else:
        fill_fields = ""
    return (
        "Theme("
        "data: Theme.of(context).copyWith("
        "checkboxTheme: CheckboxThemeData("
        f"side: BorderSide(color: {color_expr}, width: {width_lit}), "
        f"{fill_fields}"
        f"shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular({radius_lit}))"
        ")), "
        f"child: {widget})"
    )


def toggle_checkbox_stateful_helpers() -> str:
    """Return Dart helper widgets for compact checkbox controls."""
    return """
class _GeneratedToggleCheckbox extends StatefulWidget {
  const _GeneratedToggleCheckbox({
    required this.initialValue,
    required this.semanticsLabel,
    this.onChangedBody,
    this.visualScale,
    super.key,
  });

  final bool initialValue;
  final String semanticsLabel;
  final VoidCallback? onChangedBody;
  final double? visualScale;

  @override
  State<_GeneratedToggleCheckbox> createState() => _GeneratedToggleCheckboxState();
}

class _GeneratedToggleCheckboxState extends State<_GeneratedToggleCheckbox> {
  late bool _value = widget.initialValue;

  @override
  Widget build(BuildContext context) {
    Widget checkbox = Checkbox(
      value: _value,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
      onChanged: (next) {
        setState(() => _value = next ?? false);
        widget.onChangedBody?.call();
      },
    );
    final scale = widget.visualScale;
    if (scale != null && scale > 0 && scale < 0.98) {
      checkbox = Transform.scale(
        scale: scale,
        alignment: Alignment.center,
        child: checkbox,
      );
    }
    return Semantics(
      label: widget.semanticsLabel,
      child: checkbox,
    );
  }
}
"""


def render_stateful_toggle_checkbox(
    node: CleanDesignTreeNode,
    *,
    selection_stack: CleanDesignTreeNode | None = None,
) -> str:
    """Render a compact checkbox with local selection state."""
    stack_ref = selection_stack or node
    checked = variant_is_checked(node) or checkbox_option_stack_is_checked(stack_ref)
    initial = "true" if checked else "false"
    label = escape_dart_string(node.accessibility_label or node.name or "Checkbox")
    if selection_stack is not None:
        from figma_flutter_agent.parser.interaction.forms import checkbox_label_text_host

        for child in selection_stack.children:
            host = checkbox_label_text_host(child)
            if host is not None and (host.text or host.name):
                label = escape_dart_string(host.text or host.name)
                break
    zone = custom_code_zone_id(node.id, "toggle-action")
    comment = inline_custom_code_comment(zone)
    scale = _stroked_checkbox_visual_scale(node)
    scale_field = ""
    if scale is not None:
        scale_field = f", visualScale: {format_geometry_literal(scale)}"
    widget = (
        f"_GeneratedToggleCheckbox("
        f"initialValue: {initial}, "
        f"semanticsLabel: '{label}'"
        f"{scale_field}, "
        f"onChangedBody: () {{ {comment} }})"
    )
    border = checkbox_option_border_container(stack_ref)
    if border is not None and (border.style.border_color or border.style.background_color):
        widget = _checkbox_theme_wrapper(widget, border, checked=checked)
    return widget
