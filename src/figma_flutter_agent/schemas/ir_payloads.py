"""Typed semantic payloads for screen IR widget kinds."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LlmClassificationHint(BaseModel):
    """Optional LLM grey-zone hint (never authoritative on its own)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    suggested_kind: str = Field(alias="suggestedKind")
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str | None = None

    @field_validator("suggested_kind")
    @classmethod
    def _validate_suggested_kind(cls, value: str) -> str:
        from figma_flutter_agent.schemas.ir import WidgetIrKind

        WidgetIrKind(value)
        return value


class ChipChoicePayload(BaseModel):
    """Payload for ``chip_choice`` IR nodes."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    payload_kind: Literal["chip_choice"] = Field(default="chip_choice", alias="payloadKind")
    is_selected: bool = Field(alias="isSelected")


class InputTextFieldPayload(BaseModel):
    """Payload for ``input_text_field`` IR nodes."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    payload_kind: Literal["input_text_field"] = Field(
        default="input_text_field",
        alias="payloadKind",
    )
    hint_text: str | None = Field(default=None, alias="hintText")
    error_text: str | None = Field(default=None, alias="errorText")
    is_multiline: bool = Field(default=False, alias="isMultiline")
    max_lines: int | None = Field(default=None, alias="maxLines")


class GenericSemanticPayload(BaseModel):
    """Minimal payload for kinds without extra parameters."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    payload_kind: str = Field(alias="payloadKind")


KindPayload = ChipChoicePayload | InputTextFieldPayload | GenericSemanticPayload


def payload_for_kind(kind: object, *, ir_node: object | None = None) -> KindPayload:
    """Build a default payload for a classified semantic kind."""
    from figma_flutter_agent.schemas.ir import WidgetIrKind

    if not isinstance(kind, WidgetIrKind):
        kind = WidgetIrKind(str(kind))
    if kind == WidgetIrKind.CHIP_CHOICE:
        is_selected = False
        if ir_node is not None and getattr(ir_node, "is_selected", None) is not None:
            is_selected = bool(ir_node.is_selected)
        return ChipChoicePayload(is_selected=is_selected)
    if kind == WidgetIrKind.INPUT_TEXT_FIELD:
        return InputTextFieldPayload(
            hint_text=getattr(ir_node, "hint_text", None) if ir_node else None,
            error_text=getattr(ir_node, "error_text", None) if ir_node else None,
            is_multiline=bool(getattr(ir_node, "is_multiline", False)) if ir_node else False,
            max_lines=getattr(ir_node, "max_lines", None) if ir_node else None,
        )
    return GenericSemanticPayload(payload_kind=kind.value)
