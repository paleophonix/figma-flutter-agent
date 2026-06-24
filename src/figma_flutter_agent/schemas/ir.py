"""Screen IR schema models."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from figma_flutter_agent.schemas.ir_payloads import KindPayload, LlmClassificationHint

SemanticScalar = str | int | float | bool


class WidgetIrKind(StrEnum):
    """Flutter widget role in screen IR."""

    AUTO = "auto"
    COLUMN = "column"
    ROW = "row"
    WRAP = "wrap"
    STACK = "stack"
    TEXT = "text"
    IMAGE = "image"
    BUTTON = "button"
    INPUT = "input"
    CONTAINER = "container"
    EXTRACTED = "extracted"
    # Phase 1 MVP semantic kinds
    INPUT_TEXT_FIELD = "input_text_field"
    BUTTON_FILLED = "button_filled"
    CHIP_CHOICE = "chip_choice"
    CONTAINER_CARD = "container_card"
    CONTAINER_LIST_TILE = "container_list_tile"
    NAV_SCROLL_HOST = "nav_scroll_host"
    TECHNICAL_DIVIDER = "technical_divider"
    # Backlog stubs (enum only; no emit in Phase 1)
    INPUT_SEARCH_BAR = "input_search_bar"
    INPUT_DROPDOWN = "input_dropdown"
    INPUT_PICKER_DATE = "input_picker_date"
    INPUT_PICKER_TIME = "input_picker_time"
    INPUT_STEPPER = "input_stepper"
    INPUT_SLIDER = "input_slider"
    INPUT_RATING = "input_rating"
    INPUT_FILE_UPLOADER = "input_file_uploader"
    BUTTON_OUTLINED = "button_outlined"
    BUTTON_TEXT = "button_text"
    BUTTON_FAB = "button_fab"
    BUTTON_ICON = "button_icon"
    CHIP_FILTER = "chip_filter"
    CHIP_INPUT = "chip_input"
    CHIP_ACTION = "chip_action"
    CONTROL_CHECKBOX = "control_checkbox"
    CONTROL_RADIO = "control_radio"
    CONTROL_SWITCH = "control_switch"
    CONTROL_SEGMENTED = "control_segmented"
    NAV_APP_BAR = "nav_app_bar"
    NAV_BOTTOM_BAR = "nav_bottom_bar"
    NAV_TAB_BAR = "nav_tab_bar"
    NAV_DRAWER = "nav_drawer"
    NAV_STEPPER = "nav_stepper"
    NAV_PAGINATION = "nav_pagination"
    CONTAINER_GRID = "container_grid"
    CONTAINER_CAROUSEL = "container_carousel"
    CONTAINER_ACCORDION = "container_accordion"
    MEDIA_AVATAR = "media_avatar"
    MEDIA_BADGE = "media_badge"
    OVERLAY_DIALOG = "overlay_dialog"
    OVERLAY_BOTTOM_SHEET = "overlay_bottom_sheet"
    OVERLAY_SNACKBAR = "overlay_snackbar"
    OVERLAY_BANNER = "overlay_banner"
    FEEDBACK_LOADER = "feedback_loader"
    FEEDBACK_SKELETON = "feedback_skeleton"
    FEEDBACK_TOOLTIP = "feedback_tooltip"


SEMANTIC_MVP_IR_KINDS: frozenset[WidgetIrKind] = frozenset(
    {
        WidgetIrKind.INPUT_TEXT_FIELD,
        WidgetIrKind.BUTTON_FILLED,
        WidgetIrKind.BUTTON_OUTLINED,
        WidgetIrKind.BUTTON_TEXT,
        WidgetIrKind.CHIP_CHOICE,
        WidgetIrKind.CONTAINER_CARD,
        WidgetIrKind.CONTAINER_LIST_TILE,
        WidgetIrKind.NAV_SCROLL_HOST,
        WidgetIrKind.TECHNICAL_DIVIDER,
    }
)

STUB_IR_KINDS: frozenset[WidgetIrKind] = frozenset(
    kind
    for kind in WidgetIrKind
    if kind not in SEMANTIC_MVP_IR_KINDS
    and kind
    not in {
        WidgetIrKind.AUTO,
        WidgetIrKind.COLUMN,
        WidgetIrKind.ROW,
        WidgetIrKind.WRAP,
        WidgetIrKind.STACK,
        WidgetIrKind.TEXT,
        WidgetIrKind.IMAGE,
        WidgetIrKind.BUTTON,
        WidgetIrKind.INPUT,
        WidgetIrKind.CONTAINER,
        WidgetIrKind.EXTRACTED,
    }
)


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


class WidgetIrLayoutHints(BaseModel):
    """Layout metadata produced by IR passes and consumed by emit."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    flex_spacing: float | None = Field(default=None, alias="flexSpacing")
    scroll_axis: str | None = Field(default=None, alias="scrollAxis")
    gap_mode: Literal["uniform", "explicit"] | None = Field(default=None, alias="gapMode")
    explicit_gaps: list[float] | None = Field(default=None, alias="explicitGaps")
    min_height: float | None = Field(default=None, alias="minHeight")
    height_fit: str | None = Field(default=None, alias="heightFit")


class FidelityTier(StrEnum):
    """Per-node render fidelity authority for semantic emit (EPIC 3)."""

    NATIVE_VERIFIED = "native_verified"
    NATIVE_UNVERIFIED = "native_unverified"
    STYLED_PRIMITIVE = "styled_primitive"
    SVG_BAKED = "svg_baked"
    PNG_BAKED = "png_baked"
    UNSUPPORTED = "unsupported"


