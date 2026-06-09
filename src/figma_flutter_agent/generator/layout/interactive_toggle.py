"""Stateful toggle checkbox helpers for deterministic layout."""

from __future__ import annotations

from figma_flutter_agent.generator.custom_code_zones import (
    custom_code_zone_id,
    inline_custom_code_comment,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.variant.state import variant_is_checked
from figma_flutter_agent.schemas import CleanDesignTreeNode


def toggle_checkbox_stateful_helpers() -> str:
    """Return Dart helper widgets for compact checkbox controls."""
    return """
class _GeneratedToggleCheckbox extends StatefulWidget {
  const _GeneratedToggleCheckbox({
    required this.initialValue,
    required this.semanticsLabel,
    this.onChangedBody,
    super.key,
  });

  final bool initialValue;
  final String semanticsLabel;
  final VoidCallback? onChangedBody;

  @override
  State<_GeneratedToggleCheckbox> createState() => _GeneratedToggleCheckboxState();
}

class _GeneratedToggleCheckboxState extends State<_GeneratedToggleCheckbox> {
  late bool _value = widget.initialValue;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: widget.semanticsLabel,
      child: Checkbox(
        value: _value,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
        visualDensity: const VisualDensity(horizontal: -4, vertical: -4),
        onChanged: (next) {
          setState(() => _value = next ?? false);
          widget.onChangedBody?.call();
        },
      ),
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
    return (
        f"_GeneratedToggleCheckbox("
        f"initialValue: {initial}, "
        f"semanticsLabel: '{label}', "
        f"onChangedBody: () {{ {comment} }})"
    )
