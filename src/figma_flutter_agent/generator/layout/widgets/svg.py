"""SVG/vector rendering, rotation transforms, icon-stack heuristics."""

from __future__ import annotations

import math

from figma_flutter_agent.generator.geometry.affine import (
    matrix4_close_suffix,
    matrix4_compose_expr,
    requires_raster_tier,
)
from figma_flutter_agent.generator.layout.common import escape_dart_string
from figma_flutter_agent.generator.render_units import (
    format_figma_blur_sigma_literal,
)
from figma_flutter_agent.parser.numeric_rounding import (
    format_geometry_literal,
    format_micro_style_literal,
    round_geometry,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeType,
    SizingMode,
    StackPlacement,
)

from .shared import (
    _ICON_BUTTON_MAX_SIZE,
    _OVERLAY_TEXT_MAX_SIZE,
    _node_layout_size,
)

_RASTER_ASSET_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

_PI_ROTATION = 3.141592653589793
_TWO_PI = 2.0 * _PI_ROTATION
_COMPACT_NAV_ICON_MAX_PX = 32.0
_ICON_RAIL_GLYPH_SIZE = 20.0
_ICON_RAIL_FRAME_MIN = 40.0
_ICON_RAIL_FRAME_MAX = 56.0
SVG_PATH_RASTER_THRESHOLD = 120
_SKIP_CONTROL_MAX_EXTENT_PX = 120.0
_HAIRLINE_MAX_THICKNESS = 1.0


def _is_skip_control_stack(parent_node: CleanDesignTreeNode) -> bool:
    """Detect skip/rewind stacks that pair an arc vector with a numeric label."""
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_numeric_glyph_overlay_host,
        stack_hosts_notification_badge_overlay,
    )
    from figma_flutter_agent.parser.interaction.step import layout_fact_step_indicator_glyph_stack

    if layout_fact_step_indicator_glyph_stack(parent_node):
        return False

    if stack_hosts_notification_badge_overlay(parent_node):
        return False
    if layout_fact_stack_numeric_glyph_overlay_host(parent_node):
        return False
    if parent_node.type != NodeType.STACK:
        return False
    stack_width = parent_node.sizing.width
    stack_height = parent_node.sizing.height
    if stack_width is None or stack_height is None:
        return False
    if (
        float(stack_width) > _SKIP_CONTROL_MAX_EXTENT_PX
        or float(stack_height) > _SKIP_CONTROL_MAX_EXTENT_PX
    ):
        return False
    has_vector = any(
        child.type == NodeType.VECTOR and (child.vector_asset_key or child.style.has_stroke)
        for child in parent_node.children
    )
    numeric_labels = [
        child
        for child in parent_node.children
        if child.type == NodeType.TEXT and (child.text or "").strip().isdigit()
    ]
    if len(numeric_labels) != 1:
        return False
    return has_vector


def _effective_svg_dimensions(
    node: CleanDesignTreeNode,
    width: float | None,
    height: float | None,
) -> tuple[float | None, float | None]:
    """Ensure stroke-only SVG exports remain visible when Figma bbox height/width is ~0."""
    if not node.style.has_stroke:
        return width, height
    stroke = node.style.border_width or 3.0
    min_dim = max(stroke, 3.0)
    if width is not None and height is not None:
        if width >= min_dim * 4 and height < min_dim:
            height = _HAIRLINE_MAX_THICKNESS if height <= _HAIRLINE_MAX_THICKNESS else min_dim
        elif height >= min_dim * 4 and width < min_dim:
            width = _HAIRLINE_MAX_THICKNESS if width <= _HAIRLINE_MAX_THICKNESS else min_dim
    elif width is not None and width < min_dim:
        width = min_dim
    elif height is not None and height < min_dim:
        height = min_dim
    return width, height


def _stroke_line_top_adjustment(
    node: CleanDesignTreeNode,
    placement: StackPlacement,
    render_height: float | None,
) -> float | None:
    """Center expanded stroke-line bounds on the original Figma baseline."""
    if not node.style.has_stroke or placement.top is None or render_height is None:
        return placement.top
    raw_height = node.sizing.height or 0.0
    if raw_height >= render_height:
        return placement.top
    adjusted = placement.top - (render_height - raw_height) / 2.0
    return round_geometry(adjusted) or 0.0


