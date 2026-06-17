"""Layout-level contracts for generated Dart sources."""

from __future__ import annotations

import re
from typing import Literal

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

LayoutResponsiveTier = Literal["reflowed", "scaled", "fixed", "preview"]

LAYOUT_SCROLLABLE_RE = re.compile(
    r"\b(ListView|GridView|PageView|SingleChildScrollView|CustomScrollView)\b"
)

_COMPONENT_SCALEDOWN_RE = re.compile(
    r"FittedBox\s*\(\s*fit:\s*BoxFit\.scaleDown",
    re.MULTILINE,
)


def count_component_scaledown_violations(*sources: str) -> int:
    """Count per-component ``FittedBox(scaleDown)`` wrappers in generated Dart sources.

    Report-only helper for static visual gates; root viewport scale-down is classified
    separately via ``_LAYOUT_VIEWPORT_SCALE_RE``.
    """
    total = 0
    for source in sources:
        if not source:
            continue
        total += len(_COMPONENT_SCALEDOWN_RE.findall(source))
    return total


_LAYOUT_FIXED_DIM_RE = re.compile(r"\b(width|height):\s*(\d+(?:\.\d+)?)")
_LAYOUT_VIEWPORT_SCALE_RE = re.compile(r"FittedBox\s*\(\s*fit:\s*BoxFit\.(?:scaleDown|contain)")


_LAYOUT_VIEWPORT_SCALE_RE = re.compile(r"FittedBox\s*\(\s*fit:\s*BoxFit\.(?:scaleDown|contain)")
_NARROW_VIEWPORT_MAX_PX = 320


def _runtime_layout_tail(layout_source: str) -> str:
    """Return the non-preview fallback portion of generated layout Dart."""
    marker = "_artboardPreviewHeight > 0)"
    if marker in layout_source:
        return layout_source.split(marker, 1)[-1]
    return layout_source


def classify_layout_responsive_tier(
    layout_source: str,
    *,
    root_type: NodeType | None = None,
) -> LayoutResponsiveTier:
    """Classify how a generated layout adapts to host width (LAW-RESPONSIVE-DEFN).

    Args:
        layout_source: Generated ``*_layout.dart`` body or combined layout sources.
        root_type: Parsed clean-tree root type when known.

    Returns:
        ``preview`` for artboard-locked golden paths; ``reflowed`` for scroll/flex
        hosts without root scale-down; ``scaled`` for ``FittedBox`` artboard shrink;
        ``fixed`` when none of the above apply.
    """
    runtime_tail = _runtime_layout_tail(layout_source)
    has_preview_branch = "_artboardPreviewWidth > 0" in layout_source
    has_scale_down = _LAYOUT_VIEWPORT_SCALE_RE.search(runtime_tail) is not None
    has_scroll = LAYOUT_SCROLLABLE_RE.search(runtime_tail) is not None
    has_stretch_column = "Column(" in runtime_tail and "CrossAxisAlignment.stretch" in runtime_tail
    if has_preview_branch and not has_scroll and not has_stretch_column:
        return "preview"
    if has_scale_down and not has_scroll and not has_stretch_column:
        return "scaled"
    if has_scroll or has_stretch_column or root_type == NodeType.COLUMN:
        return "reflowed"
    if has_scale_down:
        return "scaled"
    return "fixed"


def layout_tier_warning_message(tier: LayoutResponsiveTier) -> str | None:
    """Return a UX suggestion when runtime layout tier is not reflowed."""
    if tier == "scaled":
        return (
            "Layout tier is 'scaled' (FittedBox scale-down artboard); enable sectionize "
            "reflow or use Auto Layout in Figma for fluid responsive layout."
        )
    if tier == "fixed":
        return (
            "Layout tier is 'fixed' (no scroll host or flex reflow); verify responsive "
            "layout passes activated for this screen root."
        )
    return None


