"""Visual style schema models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from figma_flutter_agent.schemas.geometry import Padding


class ShadowEffect(BaseModel):
    """Drop or inner shadow extracted from Figma effects."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    kind: Literal["drop", "inner"] = "drop"
    offset_x: float = Field(default=0, alias="offsetX")
    offset_y: float = Field(default=0, alias="offsetY")
    blur: float = 0
    spread: float = 0
    color: str


class GradientStop(BaseModel):
    """Single stop in a gradient fill."""

    model_config = ConfigDict(extra="forbid")

    position: float
    color: str


class GradientFill(BaseModel):
    """Linear or radial gradient fill."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    type: Literal["linear", "radial"]
    stops: list[GradientStop] = Field(default_factory=list)
    angle: float | None = None


class ComponentVariant(BaseModel):
    """Component instance variant and state metadata."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    component_id: str | None = Field(default=None, alias="componentId")
    component_set_id: str | None = Field(default=None, alias="componentSetId")
    component_name: str | None = Field(default=None, alias="componentName")
    variant_properties: dict[str, str] = Field(default_factory=dict, alias="variantProperties")
    state: str | None = None


class TextSpanPart(BaseModel):
    """Single styled run inside a Figma TEXT node with mixed styles."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    text: str
    text_color: str | None = Field(default=None, alias="textColor")
    font_weight: str | None = Field(default=None, alias="fontWeight")
    letter_spacing: float | None = Field(default=None, alias="letterSpacing")
    text_decoration: str | None = Field(default=None, alias="textDecoration")
    is_link: bool = Field(default=False, alias="isLink")


class CornerRadii(BaseModel):
    """Per-corner border radii."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    top_left: float = Field(alias="topLeft")
    top_right: float = Field(alias="topRight")
    bottom_right: float = Field(alias="bottomRight")
    bottom_left: float = Field(alias="bottomLeft")


class NodeStyle(BaseModel):
    """Visual style attributes used by codegen."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    background_color: str | None = Field(default=None, alias="backgroundColor")
    border_radius: float | None = Field(default=None, alias="borderRadius")
    border_radius_corners: CornerRadii | None = Field(default=None, alias="borderRadiusCorners")
    stroke_align: str | None = Field(default=None, alias="strokeAlign")
    stroke_dash_pattern: list[float] = Field(default_factory=list, alias="strokeDashPattern")
    text_color: str | None = Field(default=None, alias="textColor")
    font_size: float | None = Field(default=None, alias="fontSize")
    font_weight: str | None = Field(default=None, alias="fontWeight")
    text_align: str | None = Field(default=None, alias="textAlign")
    line_height: float | None = Field(default=None, alias="lineHeight")
    letter_spacing: float | None = Field(default=None, alias="letterSpacing")
    font_family: str | None = Field(default=None, alias="fontFamily")
    font_style: str | None = Field(default=None, alias="fontStyle")
    glyph_top_offset: float | None = Field(default=None, alias="glyphTopOffset")
    glyph_height: float | None = Field(default=None, alias="glyphHeight")
    border_width: float | None = Field(default=None, alias="borderWidth")
    border_color: str | None = Field(default=None, alias="borderColor")
    opacity: float | None = None
    elevation: float | None = None
    style_name: str | None = Field(default=None, alias="styleName")
    effects: list[ShadowEffect] = Field(default_factory=list)
    gradient: GradientFill | None = None
    layer_blur: float | None = Field(default=None, alias="layerBlur")
    background_blur: float | None = Field(default=None, alias="backgroundBlur")
    render_bounds_expand: Padding | None = Field(default=None, alias="renderBoundsExpand")
    has_stroke: bool = Field(default=False, alias="hasStroke")
    blend_mode: str | None = Field(default=None, alias="blendMode")
    css_properties: dict[str, str] = Field(default_factory=dict, alias="cssProperties")