_SKIP_NUMERAL_DOWN_NUDGE = 2.5


def _skip_control_numeral_top(
    parent_node: CleanDesignTreeNode,
    text_node: CleanDesignTreeNode,
    placement: StackPlacement,
) -> float:
    """Vertically center skip numerals inside the arc with a small optical nudge."""
    parent_height = parent_node.sizing.height or 0.0
    text_height = text_node.sizing.height or placement.height or 0.0
    if parent_height <= 0 or text_height <= 0:
        return placement.top or 0.0
    adjusted = (parent_height - text_height) / 2.0 + _SKIP_NUMERAL_DOWN_NUDGE
    return round_geometry(adjusted) or 0.0


def _slider_thumb_top(
    outer: CleanDesignTreeNode,
    siblings: list[CleanDesignTreeNode],
    default_top: float,
) -> float:
    """Align slider thumbs to the visual center of a sibling progress stroke."""
    outer_height = outer.sizing.height or 17.0
    outer_left = outer.stack_placement.left if outer.stack_placement else 0.0
    outer_right = outer_left + (outer.sizing.width or outer_height)
    for sibling in siblings:
        if (
            sibling.id == outer.id
            or sibling.type != NodeType.VECTOR
            or not sibling.style.has_stroke
        ):
            continue
        placement = sibling.stack_placement
        if placement is None:
            continue
        track_left = placement.left or 0.0
        track_width = sibling.sizing.width or 0.0
        track_right = track_left + track_width
        if track_right < outer_left - 8.0 or track_left > outer_right + 8.0:
            continue
        _track_width, effective_height = _effective_svg_dimensions(
            sibling,
            sibling.sizing.width,
            sibling.sizing.height,
        )
        effective_height = effective_height or 3.0
        raw_height = sibling.sizing.height or 0.0
        line_top = placement.top or 0.0
        if raw_height < effective_height:
            line_top -= (effective_height - raw_height) / 2.0
        line_center = line_top + effective_height / 2.0
        adjusted = line_center - outer_height / 2.0
        return round_geometry(adjusted) or 0.0
    return default_top


_ICON_MAX_BOX_FIT_CONTAIN = 32.0
_METRIC_STRIP_MAX_HEIGHT = 24.0
_METRIC_STRIP_MIN_ASPECT = 2.0


def _svg_fit_mode(
    node: CleanDesignTreeNode,
    width: float | None,
    height: float | None,
) -> str:
    """Choose BoxFit for exported SVG assets."""
    if (
        node.render_boundary
        and node.flatten_figma_node_ids
        and width
        and height
        and max(float(width), float(height)) > _ICON_MAX_BOX_FIT_CONTAIN
    ):
        if node.image_asset_key and not node.image_asset_key.lower().endswith(".svg"):
            return "BoxFit.cover"
        return "BoxFit.cover"
    if (
        node.style.has_stroke
        and width is not None
        and height is not None
        and width >= 12.0
        and height <= _HAIRLINE_MAX_THICKNESS
    ):
        return "BoxFit.fitWidth"
    if node.style.has_stroke and node.style.background_color is None:
        if width and height and (width < 4.0 or height < 4.0):
            return "BoxFit.fill"
        return "BoxFit.contain"
    if node.style.gradient is not None and width and height:
        return "BoxFit.contain"
    if (
        width
        and height
        and width > 0
        and height > 0
        and height > width * 1.15
        and max(width, height) <= 64.0
    ):
        return "BoxFit.contain"
    if (
        width
        and height
        and width > 0
        and height > 0
        and node.sizing.width
        and node.sizing.height
        and node.sizing.width > 0
        and node.sizing.height > 0
    ):
        box_aspect = width / height
        design_aspect = node.sizing.width / node.sizing.height
        if abs(box_aspect - design_aspect) > 0.12:
            return "BoxFit.contain"
    if (
        width
        and height
        and width <= _ICON_MAX_BOX_FIT_CONTAIN
        and height <= _ICON_MAX_BOX_FIT_CONTAIN
    ):
        return "BoxFit.contain"
    if (
        width
        and height
        and height <= _METRIC_STRIP_MAX_HEIGHT
        and width / height >= _METRIC_STRIP_MIN_ASPECT
    ):
        return "BoxFit.contain"
    if width and height and max(float(width), float(height)) <= 72.0:
        return "BoxFit.contain"
    return "BoxFit.fill" if width and height else "BoxFit.contain"