class TierSource(StrEnum):
    """Provenance for how a node's fidelity tier was assigned (EPIC 4.5)."""

    MANIFEST = "manifest"
    POLICY_FALLBACK = "policy_fallback"
    MANUAL_OVERRIDE = "manual_override"
    RUNTIME_SIGNOFF = "runtime_signoff"


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
    layout_hints: WidgetIrLayoutHints | None = Field(default=None, alias="layoutHints")
    is_selected: bool | None = Field(default=None, alias="isSelected")
    hint_text: str | None = Field(default=None, alias="hintText")
    error_text: str | None = Field(default=None, alias="errorText")
    is_multiline: bool | None = Field(default=None, alias="isMultiline")
    max_lines: int | None = Field(default=None, alias="maxLines")
    payload: KindPayload | None = None
    classification_hint: LlmClassificationHint | None = Field(
        default=None,
        alias="classificationHint",
    )
    fidelity_tier: FidelityTier | None = Field(default=None, alias="fidelityTier")
    tier_source: TierSource | None = Field(default=None, alias="tierSource")

    @model_validator(mode="after")
    def validate_kind_payload(self) -> Self:
        from figma_flutter_agent.parser.semantics.prefilter import SEMANTIC_IR_KINDS
        from figma_flutter_agent.schemas.ir_payloads import ChipChoicePayload, payload_for_kind

        if self.kind in SEMANTIC_IR_KINDS and self.payload is None:
            self.payload = payload_for_kind(self.kind, ir_node=self)
        if self.kind == WidgetIrKind.CHIP_CHOICE:
            if isinstance(self.payload, ChipChoicePayload) and self.is_selected is None:
                self.is_selected = self.payload.is_selected
            elif self.is_selected is None and self.payload is None:
                msg = "chip_choice requires isSelected"
                raise ValueError(msg)
        return self


class SemanticOptionVerdict(BaseModel):
    """Report-only semantic option inside a control verdict."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str | None = Field(default=None, alias="nodeId")
    label: str | None = None
    selected: bool | None = None
    value: SemanticScalar | None = None
    confidence: float | None = None


class SemanticContractTraits(BaseModel):
    """Report-only trait bag for future Element Contract / Layout Law gates."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    is_multiline: bool | None = Field(default=None, alias="isMultiline")
    max_lines: int | None = Field(default=None, alias="maxLines")
    obscure_text: bool | None = Field(default=None, alias="obscureText")
    current_value: SemanticScalar | None = Field(default=None, alias="currentValue")
    selected_options: list[str] | None = Field(default=None, alias="selectedOptions")
    rating_value: SemanticScalar | None = Field(default=None, alias="ratingValue")
    rating_max: SemanticScalar | None = Field(default=None, alias="ratingMax")
    action_kind: str | None = Field(default=None, alias="actionKind")
    social_provider: str | None = Field(default=None, alias="socialProvider")
    keyboard_intent: str | None = Field(default=None, alias="keyboardIntent")
    visual_state: str | None = Field(default=None, alias="visualState")


class SemanticControlVerdict(BaseModel):
    """Report-only LLM semantic annotation identifying a future control contract shape."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    role: str
    subtype: str | None = None
    control_node_id: str | None = Field(default=None, alias="controlNodeId")
    boundary_node_id: str | None = Field(default=None, alias="boundaryNodeId")
    label_node_ids: list[str] = Field(default_factory=list, alias="labelNodeIds")
    placeholder_node_ids: list[str] = Field(default_factory=list, alias="placeholderNodeIds")
    value_node_ids: list[str] = Field(default_factory=list, alias="valueNodeIds")
    decoration_node_ids: list[str] = Field(default_factory=list, alias="decorationNodeIds")
    option_node_ids: list[str] = Field(default_factory=list, alias="optionNodeIds")
    state_node_ids: list[str] = Field(default_factory=list, alias="stateNodeIds")
    contract_kind: str | None = Field(default=None, alias="contractKind")
    contract_traits: SemanticContractTraits | None = Field(default=None, alias="contractTraits")
    proposed_layout_laws: list[str] = Field(default_factory=list, alias="proposedLayoutLaws")
    value: SemanticScalar | None = None
    options: list[SemanticOptionVerdict] = Field(default_factory=list)
    confidence: float
    proposed_effects: list[str] = Field(default_factory=list, alias="proposedEffects")
    explanation: str | None = None


class SemanticScreenSummary(BaseModel):
    """Report-only screen-level semantic summary from IR extraction."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    screen_role: str | None = Field(default=None, alias="screenRole")
    confidence: float | None = None
    explanation: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ScreenIr(BaseModel):
    """Screen body structure keyed by Figma node ids."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    root: WidgetIrNode
    omit_figma_ids: list[str] = Field(default_factory=list, alias="omitFigmaIds")
    stack_child_order: list[str] | None = Field(default=None, alias="stackChildOrder")
    state_by_figma_id: dict[str, WidgetIrState] = Field(
        default_factory=dict, alias="stateByFigmaId"
    )
    adaptive_rules: list[AdaptiveRule] = Field(default_factory=list, alias="adaptiveRules")
    semantic_summary: SemanticScreenSummary | None = Field(default=None, alias="semanticSummary")
    semantic_verdicts: list[SemanticControlVerdict] = Field(
        default_factory=list,
        alias="semanticVerdicts",
    )
