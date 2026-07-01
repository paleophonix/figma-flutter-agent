"""Clean design tree schema models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from figma_flutter_agent.schemas.geometry import (
    Alignment,
    GeometryFrame,
    LayoutSlotIr,
    Padding,
    Sizing,
    StackPlacement,
    TextMetricsFrame,
)
from figma_flutter_agent.schemas.style import ComponentVariant, NodeStyle, TextSpanPart
from figma_flutter_agent.schemas.types import NodeType, ScrollAxis


class CleanDesignTreeNode(BaseModel):
    """Intermediate design tree consumed by the LLM."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    type: NodeType
    padding: Padding = Field(default_factory=Padding)
    spacing: float = 0
    sizing: Sizing = Field(default_factory=Sizing)
    alignment: Alignment = Field(default_factory=Alignment)
    style: NodeStyle = Field(default_factory=NodeStyle)
    text: str | None = None
    text_spans: list[TextSpanPart] = Field(default_factory=list, alias="textSpans")
    vector_asset_key: str | None = Field(default=None, alias="vectorAssetKey")
    vector_svg_has_filter: bool = Field(default=False, alias="vectorSvgHasFilter")
    vector_svg_path_count: int | None = Field(default=None, alias="vectorSvgPathCount")
    rotation: float | None = None
    rotation_rad: float | None = Field(default=None, alias="rotationRad")
    image_asset_key: str | None = Field(default=None, alias="imageAssetKey")
    component_ref: str | None = Field(default=None, alias="componentRef")
    cluster_id: str | None = Field(default=None, alias="clusterId")
    shape_cluster_id: str | None = Field(default=None, alias="shapeClusterId")
    accessibility_label: str | None = Field(default=None, alias="accessibilityLabel")
    accessibility_hint: str | None = Field(default=None, alias="accessibilityHint")
    variant: ComponentVariant | None = None
    layout_positioning: str = Field(default="AUTO", alias="layoutPositioning")
    offset_x: float = Field(default=0, alias="offsetX")
    offset_y: float = Field(default=0, alias="offsetY")
    stack_placement: StackPlacement | None = Field(default=None, alias="stackPlacement")
    scroll_axis: ScrollAxis = Field(default="none", alias="scrollAxis")
    grid_column_count: int | None = Field(default=None, alias="gridColumnCount")
    grid_row_gap: float | None = Field(default=None, alias="gridRowGap")
    grid_column_gap: float | None = Field(default=None, alias="gridColumnGap")
    children: list[CleanDesignTreeNode] = Field(default_factory=list)
    extracted_widget_ref: str | None = Field(default=None, alias="extractedWidgetRef")
    nested_scroll_constraints: bool = Field(default=False, alias="nestedScrollConstraints")
    min_touch_target: float | None = Field(default=None, alias="minTouchTarget")
    render_boundary: bool = Field(default=False, alias="renderBoundary")
    flatten_figma_node_ids: list[str] | None = Field(default=None, alias="flattenFigmaNodeIds")
    geometry_frame: GeometryFrame | None = Field(default=None, alias="geometryFrame")
    text_metrics_frame: TextMetricsFrame | None = Field(default=None, alias="textMetricsFrame")
    layout_slot: LayoutSlotIr | None = Field(default=None, alias="layoutSlot")
    flex_gap_mode: Literal["uniform", "explicit"] | None = Field(
        default=None,
        alias="flexGapMode",
    )
    flex_explicit_gaps: list[float] | None = Field(default=None, alias="flexExplicitGaps")
    layout_role: str | None = Field(default=None, alias="layoutRole")
