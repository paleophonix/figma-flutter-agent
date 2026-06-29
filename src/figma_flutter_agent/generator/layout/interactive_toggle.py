"""Stateful toggle checkbox helpers for deterministic layout."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.variant.state import variant_is_checked
from figma_flutter_agent.parser.interaction.forms import _stack_hosts_stroked_outline_checkbox_glyph
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


def render_stateful_toggle_checkbox(node: CleanDesignTreeNode) -> str:
    """Render a compact checkbox with local selection state."""
    initial = "true" if variant_is_checked(node) else "false"
    label = escape_dart_string(node.accessibility_label or "Checkbox")
    zone = custom_code_zone_id(node.id, "toggle-action")
    comment = inline_custom_code_comment(zone)
    scale = _stroked_checkbox_visual_scale(node)
    scale_field = ""
    if scale is not None:
        scale_field = f", visualScale: {format_geometry_literal(scale)}"
    return (
        f"_GeneratedToggleCheckbox("
        f"initialValue: {initial}, "
        f"semanticsLabel: '{label}'"
        f"{scale_field}, "
        f"onChangedBody: () {{ {comment} }})"
    )
