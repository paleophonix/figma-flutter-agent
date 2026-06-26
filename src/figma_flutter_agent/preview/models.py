"""Preview scene and capture request/result models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PreviewNode(BaseModel):
    """One absolutely positioned preview layer."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["rect", "text", "image"]
    x: float
    y: float
    width: float
    height: float
    fill: str | None = None
    border_radius: float | None = None
    border_width: float | None = None
    border_color: str | None = None
    opacity: float | None = None
    text: str | None = None
    font_size: float | None = None
    font_family: str | None = None
    font_weight: str | int | None = None
    color: str | None = None
    line_height: float | None = None
    image_src: str | None = None


class PreviewScene(BaseModel):
    """Serializable scene for the browser preview renderer."""

    model_config = ConfigDict(extra="forbid")

    width: int
    height: int
    background: str = "#FFFFFF"
    nodes: list[PreviewNode] = Field(default_factory=list)


class PreviewCaptureRequest(BaseModel):
    """Input for a single browser preview capture."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    scene: PreviewScene
    output_path: Path | None = None
    timeout_sec: float = 5.0
    device_scale_factor: float = 1.0
    screen_id: str | None = None


class PreviewCaptureResult(BaseModel):
    """Outcome of a browser preview capture attempt."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    png: bytes | None = None
    reason: str | None = None
    elapsed_sec: float | None = None
    backend: str = "browser_preview"

    @property
    def ok(self) -> bool:
        return self.png is not None and self.reason is None
