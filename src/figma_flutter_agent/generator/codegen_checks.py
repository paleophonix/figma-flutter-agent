"""Deterministic validation for generated Dart sources."""

from __future__ import annotations

import re

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.dart_postprocess import TEXT_DISPLAY_WIDGET_RE
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, SizingMode

_FIXED_WIDTH_RE = re.compile(r"width:\s*\d+(?:\.\d+)?(?!\s*\*)")
_FIXED_HEIGHT_RE = re.compile(r"height:\s*\d+(?:\.\d+)?(?!\s*\*)")
_SEMANTICS_RE = re.compile(r"\bSemantics\s*\(")
_TEXT_SCALER_RE = re.compile(
    r"(textScaler:\s*MediaQuery\.textScalerOf\(\w+\)|"
    r"(?:final|var)\s+\w*\s*textScaler\s*=\s*MediaQuery\.textScalerOf\(\w+\))"
)
_RESPONSIVE_SHELL_RE = re.compile(r"\bGeneratedScreenShell\s*\(")
_FLEX_WIDGET_RE = re.compile(r"\b(Expanded|Flexible)\s*\(")
_OVERLAY_HELPER_RE = re.compile(r"\b(showModalBottomSheet|showDialog)\s*[(<]")
_LAYOUT_FIXED_DIM_RE = re.compile(r"\b(width|height):\s*(\d+(?:\.\d+)?)")
_NARROW_VIEWPORT_MAX_PX = 320
_SCROLLABLE_LAYOUT_RE = re.compile(
    r"\b(ListView|GridView|PageView|SingleChildScrollView|CustomScrollView)\b"
)


def _collect_interactive_nodes(
    node: CleanDesignTreeNode,
    *,
    parent_type: NodeType | None = None,
) -> list[CleanDesignTreeNode]:
    """Collect nodes that require explicit Semantics in generated Dart."""
    interactive: list[CleanDesignTreeNode] = []
    if node.type in {NodeType.BUTTON, NodeType.INPUT} or (
        node.accessibility_label
        and not (node.type == NodeType.TEXT and parent_type in {NodeType.BOTTOM_NAV, NodeType.TABS})
    ):
        interactive.append(node)
    for child in node.children:
        interactive.extend(_collect_interactive_nodes(child, parent_type=node.type))
    return interactive


def _collect_fill_sizing_nodes(node: CleanDesignTreeNode) -> list[CleanDesignTreeNode]:
    fill_nodes: list[CleanDesignTreeNode] = []
    if node.sizing.width_mode == SizingMode.FILL or node.sizing.height_mode == SizingMode.FILL:
        fill_nodes.append(node)
    for child in node.children:
        fill_nodes.extend(_collect_fill_sizing_nodes(child))
    return fill_nodes


def _positioned_constraint_arg_strings(layout_source: str) -> list[str]:
    """Extract argument strings for each ``Positioned(…, child:`` in layout Dart."""
    args_list: list[str] = []
    needle = "Positioned("
    search_from = 0
    while True:
        start = layout_source.find(needle, search_from)
        if start < 0:
            break
        depth = 1
        j = start + len(needle)
        while j < len(layout_source):
            char = layout_source[j]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    args_list.append(layout_source[start + len(needle) : j])
                    search_from = j + 1
                    break
            j += 1
        else:
            break
    return args_list


def _assert_valid_positioned_fields(layout_source: str, *, layout_path: str) -> None:
    """Fail when generated ``Positioned`` uses more than two horizontal or vertical pins."""
    for index, args in enumerate(_positioned_constraint_arg_strings(layout_source)):
        constraint_args = args.split(", child:", 1)[0]
        horizontal = sum(token in constraint_args for token in ("left:", "right:", "width:"))
        vertical = sum(token in constraint_args for token in ("top:", "bottom:", "height:"))
        if horizontal > 2 or vertical > 2:
            raise GenerationError(
                f"Generated layout '{layout_path}' has invalid Positioned #{index + 1}: "
                "Flutter allows at most two of left/right/width and two of top/bottom/height"
            )


def _layout_line_skips_narrow_width_check(line: str) -> bool:
    """Return True when a layout line may use bounded pixel widths safely."""
    return any(
        token in line
        for token in (
            "double.infinity",
            "Positioned(",
            "AspectRatio(",
            "PageView(",
            "ListView",
            "GridView",
            "SvgPicture",
        )
    )


