"""Infer constructor parameters for parameterized cluster widgets."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType


@dataclass(frozen=True)
class WidgetParamSpec:
    """Single Dart constructor parameter for a parameterized widget."""

    name: str
    dart_type: str
    default_literal: str


@dataclass(frozen=True)
class WidgetParamBundle:
    """Constructor params and representative literal replacements."""

    params: tuple[WidgetParamSpec, ...]
    text_literals: tuple[tuple[str, str], ...]


def diff_props(members: list[CleanDesignTreeNode]) -> WidgetParamBundle | None:
    """Build widget params when members share shape but differ in text slots."""
    if len(members) < 2:
        return None
    slots = _collect_text_slots(members)
    if not slots:
        return None
    params: list[WidgetParamSpec] = []
    replacements: list[tuple[str, str]] = []
    for index, (literal, _values) in enumerate(slots):
        name = _param_name_for_slot(index, literal)
        params.append(
            WidgetParamSpec(
                name=name,
                dart_type="String",
                default_literal=f"'{escape_dart_string(literal)}'",
            )
        )
        replacements.append((literal, name))
    return WidgetParamBundle(params=tuple(params), text_literals=tuple(replacements))


def render_widget_fields(bundle: WidgetParamBundle) -> str:
    """Render Dart field declarations for a param bundle."""
    lines = [f"  final {spec.dart_type} {spec.name};" for spec in bundle.params]
    if not lines:
        return ""
    return "\n".join(lines) + "\n\n"


def render_constructor_params(bundle: WidgetParamBundle) -> str:
    """Render Dart constructor parameter list for a param bundle."""
    if not bundle.params:
        return "{super.key}"
    parts = ["super.key"]
    for spec in bundle.params:
        parts.append(f"this.{spec.name} = {spec.default_literal}")
    return "{" + ", ".join(parts) + "}"


def parameterize_widget_body(body: str, bundle: WidgetParamBundle) -> str:
    """Replace representative text literals with constructor parameter references."""
    updated = body
    for literal, param_name in bundle.text_literals:
        quoted = escape_dart_string(literal)
        pattern = f"Text('{quoted}'"
        if pattern in updated:
            updated = updated.replace(pattern, f"Text({param_name}", 1)
            continue
        lower_pattern = f"Text('{escape_dart_string(literal.lower())}'"
        if lower_pattern in updated:
            updated = updated.replace(lower_pattern, f"Text({param_name}", 1)
    return updated


def cluster_reference_args_for_member(
    member: CleanDesignTreeNode,
    bundle: WidgetParamBundle,
    *,
    representative: CleanDesignTreeNode,
) -> str:
    """Build named constructor args for a cluster member from its text slots."""
    member_slots = _text_values_by_path(member)
    rep_slots = _text_values_by_path(representative)
    args: list[str] = []
    for index, (path, rep_value) in enumerate(rep_slots):
        if index >= len(bundle.params):
            break
        member_value = member_slots.get(path)
        if member_value is None or member_value == rep_value:
            continue
        param = bundle.params[index]
        args.append(f"{param.name}: '{escape_dart_string(member_value)}'")
    return ", ".join(args)


def _collect_text_slots(
    members: list[CleanDesignTreeNode],
) -> list[tuple[str, set[str]]]:
    """Return text literals whose values differ across members at stable paths."""
    paths: dict[str, set[str]] = {}
    rep_paths = _text_values_by_path(members[0])
    for path in rep_paths:
        paths[path] = set()
    for member in members:
        for path, value in _text_values_by_path(member).items():
            paths.setdefault(path, set()).add(value)
    slots: list[tuple[str, set[str]]] = []
    for path, values in paths.items():
        if len(values) <= 1:
            continue
        rep_literal = rep_paths.get(path, "")
        if rep_literal:
            slots.append((rep_literal, values))
    return slots


def _text_values_by_path(node: CleanDesignTreeNode, prefix: str = "") -> dict[str, str]:
    values: dict[str, str] = {}

    def walk(current: CleanDesignTreeNode, path: str) -> None:
        if current.type == NodeType.TEXT:
            raw = (current.text or current.name or "").strip()
            if raw:
                values[path or "0"] = raw
        for index, child in enumerate(current.children):
            walk(child, f"{path}/{index}:{child.type.value}")

    walk(node, prefix)
    return values


def _param_name_for_slot(index: int, literal: str) -> str:
    _ = literal
    if index == 0:
        return "title"
    if index == 1:
        return "subtitle"
    return f"label{index + 1}"
