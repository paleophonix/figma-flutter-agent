"""Shared schema models for parser, LLM, and generator stages."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ScrollAxis = Literal["none", "vertical", "horizontal", "both"]
HorizontalConstraint = Literal["LEFT", "RIGHT", "CENTER", "LEFT_RIGHT", "SCALE"]
VerticalConstraint = Literal["TOP", "BOTTOM", "CENTER", "TOP_BOTTOM", "SCALE"]


class NodeType(StrEnum):
    """Semantic node types for the clean design tree."""

    COLUMN = "COLUMN"
    ROW = "ROW"
    WRAP = "WRAP"
    STACK = "STACK"
    GRID = "GRID"
    TEXT = "TEXT"
    IMAGE = "IMAGE"
    VECTOR = "VECTOR"
    INPUT = "INPUT"
    BUTTON = "BUTTON"
    CHECKBOX = "CHECKBOX"
    SWITCH = "SWITCH"
    RADIO = "RADIO"
    RADIO_GROUP = "RADIO_GROUP"
    DROPDOWN = "DROPDOWN"
    DIALOG = "DIALOG"
    SLIDER = "SLIDER"
    CAROUSEL = "CAROUSEL"
    TABS = "TABS"
    BOTTOM_NAV = "BOTTOM_NAV"
    CARD = "CARD"
    CONTAINER = "CONTAINER"


class SizingMode(StrEnum):
    """Sizing behavior for a node."""

    FIXED = "FIXED"
    HUG = "HUG"
    FILL = "FILL"


class Padding(BaseModel):
    """Padding values in logical pixels."""

    model_config = ConfigDict(extra="forbid")

    top: float = 0
    bottom: float = 0
    left: float = 0
    right: float = 0


class StackPlacement(BaseModel):
    """Classic Figma frame constraints mapped to Stack/Positioned edges."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    width_mode: SizingMode = Field(default=SizingMode.HUG, alias="widthMode")
    height_mode: SizingMode = Field(default=SizingMode.HUG, alias="heightMode")
    width: float | None = None
    height: float | None = None


class Alignment(BaseModel):
    """Main and cross axis alignment."""

    model_config = ConfigDict(extra="forbid")

    main: Literal["start", "end", "center", "spaceBetween", "stretch", "baseline"] = "start"
    cross: Literal["start", "end", "center", "spaceBetween", "stretch", "baseline"] = "start"


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
    is_link: bool = Field(default=False, alias="isLink")


class NodeStyle(BaseModel):
    """Visual style attributes used by codegen."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    background_color: str | None = Field(default=None, alias="backgroundColor")
    border_radius: float | None = Field(default=None, alias="borderRadius")
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
    has_stroke: bool = Field(default=False, alias="hasStroke")
    css_properties: dict[str, str] = Field(default_factory=dict, alias="cssProperties")


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
    rotation: float | None = None
    image_asset_key: str | None = Field(default=None, alias="imageAssetKey")
    component_ref: str | None = Field(default=None, alias="componentRef")
    cluster_id: str | None = Field(default=None, alias="clusterId")
    accessibility_label: str | None = Field(default=None, alias="accessibilityLabel")
    accessibility_hint: str | None = Field(default=None, alias="accessibilityHint")
    variant: ComponentVariant | None = None
    layout_positioning: Literal["AUTO", "ABSOLUTE"] = Field(
        default="AUTO", alias="layoutPositioning"
    )
    offset_x: float = Field(default=0, alias="offsetX")
    offset_y: float = Field(default=0, alias="offsetY")
    stack_placement: StackPlacement | None = Field(default=None, alias="stackPlacement")
    scroll_axis: ScrollAxis = Field(default="none", alias="scrollAxis")
    grid_column_count: int | None = Field(default=None, alias="gridColumnCount")
    grid_row_gap: float | None = Field(default=None, alias="gridRowGap")
    grid_column_gap: float | None = Field(default=None, alias="gridColumnGap")
    children: list[CleanDesignTreeNode] = Field(default_factory=list)
    extracted_widget_ref: str | None = Field(
        default=None,
        alias="extractedWidgetRef",
    )


class TypographyStyle(BaseModel):
    """Typography values keyed by style name in ``DesignTokens.typography``."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    font_size: float = Field(alias="fontSize")
    font_weight: str = Field(default="w400", alias="fontWeight")


# Backward-compatible alias for tests and imports.
TypographyToken = TypographyStyle


class DesignTokens(BaseModel):
    """Design tokens extracted from Figma (flat maps for LLM-efficient JSON)."""

    model_config = ConfigDict(extra="forbid")

    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, TypographyStyle] = Field(default_factory=dict)
    spacing: dict[str, float] = Field(default_factory=dict)
    radii: dict[str, float] = Field(default_factory=dict)
    elevations: dict[str, float] = Field(default_factory=dict)


class WidgetIrKind(StrEnum):
    """Flutter widget role in screen IR (AUTO reads ``CleanDesignTreeNode.type``)."""

    AUTO = "auto"
    COLUMN = "column"
    ROW = "row"
    STACK = "stack"
    TEXT = "text"
    IMAGE = "image"
    BUTTON = "button"
    INPUT = "input"
    CONTAINER = "container"
    EXTRACTED = "extracted"


class FlexWrapIr(StrEnum):
    """Flex wrapper hint for the Dart emitter."""

    NONE = "none"
    EXPANDED = "expanded"
    FLEXIBLE_LOOSE = "flexibleLoose"
    SIZED_BOX_WIDTH = "sizedBoxWidth"


WidgetIrArgValue = str | int | float | bool | None


