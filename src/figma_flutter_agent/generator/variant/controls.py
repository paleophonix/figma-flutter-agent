"""Render Material/Cupertino controls from variant metadata."""

from __future__ import annotations

from figma_flutter_agent.generator.variant.actions import (
    slider_on_changed_expr,
    slider_value_expr,
    toggle_on_changed_expr,
    toggle_value_expr,
)
from figma_flutter_agent.generator.variant.state import (
    variant_button_kind,
    variant_input_has_error,
    variant_is_checked,
    variant_size_label,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

VARIANT_BUTTON_PADDING: dict[str, tuple[str, str]] = {
    "small": ("AppSpacing.sm", "AppSpacing.xs"),
    "medium": ("AppSpacing.md", "AppSpacing.sm"),
    "large": ("AppSpacing.lg", "AppSpacing.md"),
}
DESTRUCTIVE_COLOR = "const Color(0xFFB3261E)"


def input_decoration_expr(node: CleanDesignTreeNode, *, label: str) -> str:
    """Build InputDecoration from label and error variant state."""
    if not variant_input_has_error(node):
        return f"InputDecoration(labelText: '{label}')"
    return (
        f"InputDecoration("
        f"labelText: '{label}', "
        f"errorText: '{label}', "
        f"errorBorder: const OutlineInputBorder("
        f"borderSide: BorderSide(color: {DESTRUCTIVE_COLOR})"
        f")"
        f")"
    )


def render_material_button_widget(
    *,
    label: str,
    on_pressed: str,
    background_color: str,
    node: CleanDesignTreeNode,
) -> str:
    """Render a Material button widget from variant Type and Size."""
    kind = variant_button_kind(node)
    padding = button_padding_fragment(node)
    padding_suffix = f", {padding}" if padding else ""

    if kind == "outlined":
        return (
            f"OutlinedButton("
            f"onPressed: {on_pressed}, "
            f"style: OutlinedButton.styleFrom(foregroundColor: {background_color}{padding_suffix}), "
            f"child: Text('{label}')"
            f")"
        )
    if kind == "text":
        return (
            f"TextButton("
            f"onPressed: {on_pressed}, "
            f"style: TextButton.styleFrom(foregroundColor: {background_color}{padding_suffix}), "
            f"child: Text('{label}')"
            f")"
        )
    if kind == "destructive":
        return (
            f"ElevatedButton("
            f"onPressed: {on_pressed}, "
            f"style: ElevatedButton.styleFrom(backgroundColor: {DESTRUCTIVE_COLOR}{padding_suffix}), "
            f"child: Text('{label}')"
            f")"
        )
    return (
        f"ElevatedButton("
        f"onPressed: {on_pressed}, "
        f"style: ElevatedButton.styleFrom(backgroundColor: {background_color}{padding_suffix}), "
        f"child: Text('{label}')"
        f")"
    )


def render_cupertino_button_widget(
    *,
    label: str,
    on_pressed: str,
    node: CleanDesignTreeNode,
) -> str:
    """Render a Cupertino button from variant Type."""
    kind = variant_button_kind(node)
    if kind == "destructive":
        return (
            f"CupertinoButton("
            f"color: CupertinoColors.destructiveRed, "
            f"onPressed: {on_pressed}, "
            f"child: Text('{label}')"
            f")"
        )
    if kind in {"outlined", "text"}:
        return f"CupertinoButton(onPressed: {on_pressed}, child: Text('{label}'))"
    return f"CupertinoButton.filled(onPressed: {on_pressed}, child: Text('{label}'))"


def render_radio_group_widget(
    *, node: CleanDesignTreeNode, theme_variant: str = "material_3"
) -> str:
    """Render a Column of radio controls for a radio group."""
    selected_index = selected_child_index(node)
    group_value = f"'option_{selected_index}'"
    on_changed = toggle_on_changed_expr(node.children[0] if node.children else node)
    tiles: list[str] = []
    for index, child in enumerate(node.children):
        label = escape_label(child)
        value = f"'option_{index}'"
        if theme_variant == "cupertino":
            tiles.append(
                f"Row(children: [CupertinoRadio<String>(value: {value}), Text('{label}')])"
            )
        else:
            tiles.append(f"RadioListTile<String>(title: Text('{label}'), value: {value})")
    body = ", ".join(tiles) if tiles else "const SizedBox.shrink()"
    return (
        f"RadioGroup<String>(groupValue: {group_value}, onChanged: {on_changed}, "
        f"child: Column(children: [{body}]))"
    )


def render_radio_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str = "material_3",
    compact_glyph: bool = False,
) -> str:
    """Render a single radio control."""
    on_changed = toggle_on_changed_expr(node)
    group_value = "'selected'" if variant_is_checked(node) else "'unselected'"
    if theme_variant == "cupertino":
        inner = f"Row(children: [CupertinoRadio<String>(value: 'selected'), Text('{label}')])"
    elif compact_glyph:
        inner = "Radio<String>(value: 'selected')"
    else:
        inner = f"RadioListTile<String>(title: Text('{label}'), value: 'selected')"
    return f"RadioGroup<String>(groupValue: {group_value}, onChanged: {on_changed}, child: {inner})"


