"""Design token schema models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from figma_flutter_agent.schemas.geometry import Padding


class TypographyStyle(BaseModel):
    """Typography values keyed by style name."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    font_size: float = Field(alias="fontSize")
    font_weight: str = Field(default="w400", alias="fontWeight")


TypographyToken = TypographyStyle


class DesignTokens(BaseModel):
    """Design tokens extracted from Figma."""

    model_config = ConfigDict(extra="forbid")

    colors: dict[str, str] = Field(default_factory=dict)
    typography: dict[str, TypographyStyle] = Field(default_factory=dict)
    spacing: dict[str, float] = Field(default_factory=dict)
    radii: dict[str, float] = Field(default_factory=dict)
    elevations: dict[str, float] = Field(default_factory=dict)
    edge_insets: dict[str, Padding] = Field(default_factory=dict)
    icons: dict[str, str] = Field(default_factory=dict)
