"""Screen IR schema models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WidgetIrKind(StrEnum):
    """Flutter widget role in screen IR."""

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
    text_color: str | None = Field(default=None, alias="textColor")
    background_color: str | None = Field(default=None, alias="backgroundColor")
    font_size: float | None = Field(default=None, alias="fontSize")


class WidgetIrState(StrEnum):
    """Figma component state mirrored in screen IR."""

    DEFAULT = "default"
    DISABLED = "disabled"
    LOADING = "loading"
    SELECTED = "selected"
    ERROR = "error"


class AdaptiveRuleWhen(BaseModel):
    """Condition for an adaptive IR rule."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    state: WidgetIrState | None = None
    min_viewport_width: float | None = Field(default=None, alias="minViewportWidth")
    max_viewport_width: float | None = Field(default=None, alias="maxViewportWidth")
    variant_property: str | None = Field(default=None, alias="variantProperty")
    variant_value: str | None = Field(default=None, alias="variantValue")


class AdaptiveRule(BaseModel):
    """Apply IR overrides when ``when`` matches runtime/design context."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    figma_id: str = Field(alias="figmaId")
    when: AdaptiveRuleWhen
    overrides: WidgetIrOverrides | None = None
    wrap: FlexWrapIr | None = None


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
    state_by_figma_id: dict[str, WidgetIrState] = Field(default_factory=dict, alias="stateByFigmaId")
    adaptive_rules: list[AdaptiveRule] = Field(default_factory=list, alias="adaptiveRules")