def layout_scales_to_narrow_viewport(content: str) -> bool:
    """True when the layout file shrinks or scrolls a fixed artboard for narrow widths."""
    if LAYOUT_SCROLLABLE_RE.search(content):
        return True
    return _LAYOUT_VIEWPORT_SCALE_RE.search(content) is not None


def positioned_constraint_arg_strings(layout_source: str) -> list[str]:
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


def assert_valid_positioned_fields(layout_source: str, *, layout_path: str) -> None:
    """Fail when generated ``Positioned`` uses more than two horizontal or vertical pins."""
    for index, args in enumerate(positioned_constraint_arg_strings(layout_source)):
        constraint_args = args.split(", child:", 1)[0]
        horizontal = sum(token in constraint_args for token in ("left:", "right:", "width:"))
        vertical = sum(token in constraint_args for token in ("top:", "bottom:", "height:"))
        if horizontal > 2 or vertical > 2:
            raise GenerationError(
                f"Generated layout '{layout_path}' has invalid Positioned #{index + 1}: "
                "Flutter allows at most two of left/right/width and two of top/bottom/height"
            )


def layout_line_skips_narrow_width_check(line: str) -> bool:
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


def validate_narrow_viewport_layout(planned_files: dict[str, str]) -> None:
    """Codegen contract: layouts must not overflow a 320px logical viewport width."""
    for path, content in planned_files.items():
        if not path.endswith("_layout.dart"):
            continue
        if layout_scales_to_narrow_viewport(content):
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
            if layout_line_skips_narrow_width_check(line):
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


def validate_responsive_reflow_required(
    planned_files: dict[str, str],
    clean_trees: list[CleanDesignTreeNode],
    *,
    require_reflow: bool,
    responsive_enabled: bool,
) -> None:
    """Fail closed when responsive reflow is required but layout tier is not reflowed."""
    if not require_reflow or not responsive_enabled:
        return
    root_type = clean_trees[0].type if clean_trees else None
    for path, content in planned_files.items():
        if not path.endswith("_layout.dart"):
            continue
        tier = classify_layout_responsive_tier(content, root_type=root_type)
        if tier == "reflowed":
            continue
        raise GenerationError(
            f"Generated layout '{path}' has responsive tier '{tier}' but "
            "responsive.require_reflow is enabled; emit scroll/flex reflow instead "
            "of artboard scale-down."
        )


def count_layout_fixed_pixel_sizes(layout_source: str) -> tuple[int, int]:
    """Count numeric width/height on SizedBox/Container lines in layout files."""
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


_METRIC_STRIP_MAX_HEIGHT_PX = 24.0
_METRIC_STRIP_MIN_ASPECT = 2.0


def _root_has_responsive_sections(clean_tree: CleanDesignTreeNode) -> bool:
    return any(child.layout_role == "responsive_section" for child in clean_tree.children)


def classify_clean_tree_responsive_tier(
    clean_tree: CleanDesignTreeNode,
    *,
    responsive_enabled: bool = True,
) -> LayoutResponsiveTier:
    """Classify responsive tier from clean-tree IR before Dart emit."""
    if clean_tree.type == NodeType.COLUMN:
        if clean_tree.scroll_axis == "vertical":
            return "reflowed"
        if _root_has_responsive_sections(clean_tree):
            return "reflowed"
        return "reflowed"
    if clean_tree.type == NodeType.STACK:
        positioned_children = sum(
            1 for child in clean_tree.children if child.stack_placement is not None
        )
        if not responsive_enabled:
            return "fixed"
        if positioned_children >= 3 and clean_tree.scroll_axis == "none":
            return "scaled"
        return "fixed"
    return "fixed"


