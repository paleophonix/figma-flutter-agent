"""Deterministic validation for generated Dart sources."""

from __future__ import annotations

import re

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.checks.layout import (
    LAYOUT_SCROLLABLE_RE,
    assert_valid_positioned_fields,
    count_layout_fixed_pixel_sizes,
    validate_narrow_viewport_layout,
)
from figma_flutter_agent.generator.checks.text_scaler import text_scaler_missing_paths
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_FIXED_WIDTH_RE = re.compile(r"width:\s*\d+(?:\.\d+)?(?!\s*\*)")
_FIXED_HEIGHT_RE = re.compile(r"height:\s*\d+(?:\.\d+)?(?!\s*\*)")
_SEMANTICS_RE = re.compile(r"\bSemantics\s*\(")
_RESPONSIVE_SHELL_RE = re.compile(r"\bGeneratedScreenShell\s*\(")
_FLEX_WIDGET_RE = re.compile(r"\b(Expanded|Flexible)\s*\(")
_OVERLAY_HELPER_RE = re.compile(r"\b(showModalBottomSheet|showDialog)\s*[(<]")


def _collect_interactive_nodes(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None = None,
) -> list[CleanDesignTreeNode]:
    """Collect nodes that require explicit Semantics in generated Dart."""
    interactive: list[CleanDesignTreeNode] = []
    if node.type in {NodeType.BUTTON, NodeType.INPUT} or (
        node.accessibility_label
        and not (
            node.type == NodeType.TEXT
            and parent_type in {NodeType.BOTTOM_NAV, NodeType.TABS}
        )
    ):
        interactive.append(node)
    for child in node.children:
        interactive.extend(_collect_interactive_nodes(child, parent_type=node.type))
    return interactive


def _collect_fill_sizing_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    fill_nodes: list[CleanDesignTreeNode] = []
    if (
        node.sizing.width_mode == SizingMode.FILL
        or node.sizing.height_mode == SizingMode.FILL
    ):
        fill_nodes.append(node)
    for child in node.children:
        fill_nodes.extend(_collect_fill_sizing_nodes(child))
    return fill_nodes


def _assert_strict_interactive_semantics(
    interactive_nodes: list[CleanDesignTreeNode],
    ui_dart_source: str,
) -> None:
    """Require Semantics coverage for every button and input in the design tree."""
    controls = [
        node
        for node in interactive_nodes
        if node.type in {NodeType.BUTTON, NodeType.INPUT}
    ]
    if not controls:
        return
    if not _SEMANTICS_RE.search(ui_dart_source):
        raise GenerationError(
            "Generated Dart is missing Semantics widgets for interactive controls"
        )
    missing: list[str] = []
    for node in controls:
        label = (node.accessibility_label or node.text or node.name or "").strip()
        if not label:
            missing.append(node.name or node.id)
            continue
        if label not in ui_dart_source:
            missing.append(label)
    if missing:
        detail = ", ".join(missing[:5])
        raise GenerationError(
            "Generated Dart omits Semantics for interactive controls: " + detail
        )


def _normalize_clean_trees(
    clean_trees: CleanDesignTreeNode | list[CleanDesignTreeNode],
) -> list[CleanDesignTreeNode]:
    if isinstance(clean_trees, list):
        return clean_trees
    return [clean_trees]


