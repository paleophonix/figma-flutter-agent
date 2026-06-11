"""Geometry schema models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from figma_flutter_agent.schemas.types import (
    IMMUTABLE_TREE_CONFIG,
    HorizontalConstraint,
    SizingMode,
    VerticalConstraint,
)


class Padding(BaseModel):
    """Padding values in logical pixels."""

    model_config = IMMUTABLE_TREE_CONFIG

    top: float = 0
    bottom: float = 0
    left: float = 0
    right: float = 0


class StackPlacement(BaseModel):
    """Classic Figma frame constraints mapped to Stack/Positioned edges."""

    model_config = IMMUTABLE_TREE_CONFIG

    horizontal: HorizontalConstraint = "LEFT"
    vertical: VerticalConstraint = "TOP"
    left: float = 0
    top: float = 0
    right: float = 0
    bottom: float = 0
    width: float | None = None
    height: float | None = None


class Sizing(BaseModel):
    """Width and height sizing metadata."""

    model_config = IMMUTABLE_TREE_CONFIG

    width_mode: SizingMode = Field(default=SizingMode.HUG, alias="widthMode")
    height_mode: SizingMode = Field(default=SizingMode.HUG, alias="heightMode")
    width: float | None = None
    height: float | None = None
    min_width: float | None = Field(default=None, alias="minWidth")
    max_width: float | None = Field(default=None, alias="maxWidth")
    min_height: float | None = Field(default=None, alias="minHeight")
    max_height: float | None = Field(default=None, alias="maxHeight")


class Alignment(BaseModel):
    """Main and cross axis alignment."""

    model_config = IMMUTABLE_TREE_CONFIG

    main: Literal["start", "end", "center", "spaceBetween", "stretch", "baseline"] = "start"
    cross: Literal["start", "end", "center", "spaceBetween", "stretch", "baseline"] = "start"


class Affine2(BaseModel):
    """2x3 affine transform."""

    model_config = IMMUTABLE_TREE_CONFIG

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    tx: float = 0.0
    ty: float = 0.0


class GeomRect(BaseModel):
    """Axis-aligned rectangle in logical pixels."""

    model_config = IMMUTABLE_TREE_CONFIG

    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0


class GeometryFrame(BaseModel):
    """World-space geometry contract for translation-theory invariants."""

    model_config = IMMUTABLE_TREE_CONFIG

    local_transform: Affine2 = Field(default_factory=Affine2, alias="localTransform")
    world_transform: Affine2 | None = Field(default=None, alias="worldTransform")
    layout_rect: GeomRect = Field(default_factory=GeomRect, alias="layoutRect")
    intrinsic_size: GeomRect = Field(default_factory=GeomRect, alias="intrinsicSize")
    placement_origin: GeomRect | None = Field(default=None, alias="placementOrigin")
    placement_aabb: GeomRect | None = Field(default=None, alias="placementAabb")
    parsed_world_aabb: GeomRect | None = Field(default=None, alias="parsedWorldAabb")
    world_aabb: GeomRect = Field(default_factory=GeomRect, alias="worldAabb")
    paint_rect: GeomRect | None = Field(default=None, alias="paintRect")


class TextMetricsFrame(BaseModel):
    """Typography line-box metrics for baseline gravity."""

    model_config = IMMUTABLE_TREE_CONFIG

    line_height_px: float | None = Field(default=None, alias="lineHeightPx")
    glyph_top_offset: float | None = Field(default=None, alias="glyphTopOffset")
    glyph_height: float | None = Field(default=None, alias="glyphHeight")
    font_size: float | None = Field(default=None, alias="fontSize")
    leading_above_flutter: float | None = Field(default=None, alias="leadingAboveFlutter")
    predicted_baseline: float | None = Field(default=None, alias="predictedBaseline")
    delta_top: float | None = None
    input_padding_top: float | None = Field(default=None, alias="inputPaddingTop")
    input_padding_bottom: float | None = Field(default=None, alias="inputPaddingBottom")
    strut_height_ratio: float | None = Field(default=None, alias="strutHeightRatio")
    baseline_verifiable: bool = Field(default=False, alias="baselineVerifiable")


class LayoutBackend(StrEnum):
    """Resolved layout backend from geometry planning."""

    STACK = "stack"
    FLEX = "flex"
    BOUNDARY = "boundary"
    SCROLL = "scroll"


class LayerClass(StrEnum):
    """Paint/repaint partition class."""

    STATIC = "static"
    INTERACTIVE = "interactive"
    ANIMATED = "animated"


class WrapKind(StrEnum):
    """Emit wrappers authorized by geometry planning."""

    REPAINT_BOUNDARY = "repaint_boundary"
    EXPANDED = "expanded"
    FLEXIBLE_LOOSE = "flexible_loose"
    CONSTRAINED_BOX = "constrained_box"
    DELTA_TOP_PADDING = "delta_top_padding"
    CROSS_STRETCH_WIDTH = "cross_stretch_width"
    CROSS_STRETCH_HEIGHT = "cross_stretch_height"


class HeightFit(StrEnum):
    """Elastic height constraint mode for TEXT/INPUT emit."""

    FIXED = "fixed"
    MIN = "min"
    INTRINSIC = "intrinsic"


class AxisPins(BaseModel):
    """Positioned pin law: at most one free coordinate per axis."""

    model_config = IMMUTABLE_TREE_CONFIG

    free_horizontal: Literal["left", "right", "width"] | None = Field(
        default=None, alias="freeHorizontal"
    )
    free_vertical: Literal["top", "bottom", "height"] | None = Field(
        default=None, alias="freeVertical"
    )
    left: float | None = None
    top: float | None = None
    right: float | None = None
    bottom: float | None = None
    width: float | None = None
    height: float | None = None


class FlexSolution(BaseModel):
    """Documented flex feasibility outcome when backend is FLEX."""

    model_config = IMMUTABLE_TREE_CONFIG

    main_axis: Literal["horizontal", "vertical"] = Field(alias="mainAxis")
    residual_max_px: float = Field(default=0.0, alias="residualMaxPx")
    wraps: tuple[WrapKind, ...] = Field(default_factory=tuple)


class LayoutSlotIr(BaseModel):
    """Geometry planning output consumed by emit."""

    model_config = IMMUTABLE_TREE_CONFIG

    backend: LayoutBackend = LayoutBackend.STACK
    slot_rect: GeomRect = Field(default_factory=GeomRect, alias="slotRect")
    positioned_pins: AxisPins | None = Field(default=None, alias="positionedPins")
    flex_solution: FlexSolution | None = Field(default=None, alias="flexSolution")
    residual_matrix: Affine2 | None = Field(default=None, alias="residualMatrix")
    layer_class: LayerClass = LayerClass.STATIC
    z_index: int = Field(default=0, alias="zIndex")
    wraps: tuple[WrapKind, ...] = Field(default_factory=tuple)
    min_height: float | None = Field(default=None, alias="minHeight")
    max_height: float | None = Field(default=None, alias="maxHeight")
    height_fit: HeightFit | None = Field(default=None, alias="heightFit")
    degraded: bool = Field(default=False)


class CascadeContext(BaseModel):
    """Unified world/local cascade channel for geometry planning."""

    model_config = IMMUTABLE_TREE_CONFIG

    world: Affine2 = Field(default_factory=Affine2)
    local: Affine2 = Field(default_factory=Affine2)
    pivot_x: float = Field(default=0.0, alias="pivotX")
    pivot_y: float = Field(default=0.0, alias="pivotY")
    intrinsic_size: GeomRect = Field(default_factory=GeomRect, alias="intrinsicSize")