def _scroll_contract_fields(
    clean_tree: CleanDesignTreeNode,
    *,
    responsive_enabled: bool,
) -> dict[str, object]:
    """Infer scroll hosts for fallback vs artboard preview runtime branches."""
    from figma_flutter_agent.generator.artboard import is_tall_mobile_artboard
    from figma_flutter_agent.generator.layout.widgets.positioned import (
        _stack_has_bottom_anchored_child,
    )

    width = clean_tree.sizing.width
    height = clean_tree.sizing.height
    tall_content = is_tall_mobile_artboard(width, height)
    tree_scrollable = clean_tree.scroll_axis != "none"
    pin_bottom = clean_tree.type == NodeType.STACK and _stack_has_bottom_anchored_child(clean_tree)
    fallback_scrollable = bool(
        tree_scrollable or tall_content or (pin_bottom and not responsive_enabled)
    )
    preview_capture_scrollable = False
    preview_interactive_scrollable = bool(tree_scrollable or tall_content)
    return {
        "tall_content": tall_content,
        "fallback_scrollable": fallback_scrollable,
        "preview_capture_scrollable": preview_capture_scrollable,
        "preview_interactive_scrollable": preview_interactive_scrollable,
        "active_branch_interactive_dev": "fallback",
        "active_branch_golden_capture": "preview_capture",
        "effective_scrollable": fallback_scrollable,
    }


def build_responsiveness_report(
    clean_tree: CleanDesignTreeNode,
    *,
    responsive_enabled: bool = True,
) -> dict[str, object]:
    """Build a debug report describing runtime responsiveness of the emit tree.

    Args:
        clean_tree: Clean tree after layout passes (or pre-pass when static).
        responsive_enabled: When false (``responsive.mode: static``), the report
            records ``verdict: skip`` because reflow is intentionally disabled.
    """
    if not responsive_enabled:
        tier = classify_clean_tree_responsive_tier(
            clean_tree,
            responsive_enabled=False,
        )
        positioned_root_children = 0
        if clean_tree.type == NodeType.STACK:
            positioned_root_children = sum(
                1 for child in clean_tree.children if child.stack_placement is not None
            )
        return {
            "root_layout": clean_tree.type.value.lower(),
            "positioned_root_children": positioned_root_children,
            "responsive_flow_sections": sum(
                1 for child in clean_tree.children if child.layout_role == "responsive_section"
            ),
            "scrollable": clean_tree.scroll_axis != "none",
            "bottom_panel_mode": "absolute_top",
            "tier": tier,
            "verdict": "skip",
            "law": None,
            "responsive_enabled": False,
            **_scroll_contract_fields(clean_tree, responsive_enabled=False),
        }
    tier = classify_clean_tree_responsive_tier(
        clean_tree,
        responsive_enabled=responsive_enabled,
    )
    positioned_root_children = 0
    if clean_tree.type == NodeType.STACK:
        positioned_root_children = sum(
            1 for child in clean_tree.children if child.stack_placement is not None
        )
    responsive_flow_sections = sum(
        1 for child in clean_tree.children if child.layout_role == "responsive_section"
    )
    scrollable = clean_tree.scroll_axis != "none"
    bottom_panel_mode = "absolute_top"
    if clean_tree.type == NodeType.COLUMN and clean_tree.children:
        last_child = clean_tree.children[-1]
        if last_child.stack_placement is None and last_child.type == NodeType.STACK:
            bottom_panel_mode = "pinned_section"
    verdict = "pass" if tier == "reflowed" else "fail"
    law: str | None = (
        None
        if verdict == "pass"
        else "runtime_screen_must_not_be_full_artboard_absolute_stack"
    )
    return {
        "root_layout": clean_tree.type.value.lower(),
        "positioned_root_children": positioned_root_children,
        "responsive_flow_sections": responsive_flow_sections,
        "scrollable": scrollable,
        "bottom_panel_mode": bottom_panel_mode,
        "tier": tier,
        "verdict": verdict,
        "law": law,
        "responsive_enabled": True,
        **_scroll_contract_fields(clean_tree, responsive_enabled=True),
    }
