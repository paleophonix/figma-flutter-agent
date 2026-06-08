"""Figma component variant state helpers."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode

DISABLED_VALUES = frozenset({"disabled", "disable", "off", "false"})
LOADING_VALUES = frozenset({"loading", "busy", "pending"})
ERROR_VALUES = frozenset({"error", "invalid", "failed"})
PASSWORD_TYPES = frozenset({"password", "secure", "securetext"})
CHECKED_VALUES = frozenset({"true", "yes", "on", "1", "checked", "selected"})
VARIANT_SIZE_TO_FONT: dict[str, float] = {
    "small": 12.0,
    "medium": 14.0,
    "large": 18.0,
}
BUTTON_KIND_ALIASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("destructive", "danger", "error"), "destructive"),
    (("secondary", "outline", "outlined"), "outlined"),
    (("tertiary", "ghost", "text", "link"), "text"),
    (("primary",), "elevated"),
)


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


def state_value(node: CleanDesignTreeNode) -> str | None:
    if node.variant is None:
        return None
    raw = node.variant.state or get_variant_property(node, "state")
    return raw.strip().lower() if raw else None


def variant_is_disabled(node: CleanDesignTreeNode) -> bool:
    """Return True when component variant metadata marks the control disabled."""
    state = state_value(node)
    if state in DISABLED_VALUES:
        return True
    disabled_flag = get_variant_property(node, "disabled")
    if disabled_flag is not None and disabled_flag.strip().lower() in {"true", "yes", "1"}:
        return True
    enabled_flag = get_variant_property(node, "enabled")
    return enabled_flag is not None and enabled_flag.strip().lower() in {"false", "no", "0"}


def variant_is_loading(node: CleanDesignTreeNode) -> bool:
    """Return True when variant state blocks interaction (loading/busy)."""
    state = state_value(node)
    return state in LOADING_VALUES


def variant_blocks_interaction(node: CleanDesignTreeNode) -> bool:
    """Return True when the control should not accept user input."""
    return variant_is_disabled(node) or variant_is_loading(node)


def variant_button_kind(node: CleanDesignTreeNode) -> str:
    """Map variant Type/Style to elevated, outlined, text, or destructive."""
    raw = get_variant_property(node, "type", "variant", "style", "kind", "hierarchy")
    if raw is None:
        return "elevated"
    normalized = raw.lower().replace("_", " ").replace("-", " ")
    for tokens, kind in BUTTON_KIND_ALIASES:
        if any(token in normalized for token in tokens):
            return kind
    return "elevated"


def variant_is_checked(node: CleanDesignTreeNode) -> bool:
    """Return True when variant State/Checked marks the toggle as on."""
    checked = get_variant_property(node, "checked", "selected", "on")
    if checked is not None:
        return checked.strip().lower() in CHECKED_VALUES
    state = state_value(node)
    return state in CHECKED_VALUES


def variant_input_has_error(node: CleanDesignTreeNode) -> bool:
    """Return True when variant State indicates a validation error."""
    state = state_value(node)
    return state in ERROR_VALUES


def variant_font_size(node: CleanDesignTreeNode) -> float | None:
    """Resolve font size from variant Size when style.font_size is absent."""
    size_label = variant_size_label(node)
    if size_label is None:
        return None
    return VARIANT_SIZE_TO_FONT.get(size_label)


def input_obscure_text_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart bool expression for TextField.obscureText from variant Type."""
    raw = get_variant_property(node, "type", "input type", "inputtype")
    if raw is None:
        return "false"
    return "true" if raw.lower().replace(" ", "") in PASSWORD_TYPES else "false"


def input_enabled_expr(node: CleanDesignTreeNode) -> str:
    """Return Dart expression for TextField/CupertinoTextField enabled flag."""
    return "false" if variant_blocks_interaction(node) else "true"