def _validate_narrow_viewport_layout(planned_files: dict[str, str]) -> None:
    """Codegen contract: layouts must not overflow a 320px logical viewport width."""
    for path, content in planned_files.items():
        if not path.endswith("_layout.dart"):
            continue
        if _SCROLLABLE_LAYOUT_RE.search(content):
            continue
        if "Column(" in content:
            has_stretch = "CrossAxisAlignment.stretch" in content
            has_other_cross = "crossAxisAlignment:" in content and not has_stretch
            if has_other_cross:
                raise GenerationError(
                    f"Generated layout '{path}' must use CrossAxisAlignment.stretch "
                    "for narrow viewports (spec section 7.3)"
                )
        for line in content.splitlines():
            if _layout_line_skips_narrow_width_check(line):
                continue
            for dimension, value_str in _LAYOUT_FIXED_DIM_RE.findall(line):
                if dimension != "width":
                    continue
                value = float(value_str)
                if value > _NARROW_VIEWPORT_MAX_PX:
                    raise GenerationError(
                        f"Generated layout '{path}' uses width {value:g}px, which exceeds "
                        f"narrow viewport max ({_NARROW_VIEWPORT_MAX_PX}px); use flexible or scroll layout"
                    )


def _assert_strict_interactive_semantics(
    interactive_nodes: list[CleanDesignTreeNode],
    ui_dart_source: str,
) -> None:
    """Require Semantics coverage for every button and input in the design tree."""
    controls = [
        node for node in interactive_nodes if node.type in {NodeType.BUTTON, NodeType.INPUT}
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
        raise GenerationError("Generated Dart omits Semantics for interactive controls: " + detail)


def _count_layout_fixed_pixel_sizes(layout_source: str) -> tuple[int, int]:
    """Count numeric width/height on SizedBox/Container lines in layout files.

    Skips ``double.infinity``, icon assets, and ``Positioned`` constraint fields.
    """
    width_count = 0
    height_count = 0
    for line in layout_source.splitlines():
        if "double.infinity" in line or "SvgPicture.asset" in line:
            continue
        if "Positioned(" in line:
            continue
        if "SizedBox(" not in line and "Container(" not in line:
            continue
        for dimension, _value in _LAYOUT_FIXED_DIM_RE.findall(line):
            if dimension == "width":
                width_count += 1
            else:
                height_count += 1
    return width_count, height_count


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
    use_deterministic_screen: bool = True,
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
        use_deterministic_screen: When False (LLM screen body), fixed pixel sizes in
            ``*_screen.dart`` are reported as warnings instead of hard failures.

    Returns:
        Non-fatal warning messages for soft contract violations.

    Raises:
        GenerationError: When required accessibility semantics are missing.
    """
    screen_files = {
        path: content for path, content in planned_files.items() if path.endswith("_screen.dart")
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
        content for path, content in planned_files.items() if path.endswith("_layout.dart")
    )
    ui_dart_source = "\n".join(ui_dart_sources.values())
    warnings: list[str] = []
    trees = _normalize_clean_trees(clean_trees)
    shell_required = (
        require_responsive_shell if require_responsive_shell is not None else responsive_enabled
    )

    interactive_nodes: list[CleanDesignTreeNode] = []
    fill_nodes: list[CleanDesignTreeNode] = []
    for tree in trees:
        interactive_nodes.extend(_collect_interactive_nodes(tree))
        fill_nodes.extend(_collect_fill_sizing_nodes(tree))

    labels = [node.accessibility_label for node in interactive_nodes if node.accessibility_label]

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
            warnings.append("Generated screens may omit explicit accessibility labels: " + detail)

    for path, content in planned_files.items():
        if path.endswith("_layout.dart"):
            _assert_valid_positioned_fields(content, layout_path=path)

    if shell_required:
        _validate_narrow_viewport_layout(planned_files)
        for path, content in screen_files.items():
            if _RESPONSIVE_SHELL_RE.search(content):
                continue
            raise GenerationError(
                f"Generated screen '{path}' is missing GeneratedScreenShell despite responsive layout being enabled"
            )

    sources_missing_text_scaler = [
        path
        for path, content in ui_dart_sources.items()
        if TEXT_DISPLAY_WIDGET_RE.search(content) and not _TEXT_SCALER_RE.search(content)
    ]
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
            if use_deterministic_screen:
                raise GenerationError(
                    f"{message}; deterministic screen shells require flexible sizing"
                )
            warnings.append(message)
        if fixed_height_count >= 1:
            message = (
                f"Generated screen Dart contains {fixed_height_count} fixed height values; "
                "responsive layout prefers flexible sizing"
            )
            if use_deterministic_screen:
                raise GenerationError(
                    f"{message}; deterministic screen shells require flexible sizing"
                )
            warnings.append(message)

        if layout_sources:
            layout_width_count, layout_height_count = _count_layout_fixed_pixel_sizes(
                layout_sources
            )
            classic_absolute_frame = _SCROLLABLE_LAYOUT_RE.search(
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