def stack_should_emit_flattened_vector_group(node: CleanDesignTreeNode) -> bool:
    """Emit a parent SVG export instead of empty color-only vector children."""
    if not node.children:
        return False
    if _compact_icon_glyph_group_should_preserve_child_vectors(node):
        return False
    if node.vector_svg_path_count is not None and node.vector_svg_path_count < 2:
        return False
    for child in node.children:
        if child.type != NodeType.VECTOR:
            return False
        if child.vector_asset_key:
            return False
    return True


def _compact_icon_glyph_group_should_preserve_child_vectors(
    node: CleanDesignTreeNode,
) -> bool:
    """Keep per-vector exports for square compact multi-glyph product icon slots."""
    if len(node.children) < 2:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    if not (22.0 <= float(width) <= 36.0 and 22.0 <= float(height) <= 36.0):
        return False
    if abs(float(width) - float(height)) > 2.0:
        return False
    vectors = [child for child in node.children if child.type == NodeType.VECTOR]
    return len(vectors) >= 2 and len(vectors) == len(node.children)


SVG_PATH_RASTER_THRESHOLD = 120


def _vector_needs_baked_raster(node: CleanDesignTreeNode) -> bool:
    """Return True when an exported vector should prefer a baked PNG raster (FID-46)."""
    if node.style.layer_blur or node.style.background_blur or node.vector_svg_has_filter:
        return True
    if node.style.has_stroke and node.style.stroke_dash_pattern:
        return True
    if (
        node.vector_svg_path_count is not None
        and node.vector_svg_path_count > SVG_PATH_RASTER_THRESHOLD
    ):
        return True
    return len(node.children) > 1 and node.vector_asset_key is None


