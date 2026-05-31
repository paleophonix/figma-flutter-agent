"""Map Figma component variant properties to deterministic Flutter widget props."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

_DISABLED_VALUES = frozenset({"disabled", "disable", "off", "false"})
_LOADING_VALUES = frozenset({"loading", "busy", "pending"})
_ERROR_VALUES = frozenset({"error", "invalid", "failed"})
_PASSWORD_TYPES = frozenset({"password", "secure", "securetext"})
_CHECKED_VALUES = frozenset({"true", "yes", "on", "1", "checked", "selected"})

_BUTTON_KIND_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("destructive", "danger", "error"), "destructive"),
    (("secondary", "outline", "outlined"), "outlined"),
    (("tertiary", "ghost", "text", "link"), "text"),
    (("primary",), "elevated"),
)

_VARIANT_SIZE_TO_FONT: dict[str, float] = {
    "small": 12.0,
    "medium": 14.0,
    "large": 18.0,
}

_VARIANT_BUTTON_PADDING: dict[str, tuple[str, str]] = {
    "small": ("AppSpacing.sm", "AppSpacing.xs"),
    "medium": ("AppSpacing.md", "AppSpacing.sm"),
    "large": ("AppSpacing.lg", "AppSpacing.md"),
}

_DESTRUCTIVE_COLOR = "const Color(0xFFB3261E)"


def get_variant_property(node: CleanDesignTreeNode, *names: str) -> str | None:
    """Return the first matching variant property value (case-insensitive keys)."""
    if node.variant is None:
        return None
    normalized_names = {name.strip().lower() for name in names}
    for key, value in node.variant.variant_properties.items():
        if key.strip().lower() in normalized_names:
            trimmed = value.strip()
            if trimmed:
                return trimmed
    return None


def variant_size_label(node: CleanDesignTreeNode) -> str | None:
    """Return normalized Size variant property when present."""
    raw = get_variant_property(node, "size")
    return raw.lower() if raw else None


def _state_value(node: CleanDesignTreeNode) -> str | None:
    if node.variant is None:
        return None
    raw = node.variant.state or get_variant_property(node, "state")
    return raw.strip().lower() if raw else None


def variant_is_disabled(node: CleanDesignTreeNode) -> bool:
    """Return True when component variant metadata marks the control disabled."""
    state = _state_value(node)
    if state in _DISABLED_VALUES:
        return True
    disabled_flag = get_variant_property(node, "disabled")
    if disabled_flag is not None and disabled_flag.strip().lower() in {"true", "yes", "1"}:
        return True
    enabled_flag = get_variant_property(node, "enabled")
    return enabled_flag is not None and enabled_flag.strip().lower() in {"false", "no", "0"}


def variant_is_loading(node: CleanDesignTreeNode) -> bool:
    """Return True when variant state blocks interaction (loading/busy)."""
    state = _state_value(node)
    return state in _LOADING_VALUES


def variant_blocks_interaction(node: CleanDesignTreeNode) -> bool:
    """Return True when the control should not accept user input."""
    return variant_is_disabled(node) or variant_is_loading(node)


def variant_button_kind(node: CleanDesignTreeNode) -> str:
    """Map variant Type/Style to elevated, outlined, text, or destructive."""
    raw = get_variant_property(node, "type", "variant", "style", "kind", "hierarchy")
    if raw is None:
        return "elevated"
    normalized = raw.lower().replace("_", " ").replace("-", " ")
    for tokens, kind in _BUTTON_KIND_ALIASES:
        if any(token in normalized for token in tokens):
            return kind
    return "elevated"


def variant_is_checked(node: CleanDesignTreeNode) -> bool:
    """Return True when variant State/Checked marks the toggle as on."""
    checked = get_variant_property(node, "checked", "selected", "on")
    if checked is not None:
        return checked.strip().lower() in _CHECKED_VALUES
    state = _state_value(node)
    return state in _CHECKED_VALUES


def toggle_value_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart bool expression for Checkbox/Switch value."""
    return "true" if variant_is_checked(node) else "false"


def slider_value_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart double literal for Slider value from variant Value (0-1 or 0-100)."""
    raw = get_variant_property(node, "value", "progress", "position")
    if raw is None:
        return "0.5"
    try:
        numeric = float(raw.replace("%", "").strip())
    except ValueError:
        return "0.5"
    if numeric > 1.0:
        numeric /= 100.0
    clamped = min(1.0, max(0.0, numeric))
    return str(clamped)


def slider_on_changed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart onChanged expression for Slider/CupertinoSlider."""
    if variant_blocks_interaction(node):
        return "null"
    return "(value) { /* <custom-code:slider-action> */ }"