class WidgetIrRef(BaseModel):
    """Reference to an extracted widget class."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    widget_name: str = Field(alias="widgetName")
    named_args: dict[str, WidgetIrArgValue] = Field(default_factory=dict, alias="namedArgs")


class WidgetIrOverrides(BaseModel):
    """Sparse overrides merged onto the clean tree node before codegen."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    text: str | None = None
    accessibility_label: str | None = Field(default=None, alias="accessibilityLabel")


class WidgetIrNode(BaseModel):
    """One node in the LLM screen intermediate representation."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    figma_id: str = Field(alias="figmaId")
    kind: WidgetIrKind = WidgetIrKind.AUTO
    children: list[WidgetIrNode] = Field(default_factory=list)
    ref: WidgetIrRef | None = None
    overrides: WidgetIrOverrides | None = None
    wrap: FlexWrapIr | None = None


class ScreenIr(BaseModel):
    """Screen body structure keyed by Figma node ids."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    root: WidgetIrNode
    omit_figma_ids: list[str] = Field(default_factory=list, alias="omitFigmaIds")
    stack_child_order: list[str] | None = Field(default=None, alias="stackChildOrder")


class ExtractedWidget(BaseModel):
    """Reusable widget generated by the LLM (Dart source and/or IR subtree)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    widget_name: str = Field(alias="widgetName")
    code: str | None = None
    widget_ir: WidgetIrNode | None = Field(default=None, alias="widgetIr")

    @model_validator(mode="after")
    def _require_widget_payload(self) -> ExtractedWidget:
        has_ir = self.widget_ir is not None
        has_code = bool((self.code or "").strip())
        if not has_ir and not has_code:
            msg = "ExtractedWidget requires widgetIr or code"
            raise ValueError(msg)
        return self

    def resolved_code(self) -> str:
        """Return Dart widget class source when already materialized."""
        return (self.code or "").strip()


class FlutterGenerationResponse(BaseModel):
    """Structured LLM output for Dart generation."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    screen_code: str | None = Field(default=None, alias="screenCode")
    screen_ir: ScreenIr | None = Field(default=None, alias="screenIr")
    extracted_widgets: list[ExtractedWidget] = Field(default_factory=list, alias="extractedWidgets")

    @model_validator(mode="after")
    def _require_screen_payload(self) -> FlutterGenerationResponse:
        has_ir = self.screen_ir is not None
        has_code = bool((self.screen_code or "").strip())
        if not has_ir and not has_code:
            msg = "FlutterGenerationResponse requires screenIr or screenCode"
            raise ValueError(msg)
        return self

    def resolved_screen_code(self) -> str:
        """Return legacy screen Dart when present (call ``materialize_screen_code_from_ir`` for IR)."""
        return (self.screen_code or "").strip()


class FlutterRepairPatch(BaseModel):
    """One scoped Dart repair patch for analyze failures."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    target: Literal["screenCode", "extractedWidget"]
    widget_name: str | None = Field(default=None, alias="widgetName")
    code: str


class FlutterRepairIrPatch(BaseModel):
    """Structured screen IR patch (no Dart syntax)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    figma_id: str = Field(alias="figmaId")
    replace_subtree: WidgetIrNode | None = Field(default=None, alias="replaceSubtree")
    overrides: WidgetIrOverrides | None = None
    reorder_children: list[str] | None = Field(default=None, alias="reorderChildren")


class FlutterRepairPatchResponse(BaseModel):
    """Structured LLM output for scoped analyze repair."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    patches: list[FlutterRepairPatch] = Field(default_factory=list)
    ir_patches: list[FlutterRepairIrPatch] = Field(default_factory=list, alias="irPatches")


class RepairCpiSupervisorResponse(BaseModel):
    """Metacognitive interrupt when analyze repair stagnates on identical errors."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    analysis: str
    pattern_interrupt_directive: str = Field(alias="patternInterruptDirective")


class AssetManifestEntry(BaseModel):
    """Exported asset metadata."""

    model_config = ConfigDict(extra="forbid")

    node_id: str
    asset_path: str
    kind: Literal["icon", "image", "illustration"]
    svg_has_filter: bool = False


class AssetManifest(BaseModel):
    """Collection of exported assets."""

    model_config = ConfigDict(extra="forbid")

    entries: list[AssetManifestEntry] = Field(default_factory=list)


class FontFaceRequirement(BaseModel):
    """Unique font face referenced by generated TEXT nodes."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    figma_family: str
    font_weight: str = Field(default="w400", alias="fontWeight")
    font_style: str | None = Field(default=None, alias="fontStyle")


class FontPubspecAsset(BaseModel):
    """Single font asset entry for pubspec.yaml."""

    model_config = ConfigDict(extra="forbid")

    asset: str
    weight: int
    style: str | None = None


class FontPubspecFamily(BaseModel):
    """Font family block for pubspec.yaml."""

    model_config = ConfigDict(extra="forbid")

    family: str
    fonts: list[FontPubspecAsset] = Field(default_factory=list)


class FontManifest(BaseModel):
    """Bundled fonts exported for a generation run."""

    model_config = ConfigDict(extra="forbid")

    families: list[FontPubspecFamily] = Field(default_factory=list)
    bundled_family_names: list[str] = Field(default_factory=list)
    family_aliases: dict[str, str] = Field(default_factory=dict)
    dart_weight_overrides_by_family: dict[str, dict[str, str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def merge_asset_manifests(base: AssetManifest, extra: AssetManifest) -> AssetManifest:
    """Merge exported assets without duplicating node ids.

    Args:
        base: Manifest that receives new entries.
        extra: Manifest whose entries are appended when unique.

    Returns:
        The updated base manifest.
    """
    seen = {entry.node_id for entry in base.entries}
    for entry in extra.entries:
        if entry.node_id in seen:
            continue
        base.entries.append(entry)
        seen.add(entry.node_id)
    return base