def _wrap_raster_layer_blur(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply ``ImageFiltered`` bloom to baked raster exports that carry ``LAYER_BLUR``."""
    blur = node.style.layer_blur
    if blur is None or blur <= 0:
        return widget
    sigma = format_figma_blur_sigma_literal(blur)
    return (
        f"ImageFiltered("
        f"imageFilter: ImageFilter.blur(sigmaX: {sigma}, sigmaY: {sigma}), "
        f"child: {widget})"
    )


def _wrap_paint_overflow_export(
    node: CleanDesignTreeNode,
    asset_expr: str,
) -> str:
    """Clip expanded paint inside the true layout box via inner ``Positioned`` overflow."""
    from figma_flutter_agent.parser.render_bounds import (
        expanded_layout_dimensions,
        node_needs_render_bounds_expansion,
        paint_overflow_position_fields,
    )

    if not node_needs_render_bounds_expansion(node):
        return asset_expr
    raw_width, raw_height = _node_layout_size(node, node.stack_placement)
    if raw_width is None or raw_height is None or raw_width <= 0 or raw_height <= 0:
        return asset_expr
    _ZERO_BBOX_EPSILON = 0.25
    width_collapsed = raw_width <= _ZERO_BBOX_EPSILON
    height_collapsed = raw_height <= _ZERO_BBOX_EPSILON
    if not width_collapsed and not height_collapsed:
        return asset_expr
    expanded_width, expanded_height = expanded_layout_dimensions(
        node,
        raw_width,
        raw_height,
    )
    fields = paint_overflow_position_fields(
        node,
        expanded_width=expanded_width,
        expanded_height=expanded_height,
    )
    if not fields:
        return asset_expr
    width_lit = format_geometry_literal(raw_width)
    height_lit = format_geometry_literal(raw_height)
    return (
        f"SizedBox(width: {width_lit}, height: {height_lit}, child: Stack("
        "clipBehavior: Clip.none, children: ["
        f"Positioned({', '.join(fields)}, child: {asset_expr})]))"
    )


def _is_raster_asset_path(asset: str) -> bool:
    """Return True when an asset path refers to a raster bundle, not SVG."""
    return asset.lower().endswith(_RASTER_ASSET_SUFFIXES)


def _layout_slot_raster_emit_dimensions(
    node: CleanDesignTreeNode,
    layout_width: float | None,
    layout_height: float | None,
) -> tuple[float | None, float | None]:
    """Keep raster emit inside a bounded stack slot instead of paint-expanded bounds."""
    from figma_flutter_agent.parser.render_bounds import expanded_layout_dimensions

    expanded_width, expanded_height = expanded_layout_dimensions(node, layout_width, layout_height)
    placement = node.stack_placement
    sizing_width = node.sizing.width
    sizing_height = node.sizing.height
    if placement is None:
        if (
            sizing_width is not None
            and sizing_height is not None
            and float(sizing_width) > 0
            and float(sizing_height) > 0
            and expanded_width is not None
            and expanded_height is not None
            and (
                float(expanded_width) > float(sizing_width) + 0.5
                or float(expanded_height) > float(sizing_height) + 0.5
            )
        ):
            return layout_width, layout_height
        return expanded_width, expanded_height
    slot_width = placement.width
    slot_height = placement.height
    if (
        slot_width is None
        or slot_height is None
        or float(slot_width) <= 0
        or float(slot_height) <= 0
        or expanded_width is None
        or expanded_height is None
    ):
        return expanded_width, expanded_height
    if float(expanded_width) > float(slot_width) + 0.5 or float(
        expanded_height
    ) > float(slot_height) + 0.5:
        return layout_width, layout_height
    return expanded_width, expanded_height


def _render_raster_asset_picture(node: CleanDesignTreeNode, asset: str) -> str:
    """Render a raster asset with explicit bounds when Figma provides them."""
    from figma_flutter_agent.parser.render_bounds import (
        expanded_layout_dimensions,
        node_needs_render_bounds_expansion,
    )

    width, height = _node_layout_size(node, node.stack_placement)
    layout_width, layout_height = width, height
    width, height = _effective_svg_dimensions(node, width, height)
    layout_width, layout_height = width, height
    width, height = expanded_layout_dimensions(node, width, height)
    image_fit = "BoxFit.contain" if node_needs_render_bounds_expansion(node) else "BoxFit.cover"
    emit_width, emit_height = _layout_slot_raster_emit_dimensions(
        node,
        layout_width,
        layout_height,
    )
    params = [f"'{asset}'"]
    if emit_width is not None and emit_width > 0:
        params.append(f"width: {emit_width}")
    if emit_height is not None and emit_height > 0:
        params.append(f"height: {emit_height}")
    params.append(f"fit: {image_fit}")
    widget = f"Image.asset({', '.join(params)})"
    return _apply_node_transform(node, widget)


def _render_exported_vector(
    node: CleanDesignTreeNode,
    *,
    uses_svg: bool,
) -> str | None:
    """Render an exported vector asset per spec (SVG, or baked PNG for blur/filter)."""
    from figma_flutter_agent.parser.render_bounds import (
        expanded_layout_dimensions,
        node_needs_render_bounds_expansion,
    )

    width, height = _node_layout_size(node, node.stack_placement)
    layout_width, layout_height = width, height
    width, height = _effective_svg_dimensions(node, width, height)
    layout_width, layout_height = width, height
    width, height = expanded_layout_dimensions(node, width, height)
    image_fit = "BoxFit.contain" if node_needs_render_bounds_expansion(node) else "BoxFit.cover"

    if node.image_asset_key:
        asset = escape_dart_string(node.image_asset_key)
        if node.image_asset_key.lower().endswith(".svg"):
            asset_widget = _render_svg_picture(node, asset)
        else:
            emit_width, emit_height = _layout_slot_raster_emit_dimensions(
                node,
                layout_width,
                layout_height,
            )
            params = [f"'{asset}'"]
            if emit_width is not None and emit_width > 0:
                params.append(f"width: {emit_width}")
            if emit_height is not None and emit_height > 0:
                params.append(f"height: {emit_height}")
            params.append(f"fit: {image_fit}")
            asset_widget = f"Image.asset({', '.join(params)})"
        if node.style.layer_blur and float(node.style.layer_blur) > 0:
            asset_widget = _wrap_raster_layer_blur(node, asset_widget)
        return _wrap_paint_overflow_export(
            node,
            asset_widget,
        )

    if node.vector_asset_key and uses_svg and node.vector_asset_key.endswith(".svg"):
        return _wrap_paint_overflow_export(
            node,
            _render_svg_picture(node, escape_dart_string(node.vector_asset_key)),
        )

    if node.vector_asset_key and _is_raster_asset_path(node.vector_asset_key):
        return _wrap_paint_overflow_export(
            node,
            _render_raster_asset_picture(node, escape_dart_string(node.vector_asset_key)),
        )

    return None


def _should_prefer_exported_svg(node: CleanDesignTreeNode) -> bool:
    """Prefer baked SVG exports over native gradients when rotation or gradients differ."""
    if node.vector_asset_key is None:
        return False
    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        return True
    if node.render_boundary:
        from figma_flutter_agent.parser.interaction import find_raster_photo_leaf

        return not (node.children and find_raster_photo_leaf(node) is not None)
    if (
        not node.children
        and node.cluster_id
        and node.type in {NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
    ):
        return True
    if node.type != NodeType.CONTAINER:
        return False
    if node.style.gradient is not None:
        return True
    return _node_rotation_rad(node) is not None and abs(_node_rotation_rad(node) or 0.0) > 1e-3


def _is_roughly_square(width: float, height: float, *, max_size: float) -> bool:
    """Return True when a frame is square-ish and small enough to be an icon button."""
    if width <= 0 or height <= 0 or width > max_size or height > max_size:
        return False
    return abs(width - height) <= max(8.0, min(width, height) * 0.15)


def _composite_glyph_slot_count(parent_node: CleanDesignTreeNode) -> int:
    """Count absolute glyph slots layered inside a compact icon host."""
    count = 0
    for child in parent_node.children:
        if child.stack_placement is None:
            continue
        if (
            child.type == NodeType.VECTOR
            or child.type == NodeType.STACK
            and any(item.type == NodeType.VECTOR for item in child.children)
        ):
            count += 1
    return count


def _is_composite_icon_stack(parent_node: CleanDesignTreeNode) -> bool:
    """Return True when a small stack layers multiple absolute vectors (e.g. Google G)."""
    if parent_node.type != NodeType.STACK:
        return False
    if _composite_glyph_slot_count(parent_node) < 2:
        return False
    parent_width = parent_node.sizing.width
    parent_height = parent_node.sizing.height
    if parent_width is None or parent_height is None:
        return False
    return parent_width <= _ICON_BUTTON_MAX_SIZE and parent_height <= _ICON_BUTTON_MAX_SIZE


def _should_center_in_parent_stack(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> bool:
    """Detect icons and overlay numerals that should fill and center in a Stack parent."""
    if parent_node is None or parent_node.type != NodeType.STACK:
        return False
    if _is_composite_icon_stack(parent_node):
        return False
    if _is_skip_control_stack(parent_node):
        return False
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_stack_circular_option_glyph_host,
        layout_fact_stack_numeric_glyph_overlay_host,
    )

    if layout_fact_stack_numeric_glyph_overlay_host(parent_node):
        return False
    if layout_fact_stack_circular_option_glyph_host(parent_node):
        return False
    parent_width = parent_node.sizing.width
    parent_height = parent_node.sizing.height
    if parent_width is None or parent_height is None or parent_width <= 0 or parent_height <= 0:
        return False

    if node.type in {NodeType.VECTOR, NodeType.IMAGE}:
        node_width = node.sizing.width
        node_height = node.sizing.height
        if node_width is None or node_height is None:
            return False
        if node_width >= parent_width * 0.85 or node_height >= parent_height * 0.85:
            return False
        return _is_roughly_square(parent_width, parent_height, max_size=_ICON_BUTTON_MAX_SIZE)

    if node.type == NodeType.TEXT:
        from figma_flutter_agent.generator.layout.flex_policy.stack import (
            _is_compact_dimension_label,
            layout_fact_stack_circular_option_glyph_host,
        )

        if layout_fact_stack_circular_option_glyph_host(parent_node):
            return _is_compact_dimension_label(node.text or "")
        if not _is_roughly_square(parent_width, parent_height, max_size=_OVERLAY_TEXT_MAX_SIZE):
            return False
        text = (node.text or "").strip()
        return bool(text) and text.isdigit() and len(text) <= 4
    return False


def _clamp_centered_text_to_parent_stack(
    node: CleanDesignTreeNode,
    parent_node: CleanDesignTreeNode | None,
) -> CleanDesignTreeNode:
    """Cap centered labels to their parent stack width for absolute title rows."""
    from figma_flutter_agent.parser.numeric_rounding import round_geometry

    if (
        node.type != NodeType.TEXT
        or node.style.text_align != "CENTER"
        or parent_node is None
        or parent_node.type != NodeType.STACK
    ):
        return node
    parent_width = parent_node.sizing.width
    if parent_width is None or parent_width <= 0:
        return node
    placement = node.stack_placement
    if placement is None:
        return node
    cap = float(parent_width)
    current_width = placement.width if placement.width is not None else node.sizing.width
    if current_width is None or float(current_width) <= cap + 0.5:
        return node
    rounded = round_geometry(cap)
    return node.model_copy(
        update={
            "stack_placement": placement.model_copy(
                update={
                    "left": 0.0,
                    "right": 0.0,
                    "width": rounded,
                    "horizontal": "LEFT_RIGHT",
                },
            ),
            "sizing": node.sizing.model_copy(
                update={"width": cap, "width_mode": SizingMode.FIXED},
            ),
        },
    )


def _wrap_centered_stack_child(node: CleanDesignTreeNode, widget: str) -> str:
    """Center a child within a square Stack using optional glyph offset padding."""
    if node.type != NodeType.TEXT:
        return f"Center(child: {widget})"
    if len((node.text or node.name or "").strip()) <= 1:
        return f"Center(child: {widget})"
    glyph_offset = node.style.glyph_top_offset
    if glyph_offset is not None and glyph_offset > 0:
        padding_top = round(min(glyph_offset, 4.0), 1)
        return (
            "Center("
            f"child: Padding(padding: const EdgeInsets.only(top: {padding_top}), child: {widget})"
            ")"
        )
    return f"Center(child: {widget})"


_PI_ROTATION = 3.141592653589793
_TWO_PI = 2.0 * _PI_ROTATION
_COMPACT_NAV_ICON_MAX_PX = 32.0


def _node_rotation_rad(node: CleanDesignTreeNode) -> float | None:
    """Return rotation in radians for Flutter ``Transform.rotate`` emit."""
    if node.rotation_rad is not None:
        return node.rotation_rad
    if node.rotation is None:
        return None
    if abs(node.rotation) <= _TWO_PI + 0.01:
        return node.rotation
    return math.radians(node.rotation)


def _skip_redundant_pi_vector_rotation(node: CleanDesignTreeNode) -> bool:
    """Omit π rotations on compact vectors where SVG export already bakes orientation."""
    angle = _node_rotation_rad(node)
    if angle is None or abs(angle) < 1e-3:
        return False
    if abs(abs(angle) - _PI_ROTATION) >= 0.25:
        return False
    width = node.sizing.width
    height = node.sizing.height
    if width is None or height is None:
        return False
    return (
        width <= _COMPACT_NAV_ICON_MAX_PX
        and height <= _COMPACT_NAV_ICON_MAX_PX
        and bool(node.vector_asset_key)
    )


def _apply_node_transform(node: CleanDesignTreeNode, widget: str) -> str:
    """Apply Figma rotation/affine using Matrix4 when geometry planner attached (T1)."""
    slot = node.layout_slot
    transform = slot.residual_matrix if slot is not None else None
    if transform is not None and not requires_raster_tier(transform):
        prefix = matrix4_compose_expr(transform)
        if prefix is not None:
            return f"{prefix}{widget}{matrix4_close_suffix()}"
    angle_rad = _node_rotation_rad(node)
    if angle_rad is None or abs(angle_rad) < 1e-3:
        return widget
    if _skip_redundant_pi_vector_rotation(node):
        return widget
    angle = format_micro_style_literal(angle_rad)
    placement = node.stack_placement
    width = node.sizing.width or (placement.width if placement else None)
    height = node.sizing.height or (placement.height if placement else None)
    if width and height and width > 0 and height > 0:
        half_w = format_geometry_literal(width / 2.0)
        half_h = format_geometry_literal(height / 2.0)
        return (
            f"Transform.translate("
            f"offset: Offset({half_w}, {half_h}), "
            f"child: Transform.rotate(angle: {angle}, child: Transform.translate("
            f"offset: Offset(-{half_w}, -{half_h}), child: {widget})))"
        )
    return f"Transform.rotate(angle: {angle}, alignment: Alignment.center, child: {widget})"


_ICON_RAIL_GLYPH_SIZE = 20.0
_ICON_RAIL_FRAME_MIN = 40.0
_ICON_RAIL_FRAME_MAX = 56.0


def _intrinsic_glyph_svg_dimensions(
    node: CleanDesignTreeNode,
    width: float | None,
    height: float | None,
) -> tuple[float | None, float | None]:
    """Prefer vector intrinsic bounds when the layout host is materially larger."""
    from figma_flutter_agent.generator.ir.extracted_paint import (
        icon_badge_stack_intrinsic_glyph_size,
    )
    from figma_flutter_agent.generator.layout.flex_policy.stack import (
        layout_fact_icon_badge_stack,
    )
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_trailing_chevron_action_slot,
        trailing_chevron_glyph_paint_span,
    )

    if layout_fact_icon_badge_stack(node):
        glyph = icon_badge_stack_intrinsic_glyph_size(node)
        if glyph is not None:
            return glyph

    if layout_fact_trailing_chevron_action_slot(node):
        from figma_flutter_agent.parser.boundaries.assets import _best_descendant_vector_asset

        component_asset = node.vector_asset_key or _best_descendant_vector_asset(node)
        if component_asset and "chevron-right" in component_asset.lower().replace("_", "-"):
            if width is not None and height is not None and width > 0 and height > 0:
                return width, height
        glyph = trailing_chevron_glyph_paint_span(node)
        if glyph is not None:
            glyph_width, glyph_height = glyph
            if glyph_width > 0 and glyph_height > 0:
                return glyph_width, glyph_height
    node_width = node.sizing.width
    node_height = node.sizing.height
    if (
        width is not None
        and height is not None
        and node_width is not None
        and node_height is not None
        and float(node_width) > 0
        and float(node_height) > 0
        and float(node_width) < float(width) - 0.5
        and float(node_height) < float(height) - 0.5
    ):
        return float(node_width), float(node_height)
    frame = node.geometry_frame
    if frame is None or width is None or height is None:
        return width, height
    intrinsic_w = frame.intrinsic_size.width
    intrinsic_h = frame.intrinsic_size.height
    if intrinsic_w <= 0 or intrinsic_h <= 0:
        return width, height
    if intrinsic_w >= float(width) - 1.0 and intrinsic_h >= float(height) - 1.0:
        return width, height
    if (
        node_width is not None
        and node_height is not None
        and width is not None
        and height is not None
        and abs(float(node_width) - float(width)) <= 0.5
        and abs(float(node_height) - float(height)) <= 0.5
        and 20.0 <= float(node_width) <= _ICON_RAIL_FRAME_MAX
        and intrinsic_w < float(node_width) * 0.85
        and intrinsic_h < float(node_height) * 0.85
    ):
        return float(node_width), float(node_height)
    return float(intrinsic_w), float(intrinsic_h)


def _wrap_trailing_chevron_glyph_in_action_slot(
    node: CleanDesignTreeNode,
    widget: str,
    *,
    glyph_width: float,
    glyph_height: float,
    slot_width: float,
    slot_height: float,
) -> str:
    """Center a small chevron glyph inside its trailing list-row action slot."""
    if glyph_width >= slot_width - 0.5 and glyph_height >= slot_height - 0.5:
        return widget
    slot_w = format_geometry_literal(slot_width)
    slot_h = format_geometry_literal(slot_height)
    glyph_w = format_geometry_literal(glyph_width)
    glyph_h = format_geometry_literal(glyph_height)
    return (
        f"SizedBox(width: {slot_w}, height: {slot_h}, "
        f"child: Center(child: SizedBox(width: {glyph_w}, height: {glyph_h}, child: {widget})))"
    )


def _clamp_svg_dimensions_for_icon_rail(
    width: float | None,
    height: float | None,
) -> tuple[float | None, float | None]:
    """Shrink square SVG exports that fill an icon rail instead of the glyph box."""
    if width is None or height is None or width <= 0 or height <= 0:
        return width, height
    if abs(float(width) - float(height)) > 1.0:
        return width, height
    size = float(width)
    if _ICON_RAIL_FRAME_MIN <= size <= _ICON_RAIL_FRAME_MAX and size > _ICON_RAIL_GLYPH_SIZE + 2.0:
        return _ICON_RAIL_GLYPH_SIZE, _ICON_RAIL_GLYPH_SIZE
    return width, height


def _preserve_full_frame_svg_dimensions(node: CleanDesignTreeNode) -> bool:
    """Keep node bounds for full-frame compact icon exports (back, chevron-in-circle)."""
    from figma_flutter_agent.assets.composite_icons import (
        layout_fact_compact_vector_icon_export_node,
    )
    from figma_flutter_agent.parser.interaction import (
        is_back_navigation_icon_stack,
        layout_fact_back_nav_stack,
    )
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_trailing_chevron_action_slot,
    )

    if layout_fact_trailing_chevron_action_slot(node):
        return False

    if layout_fact_compact_vector_icon_export_node(node):
        return True
    if layout_fact_back_nav_stack(node) or is_back_navigation_icon_stack(node):
        return True
    if node.vector_asset_key and node.type == NodeType.STACK:
        width, height = _node_layout_size(node, node.stack_placement)
        if width is not None and height is not None and width > 0 and height > 0:
            if abs(float(width) - float(height)) <= 2.0:
                size = float(width)
                if _ICON_RAIL_FRAME_MIN <= size <= _ICON_RAIL_FRAME_MAX:
                    return True
    return False


def _render_svg_picture(node: CleanDesignTreeNode, asset: str) -> str:
    """Render a bundled SVG or raster asset with explicit bounds when Figma provides them."""
    from figma_flutter_agent.parser.interaction.icons import (
        layout_fact_trailing_chevron_action_slot,
    )

    if _is_raster_asset_path(asset):
        return _render_raster_asset_picture(node, asset)
    slot_width, slot_height = _node_layout_size(node, node.stack_placement)
    width, height = slot_width, slot_height
    width, height = _effective_svg_dimensions(node, width, height)
    if not _preserve_full_frame_svg_dimensions(node):
        width, height = _intrinsic_glyph_svg_dimensions(node, width, height)
        width, height = _clamp_svg_dimensions_for_icon_rail(width, height)
    params = [f"'{asset}'"]
    if width is not None and width > 0:
        params.append(f"width: {format_geometry_literal(float(width))}")
    if height is not None and height > 0:
        params.append(f"height: {format_geometry_literal(float(height))}")
    fit = _svg_fit_mode(node, width, height)
    params.append(f"fit: {fit}")
    widget = f"SvgPicture.asset({', '.join(params)})"
    if (
        layout_fact_trailing_chevron_action_slot(node)
        and slot_width is not None
        and slot_height is not None
        and width is not None
        and height is not None
        and slot_width > 0
        and slot_height > 0
    ):
        widget = _wrap_trailing_chevron_glyph_in_action_slot(
            node,
            widget,
            glyph_width=float(width),
            glyph_height=float(height),
            slot_width=float(slot_width),
            slot_height=float(slot_height),
        )
    return _apply_node_transform(node, widget)