def render_dropdown_widget(*, node: CleanDesignTreeNode, theme_variant: str = "material_3") -> str:
    """Render a dropdown or Cupertino picker from child nodes."""
    labels = (
        [escape_label(child) for child in node.children] if node.children else [escape_label(node)]
    )
    selected_index = selected_child_index(node) if node.children else 0
    selected_index = min(selected_index, len(labels) - 1)
    if theme_variant == "cupertino":
        children = ", ".join(f"Text('{label}')" for label in labels) or "Text('Item')"
        return (
            f"SizedBox(height: 120.0, child: CupertinoPicker("
            f"scrollController: FixedExtentScrollController(initialItem: {selected_index}), "
            f"itemExtent: 32.0, onSelectedItemChanged: (_) {{}}, children: [{children}]))"
        )
    value_expr = f"'item_{selected_index}'"
    items = ", ".join(
        f"DropdownMenuItem<String>(value: 'item_{index}', child: Text('{label}'))"
        for index, label in enumerate(labels)
    )
    on_changed = toggle_on_changed_expr(node)
    dropdown = (
        f"DropdownButton<String>(value: {value_expr}, items: [{items}], onChanged: {on_changed})"
    )
    return f"DropdownButtonHideUnderline(child: {dropdown})"


def render_slider_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str,
) -> str:
    """Render Slider or CupertinoSlider with optional label."""
    value = slider_value_expr(node)
    on_changed = slider_on_changed_expr(node)
    control = (
        f"CupertinoSlider(value: {value}, onChanged: {on_changed})"
        if theme_variant == "cupertino"
        else f"Slider(value: {value}, onChanged: {on_changed})"
    )
    if not label:
        return control
    return f"Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text('{label}'), {control}])"


def render_dialog_widget(
    *,
    title: str,
    child_widgets: list[str],
    theme_variant: str = "material_3",
) -> str:
    """Render a dialog with scrollable content and a dismiss action."""
    content = ", ".join(child_widgets) if child_widgets else "const SizedBox.shrink()"
    if theme_variant == "cupertino":
        return (
            f"CupertinoAlertDialog(title: Text('{title}'), "
            f"content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [{content}])), "
            f"actions: [CupertinoDialogAction(onPressed: () {{ Navigator.of(context).pop(); }}, child: const Text('OK'))])"
        )
    return (
        f"AlertDialog(title: Text('{title}'), "
        f"content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [{content}])), "
        f"actions: [TextButton(onPressed: () {{ Navigator.of(context).pop(); }}, child: const Text('OK'))])"
    )


def render_checkbox_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str,
) -> str:
    """Render Checkbox or CupertinoCheckbox with an optional label."""
    value = toggle_value_expr(node)
    on_changed = toggle_on_changed_expr(node)
    control = (
        f"CupertinoCheckbox(value: {value}, onChanged: {on_changed})"
        if theme_variant == "cupertino"
        else f"Checkbox(value: {value}, onChanged: {on_changed})"
    )
    if not label or layout_fact_compact_checkbox_only(node):
        return control
    return f"Row(mainAxisSize: MainAxisSize.min, children: [{control}, Text('{label}')])"


def render_switch_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str,
) -> str:
    """Render Switch or CupertinoSwitch with an optional label."""
    value = toggle_value_expr(node)
    on_changed = toggle_on_changed_expr(node)
    control = (
        f"CupertinoSwitch(value: {value}, onChanged: {on_changed})"
        if theme_variant == "cupertino"
        else f"Switch(value: {value}, onChanged: {on_changed})"
    )
    if not label:
        return control
    return f"Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text('{label}'), {control}])"


def button_padding_fragment(node: CleanDesignTreeNode) -> str:
    size = variant_size_label(node)
    if size is None or size not in VARIANT_BUTTON_PADDING:
        return ""
    horizontal, vertical = VARIANT_BUTTON_PADDING[size]
    return f"padding: const EdgeInsets.symmetric(horizontal: {horizontal}, vertical: {vertical})"


def selected_child_index(node: CleanDesignTreeNode) -> int:
    for index, child in enumerate(node.children):
        if variant_is_checked(child):
            return index
    return 0


def escape_label(node: CleanDesignTreeNode) -> str:
    """Escape a display label for generated Dart string literals."""
    if node.text and node.text.strip():
        raw = node.text.strip()
    elif node.type == NodeType.TEXT and node.name:
        raw = node.name
    else:
        raw = node.name
    return raw.replace("\\", "\\\\").replace("'", "\\'")


def layout_fact_compact_checkbox_only(node: CleanDesignTreeNode) -> bool:
    from figma_flutter_agent.parser.interaction import layout_fact_checkbox_control

    if layout_fact_checkbox_control(node):
        return True
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if width > 36.0 or height > 36.0:
        return False
    lowered = node.name.strip().lower()
    if lowered.startswith("rectangle") or lowered in {"checkbox", "check box"}:
        return True
    return node.type == NodeType.CONTAINER and width <= 32.0 and height <= 32.0
