"""Variant configuration models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ComponentConfig(BaseModel):
    """Variant visibility and slot configuration (WP-3)."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    visible: bool = True
    slot_overrides: dict[str, str] = Field(default_factory=dict, alias="slotOverrides")
    frozen_params: tuple[str, ...] = Field(default_factory=tuple, alias="frozenParams")