def toggle_on_changed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart onChanged expression for Checkbox/Switch."""
    if variant_blocks_interaction(node):
        return "null"
    return "(value) { /* <custom-code:toggle-action> */ }"


def variant_input_has_error(node: CleanDesignTreeNode) -> bool:
    """Return True when variant State indicates a validation error."""
    state = _state_value(node)
    return state in _ERROR_VALUES


def input_obscure_text_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart bool expression for TextField.obscureText from variant Type."""
    raw = get_variant_property(node, "type", "input type", "inputtype")
    if raw is None:
        return "false"
    return "true" if raw.lower().replace(" ", "") in _PASSWORD_TYPES else "false"


def button_on_pressed_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart expression for button onPressed."""
    if variant_blocks_interaction(node):
        return "null"
    return "() { /* <custom-code:button-action> */ }"


def input_enabled_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart expression for TextField/CupertinoTextField enabled flag."""
    return "false" if variant_blocks_interaction(node) else "true"


def _button_padding_fragment(node: CleanDesignTreeNode) -> str:
    size = variant_size_label(node)
    if size is None or size not in _VARIANT_BUTTON_PADDING:
        return ""
    horizontal, vertical = _VARIANT_BUTTON_PADDING[size]
    return f"padding: const EdgeInsets.symmetric(horizontal: {horizontal}, vertical: {vertical})"