def validate_generated_dart(
    planned_files: dict[str, str],
    clean_trees: CleanDesignTreeNode | list[CleanDesignTreeNode],
    *,
    responsive_enabled: bool,
    avoid_fixed_sizes: bool,
    require_overlay_helpers: bool = False,
    strict_accessibility_labels: bool = False,
    require_responsive_shell: bool | None = None,
) -> list[str]:
    """Validate generated Dart against accessibility and responsive contracts.

    Args:
        planned_files: Planned project files keyed by relative path.
        clean_trees: One or more parsed clean design trees to validate against.
        responsive_enabled: Whether responsive generation is enabled in config.
        avoid_fixed_sizes: Whether fixed pixel widths should be avoided.
        require_overlay_helpers: When True, require modal helpers for overlay links.
        strict_accessibility_labels: When True, fail if labels are missing from Dart output.
        require_responsive_shell: When set, overrides shell requirement (planner uses this for
            absolute ``STACK`` frames that skip ``GeneratedScreenShell``).
    Returns:
        Non-fatal warning messages for soft contract violations.

    Raises:
        GenerationError: When required accessibility semantics are missing.
    """
    screen_files = {
        path: content
        for path, content in planned_files.items()
        if path.endswith("_screen.dart")
    }
    ui_dart_sources = {
        path: content
        for path, content in planned_files.items()
        if path.endswith(".dart")
        and path.startswith(
            ("lib/features/", "lib/presentation/", "lib/generated/", "lib/widgets/")
        )
    }
    if not screen_files and not ui_dart_sources:
        return []

    screen_sources = "\n".join(screen_files.values())
    layout_sources = "\n".join(
        content
        for path, content in planned_files.items()
        if path.endswith("_layout.dart")
    )
    ui_dart_source = "\n".join(ui_dart_sources.values())
    warnings: list[str] = []
    trees = _normalize_clean_trees(clean_trees)
    shell_required = (
        require_responsive_shell
        if require_responsive_shell is not None
        else responsive_enabled
    )

    interactive_nodes: list[CleanDesignTreeNode] = []
    fill_nodes: list[CleanDesignTreeNode] = []
    for tree in trees:
        interactive_nodes.extend(_collect_interactive_nodes(tree))
        fill_nodes.extend(_collect_fill_sizing_nodes(tree))

    labels = [
        node.accessibility_label
        for node in interactive_nodes
        if node.accessibility_label
    ]

    if labels and not _SEMANTICS_RE.search(ui_dart_source):
        raise GenerationError(
            "Generated Dart is missing Semantics widgets despite accessibility labels in the design tree"
        )

    if strict_accessibility_labels:
        _assert_strict_interactive_semantics(interactive_nodes, ui_dart_source)

    if labels:
        missing_labels = [label for label in labels if label not in ui_dart_source]
        if missing_labels:
            detail = ", ".join(missing_labels[:5])
            if strict_accessibility_labels:
                raise GenerationError(
                    "Generated Dart omits accessibility labels present in the design tree: "
                    + detail
                )
            warnings.append(
                "Generated screens may omit explicit accessibility labels: " + detail
            )

    for path, content in planned_files.items():
        if path.endswith("_layout.dart"):
            assert_valid_positioned_fields(content, layout_path=path)

    if shell_required:
        validate_narrow_viewport_layout(planned_files)
        for path, content in screen_files.items():
            if _RESPONSIVE_SHELL_RE.search(content):
                continue
            raise GenerationError(
                f"Generated screen '{path}' is missing GeneratedScreenShell despite responsive layout being enabled"
            )

    sources_missing_text_scaler = text_scaler_missing_paths(ui_dart_sources)
    if sources_missing_text_scaler:
        raise GenerationError(
            "Generated Dart files missing MediaQuery.textScalerOf(context): "
            + ", ".join(sources_missing_text_scaler[:5])
        )

    if require_overlay_helpers and "prototype_navigation.dart" in planned_files:
        helper_source = planned_files["lib/core/prototype_navigation.dart"]
        if "overlay" in helper_source and not _OVERLAY_HELPER_RE.search(helper_source):
            warnings.append(
                "Overlay prototype links exist but no showModalBottomSheet/showDialog helper was generated"
            )

    if responsive_enabled and avoid_fixed_sizes:
        if fill_nodes and not _FLEX_WIDGET_RE.search(screen_sources):
            warnings.append(
                f"Design trees have {len(fill_nodes)} FILL-sized nodes but generated screens "
                "do not use Expanded/Flexible widgets"
            )

        # Only screen shells are required to avoid fixed pixels; deterministic layout
        # files may use AspectRatio/Expanded for bounded regions (carousel, etc.).
        fixed_width_count = len(_FIXED_WIDTH_RE.findall(screen_sources))
        fixed_height_count = len(_FIXED_HEIGHT_RE.findall(screen_sources))
        if fixed_width_count >= 1:
            message = (
                f"Generated screen Dart contains {fixed_width_count} fixed width values; "
                "responsive layout prefers flexible sizing"
            )
            warnings.append(message)
        if fixed_height_count >= 1:
            message = (
                f"Generated screen Dart contains {fixed_height_count} fixed height values; "
                "responsive layout prefers flexible sizing"
            )
            warnings.append(message)

        if layout_sources:
            layout_width_count, layout_height_count = count_layout_fixed_pixel_sizes(
                layout_sources
            )
            classic_absolute_frame = LAYOUT_SCROLLABLE_RE.search(
                layout_sources
            ) is not None or any(tree.type == NodeType.STACK for tree in trees)
            if layout_width_count >= 1 and not classic_absolute_frame:
                raise GenerationError(
                    f"Generated layout Dart contains {layout_width_count} fixed width values "
                    "in SizedBox/Container; use Expanded/Flexible or breakpoint-aware sizing"
                )
            if layout_height_count >= 1 and not classic_absolute_frame:
                raise GenerationError(
                    f"Generated layout Dart contains {layout_height_count} fixed height values "
                    "in SizedBox/Container; use Expanded/Flexible or breakpoint-aware sizing"
                )

    return warnings
