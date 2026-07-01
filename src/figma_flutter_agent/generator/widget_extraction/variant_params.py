"""Map Figma variant properties to Dart widget constructor parameters."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode


def variant_reference_args(node: CleanDesignTreeNode) -> str:
    """Build constructor args from Figma variant properties on ``node``."""
    variant = node.variant
    if variant is None:
        return ""
    props = {str(key).strip().lower(): str(value).strip().lower() for key, value in variant.variant_properties.items()}
    args: list[str] = []
    state = props.get("state") or (variant.state or "").strip().lower()
    if state == "disabled":
        args.append("enabled: false")
    selected = props.get("selected")
    if selected in {"true", "yes", "on", "selected"}:
        args.append("isSelected: true")
    elif selected in {"false", "no", "off"}:
        args.append("isSelected: false")
    return ", ".join(args)


def variant_widget_fields(node: CleanDesignTreeNode) -> str:
    """Return extra widget fields required for variant parameterization."""
    args = variant_reference_args(node)
    fields: list[str] = []
    if "enabled:" in args:
        fields.append("  final bool enabled;")
    if "isSelected:" in args:
        fields.append("  final bool isSelected;")
    if not fields:
        return ""
    return "\n".join(fields) + "\n\n"


def variant_constructor_params(node: CleanDesignTreeNode) -> str | None:
    """Return constructor params when variant mapping applies."""
    variant = node.variant
    if variant is None:
        return None
    props = {str(key).strip().lower(): str(value).strip().lower() for key, value in variant.variant_properties.items()}
    parts = ["super.key"]
    state = props.get("state") or (variant.state or "").strip().lower()
    if state == "disabled":
        parts.append("this.enabled = false")
    selected = props.get("selected")
    if selected in {"true", "yes", "on", "selected"}:
        parts.append("this.isSelected = true")
    elif selected in {"false", "no", "off"}:
        parts.append("this.isSelected = false")
    if len(parts) == 1:
        return None
    return "{" + ", ".join(parts) + "}"
