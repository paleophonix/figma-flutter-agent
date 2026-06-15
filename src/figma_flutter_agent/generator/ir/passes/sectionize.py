"""Root screen sectionization pass: absolute STACK → responsive COLUMN."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.generator.ir.passes.geometry import (
    _OVERLAP_TOLERANCE_PX,
    child_layout_height,
    child_layout_width,
    child_layout_y,
    stack_children_overlap_on_y,
)
from figma_flutter_agent.generator.ir.passes.protocol import PassContext
from figma_flutter_agent.generator.ir.passes.provenance_record import record_node_mutation
from figma_flutter_agent.generator.ir.passes.sync import (
    index_ir_nodes,
    ir_kind_for_node_type,
)
from figma_flutter_agent.generator.layout.flex_policy.stack import is_viewport_chrome_band
from figma_flutter_agent.generator.layout.widgets.positioned import _should_pin_bottom
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    ScreenIr,
    WidgetIrLayoutHints,
    WidgetIrNode,
)

_SECTION_LAYOUT_ROLE = "responsive_section"


@dataclass(frozen=True)
class SectionizePlan:
    """Partition plan for converting a root STACK into a responsive COLUMN."""

    activated: bool
    top_chrome: tuple[CleanDesignTreeNode, ...] = field(default_factory=tuple)
    scroll_sections: tuple[CleanDesignTreeNode, ...] = field(default_factory=tuple)
    section_gaps: tuple[float, ...] = field(default_factory=tuple)
    bottom_chrome: tuple[CleanDesignTreeNode, ...] = field(default_factory=tuple)
    reject_reason: str | None = None
    evidence: dict[str, object] = field(default_factory=dict)


def _parent_artboard_height(root: CleanDesignTreeNode) -> float | None:
    height = root.sizing.height
    if height is not None and height > 0:
        return float(height)
    frame = root.geometry_frame
    if frame is not None and frame.world_aabb.height > 0:
        return float(frame.world_aabb.height)
    return None


def _is_bottom_pinned_child(
    child: CleanDesignTreeNode,
    *,
    parent_height: float | None,
) -> bool:
    placement = child.stack_placement
    if placement is None:
        return False
    if placement.vertical == "BOTTOM":
        return True
    return _should_pin_bottom(placement, parent_height=parent_height)


def _cluster_y_bands(children: list[CleanDesignTreeNode]) -> list[list[CleanDesignTreeNode]]:
    if not children:
        return []
    ordered = sorted(children, key=lambda child: child_layout_y(child) or 0.0)
    bands: list[list[CleanDesignTreeNode]] = [[ordered[0]]]
    for child in ordered[1:]:
        previous = bands[-1][-1]
        previous_y = child_layout_y(previous) or 0.0
        previous_h = child_layout_height(previous) or 0.0
        child_y = child_layout_y(child) or 0.0
        if stack_children_overlap_on_y(previous, child):
            bands[-1].append(child)
            continue
        if child_y >= previous_y + previous_h - _OVERLAP_TOLERANCE_PX:
            bands.append([child])
        else:
            bands[-1].append(child)
    return bands


def _clear_flex_placement(node: CleanDesignTreeNode) -> CleanDesignTreeNode:
    return node.model_copy(
        update={
            "stack_placement": None,
            "layout_positioning": "AUTO",
            "layout_role": _SECTION_LAYOUT_ROLE,
        },
    )


def _band_to_section_node(band: list[CleanDesignTreeNode]) -> CleanDesignTreeNode | None:
    if len(band) == 1:
        return _clear_flex_placement(band[0])
    stack_hosts = [child for child in band if child.type == NodeType.STACK]
    if not stack_hosts:
        return None
    host = max(
        stack_hosts,
        key=lambda child: (child_layout_height(child) or 0.0) * (child_layout_width(child) or 0.0),
    )
    host_index = band.index(host)
    others = [child for index, child in enumerate(band) if index != host_index]
    if not others:
        return _clear_flex_placement(host)
    merged_children = list(host.children)
    for child in others:
        placement = child.stack_placement
        if placement is not None:
            merged_children.append(child)
        else:
            merged_children.append(child)
    return host.model_copy(
        update={
            "children": merged_children,
            "layout_positioning": "ABSOLUTE",
            "layout_role": _SECTION_LAYOUT_ROLE,
        },
    )


def _section_gaps_from_bands(bands: list[list[CleanDesignTreeNode]]) -> list[float]:
    gaps: list[float] = []
    for index in range(len(bands) - 1):
        current = bands[index][-1]
        nxt = bands[index + 1][0]
        current_y = child_layout_y(current)
        current_h = child_layout_height(current)
        next_y = child_layout_y(nxt)
        if current_y is None or current_h is None or next_y is None:
            gaps.append(0.0)
            continue
        gaps.append(max(0.0, next_y - current_y - current_h))
    return gaps


def evaluate_root_sectionize(
    root: CleanDesignTreeNode,
    *,
    responsive_reflow_enabled: bool,
) -> SectionizePlan:
    """Return whether an absolute root STACK may become a responsive COLUMN."""
    if not responsive_reflow_enabled:
        return SectionizePlan(activated=False, reject_reason="responsive_disabled")
    if root.type != NodeType.STACK or len(root.children) < 2:
        return SectionizePlan(activated=False, reject_reason="not_stack_or_too_few_children")
    parent_height = _parent_artboard_height(root)
    if parent_height is None:
        return SectionizePlan(activated=False, reject_reason="unknown_artboard_height")

    top_chrome: list[CleanDesignTreeNode] = []
    bottom_chrome: list[CleanDesignTreeNode] = []
    scroll_candidates: list[CleanDesignTreeNode] = []
    for child in root.children:
        if is_viewport_chrome_band(child):
            placement = child.stack_placement
            if placement is not None and placement.vertical == "TOP":
                top_chrome.append(child)
                continue
            if placement is not None and placement.vertical == "BOTTOM":
                bottom_chrome.append(child)
                continue
        if _is_bottom_pinned_child(child, parent_height=parent_height):
            bottom_chrome.append(child)
            continue
        scroll_candidates.append(child)

    bands = _cluster_y_bands(scroll_candidates)
    sections: list[CleanDesignTreeNode] = []
    for band in bands:
        section = _band_to_section_node(band)
        if section is None:
            return SectionizePlan(
                activated=False,
                reject_reason="overlapping_band_without_stack_host",
                evidence={"band_size": len(band)},
            )
        sections.append(section)

    if len(sections) < 2 and not bottom_chrome:
        return SectionizePlan(
            activated=False,
            reject_reason="insufficient_sections",
            evidence={"sections": len(sections), "bottom_chrome": len(bottom_chrome)},
        )

    gaps = _section_gaps_from_bands(bands)
    return SectionizePlan(
        activated=True,
        top_chrome=tuple(top_chrome),
        scroll_sections=tuple(sections),
        section_gaps=tuple(gaps),
        bottom_chrome=tuple(bottom_chrome),
        evidence={
            "sections": len(sections),
            "bands": len(bands),
            "bottom_chrome": len(bottom_chrome),
            "top_chrome": len(top_chrome),
        },
    )


def _apply_sectionize_clean(
    root: CleanDesignTreeNode,
    plan: SectionizePlan,
) -> CleanDesignTreeNode:
    column_children = [*plan.top_chrome, *plan.scroll_sections, *plan.bottom_chrome]
    return root.model_copy(
        update={
            "type": NodeType.COLUMN,
            "layout_positioning": "AUTO",
            "scroll_axis": "none",
            "spacing": 0.0,
            "flex_gap_mode": "explicit" if plan.section_gaps else "uniform",
            "flex_explicit_gaps": list(plan.section_gaps) if plan.section_gaps else None,
            "children": column_children,
        },
    )


def _sync_ir_from_clean_subtree(
    ir_node: WidgetIrNode,
    clean_node: CleanDesignTreeNode,
    *,
    ir_index: dict[str, WidgetIrNode],
) -> WidgetIrNode:
    child_ir: list[WidgetIrNode] = []
    for child in clean_node.children:
        mapped = ir_index.get(child.id)
        if mapped is None:
            continue
        child_ir.append(_sync_ir_from_clean_subtree(mapped, child, ir_index=ir_index))
    kind = ir_kind_for_node_type(clean_node.type.value)
    hints = ir_node.layout_hints
    if clean_node.scroll_axis == "vertical":
        hints = WidgetIrLayoutHints(scroll_axis="vertical")
    return ir_node.model_copy(update={"kind": kind, "children": child_ir, "layout_hints": hints})


def sectionize_root_stack(
    screen_ir: ScreenIr,
    clean_tree: CleanDesignTreeNode,
    *,
    responsive_reflow_enabled: bool = True,
    ctx: PassContext | None = None,
) -> tuple[ScreenIr, CleanDesignTreeNode]:
    """Convert an absolute root STACK into a responsive COLUMN with scroll sections."""
    plan = evaluate_root_sectionize(
        clean_tree,
        responsive_reflow_enabled=responsive_reflow_enabled,
    )
    if not plan.activated:
        return screen_ir, clean_tree

    before = clean_tree
    updated_clean = _apply_sectionize_clean(clean_tree, plan)
    ir_index = index_ir_nodes(screen_ir.root)
    updated_root = _sync_ir_from_clean_subtree(screen_ir.root, updated_clean, ir_index=ir_index)
    updated_ir = screen_ir.model_copy(update={"root": updated_root})

    if ctx is not None:
        record_node_mutation(
            ctx,
            transform="sectionize",
            node_id=clean_tree.id,
            field_name="type",
            old=before.type.value,
            new=updated_clean.type.value,
        )
        record_node_mutation(
            ctx,
            transform="sectionize",
            node_id=clean_tree.id,
            field_name="layout_evidence",
            old=None,
            new=plan.evidence,
        )

    return updated_ir, updated_clean