def input_decoration_expr(node: CleanDesignTreeNode, *, label: str) -> str:
    """Build InputDecoration from label and error variant state."""
    if not variant_input_has_error(node):
        return f"InputDecoration(labelText: '{label}')"
    return (
        f"InputDecoration("
        f"labelText: '{label}', "
        f"errorText: '{label}', "
        f"errorBorder: const OutlineInputBorder("
        f"borderSide: BorderSide(color: {_DESTRUCTIVE_COLOR})"
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
    padding = _button_padding_fragment(node)
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
        color = _DESTRUCTIVE_COLOR
        return (
            f"ElevatedButton("
            f"onPressed: {on_pressed}, "
            f"style: ElevatedButton.styleFrom(backgroundColor: {color}{padding_suffix}), "
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
    """Render a Cupertino button from variant Type (filled vs plain vs destructive)."""
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


def _selected_child_index(node: CleanDesignTreeNode) -> int:
    for index, child in enumerate(node.children):
        if variant_is_checked(child):
            return index
    return 0


def render_radio_group_widget(*, node: CleanDesignTreeNode, theme_variant: str = "material_3") -> str:
    """Render a Column of radio controls for a radio group."""
    selected_index = _selected_child_index(node)
    group_value = f"'option_{selected_index}'"
    tiles: list[str] = []
    for index, child in enumerate(node.children):
        label = _escape_label(child)
        value = f"'option_{index}'"
        on_changed = toggle_on_changed_expr(child)
        if theme_variant == "cupertino":
            tiles.append(
                f"Row("
                f"children: ["
                f"CupertinoRadio<String>(value: {value}, groupValue: {group_value}, onChanged: {on_changed}), "
                f"Text('{label}')"
                f"]"
                f")"
            )
        else:
            tiles.append(
                f"RadioListTile<String>("
                f"title: Text('{label}'), "
                f"value: {value}, "
                f"groupValue: {group_value}, "
                f"onChanged: {on_changed}"
                f")"
            )
    body = ", ".join(tiles) if tiles else "const SizedBox.shrink()"
    return f"Column(children: [{body}])"


def render_radio_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str = "material_3",
) -> str:
    """Render a single radio control."""
    on_changed = toggle_on_changed_expr(node)
    group_value = "'selected'" if variant_is_checked(node) else "'unselected'"
    if theme_variant == "cupertino":
        return (
            f"Row("
            f"children: ["
            f"CupertinoRadio<String>(value: 'selected', groupValue: {group_value}, onChanged: {on_changed}), "
            f"Text('{label}')"
            f"]"
            f")"
        )
    return (
        f"RadioListTile<String>("
        f"title: Text('{label}'), "
        f"value: 'selected', "
        f"groupValue: {group_value}, "
        f"onChanged: {on_changed}"
        f")"
    )


def render_dropdown_widget(*, node: CleanDesignTreeNode, theme_variant: str = "material_3") -> str:
    """Render a dropdown or Cupertino picker from child nodes."""
    if node.children:
        labels = [_escape_label(child) for child in node.children]
    else:
        labels = [_escape_label(node)]
    selected_index = _selected_child_index(node) if node.children else 0
    selected_index = min(selected_index, len(labels) - 1)
    if theme_variant == "cupertino":
        children = ", ".join(f"Text('{label}')" for label in labels) or "Text('Item')"
        return (
            f"SizedBox("
            f"height: 120.0, "
            f"child: CupertinoPicker("
            f"scrollController: FixedExtentScrollController(initialItem: {selected_index}), "
            f"itemExtent: 32.0, "
            f"onSelectedItemChanged: (_) {{}}, "
            f"children: [{children}]"
            f")"
            f")"
        )
    value_expr = f"'item_{selected_index}'"
    items = ", ".join(
        f"DropdownMenuItem<String>(value: 'item_{index}', child: Text('{label}'))"
        for index, label in enumerate(labels)
    )
    on_changed = toggle_on_changed_expr(node)
    return f"DropdownButton<String>(value: {value_expr}, items: [{items}], onChanged: {on_changed})"


def _escape_label(node: CleanDesignTreeNode) -> str:
    """Escape a display label for generated Dart string literals."""
    if node.text and node.text.strip():
        raw = node.text.strip()
    elif node.type == NodeType.TEXT and node.name:
        raw = node.name
    else:
        raw = node.name
    return raw.replace("\\", "\\\\").replace("'", "\\'")


def render_slider_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str,
) -> str:
    """Render Slider or CupertinoSlider with optional label."""
    value = slider_value_expr(node)
    on_changed = slider_on_changed_expr(node)
    if theme_variant == "cupertino":
        control = f"CupertinoSlider(value: {value}, onChanged: {on_changed})"
    else:
        control = f"Slider(value: {value}, onChanged: {on_changed})"
    if not label:
        return control
    return (
        f"Column("
        f"crossAxisAlignment: CrossAxisAlignment.start, "
        f"children: [Text('{label}'), {control}]"
        f")"
    )


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
            f"CupertinoAlertDialog("
            f"title: Text('{title}'), "
            f"content: SingleChildScrollView("
            f"child: Column(mainAxisSize: MainAxisSize.min, children: [{content}])"
            f"), "
            f"actions: ["
            f"CupertinoDialogAction("
            f"onPressed: () {{ Navigator.of(context).pop(); }}, "
            f"child: const Text('OK')"
            f")"
            f"]"
            f")"
        )
    return (
        f"AlertDialog("
        f"title: Text('{title}'), "
        f"content: SingleChildScrollView("
        f"child: Column(mainAxisSize: MainAxisSize.min, children: [{content}])"
        f"), "
        f"actions: ["
        f"TextButton("
        f"onPressed: () {{ Navigator.of(context).pop(); }}, "
        f"child: const Text('OK')"
        f")"
        f"]"
        f")"
    )


def _is_compact_checkbox_only(node: CleanDesignTreeNode) -> bool:
    from figma_flutter_agent.parser.interaction import looks_like_checkbox_control

    if looks_like_checkbox_control(node):
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


def render_checkbox_widget(
    *,
    label: str,
    node: CleanDesignTreeNode,
    theme_variant: str,
) -> str:
    """Render Checkbox or CupertinoCheckbox with an optional label."""
    value = toggle_value_expr(node)
    on_changed = toggle_on_changed_expr(node)
    if theme_variant == "cupertino":
        control = f"CupertinoCheckbox(value: {value}, onChanged: {on_changed})"
    else:
        control = f"Checkbox(value: {value}, onChanged: {on_changed})"
    if not label or _is_compact_checkbox_only(node):
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
    if theme_variant == "cupertino":
        control = f"CupertinoSwitch(value: {value}, onChanged: {on_changed})"
    else:
        control = f"Switch(value: {value}, onChanged: {on_changed})"
    if not label:
        return control
    return (
        f"Row("
        f"mainAxisAlignment: MainAxisAlignment.spaceBetween, "
        f"children: [Text('{label}'), {control}]"
        f")"
    )


def variant_font_size(node: CleanDesignTreeNode) -> float | None:
    """Resolve font size from variant Size when style.font_size is absent."""
    size_label = variant_size_label(node)
    if size_label is None:
        return None
    return _VARIANT_SIZE_TO_FONT.get(size_label)
