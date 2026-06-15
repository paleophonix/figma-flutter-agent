"""Figma style → Jinja template context for semantic widgets (EPIC 3.2)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


def _color_dart(raw: str | None) -> str | None:
    if raw is None or not str(raw).strip():
        return None
    text = str(raw).strip()
    if text.startswith("Color("):
        return text
    if text.startswith("0x"):
        return f"Color({text})"
    return f"Color(0x{text})"


def _radius_dart(radius: float | None) -> str | None:
    if radius is None:
        return None
    return f"BorderRadius.circular({radius})"


@dataclass(frozen=True)
class FigmaStyleContext:
    """Typed style payload for semantic Jinja templates."""

    background_color: str | None = None
    border_radius: str | None = None
    border_color: str | None = None
    border_width: str | None = None
    padding_horizontal: str | None = None
    padding_vertical: str | None = None
    text_color: str | None = None
    font_size: str | None = None
    elevation: str | None = None

    def as_template_dict(self) -> dict[str, str | None]:
        return {
            "background_color": self.background_color,
            "border_radius": self.border_radius,
            "border_color": self.border_color,
            "border_width": self.border_width,
            "padding_horizontal": self.padding_horizontal,
            "padding_vertical": self.padding_vertical,
            "text_color": self.text_color,
            "font_size": self.font_size,
            "elevation": self.elevation,
        }


def build_style_context(
    clean: CleanDesignTreeNode,
    *,
    tokens: DesignTokens | None = None,
    ctx: IrEmitContext | None = None,
) -> FigmaStyleContext:
    """Map clean-tree style fields to Dart expression fragments for templates."""
    del tokens, ctx
    style = clean.style
    pad = clean.padding
    return FigmaStyleContext(
        background_color=_color_dart(style.background_color),
        border_radius=_radius_dart(style.border_radius),
        border_color=_color_dart(style.border_color),
        border_width=(f"{style.border_width}" if style.border_width is not None else None),
        padding_horizontal=(f"{pad.left + pad.right}" if pad is not None else None),
        padding_vertical=(f"{pad.top + pad.bottom}" if pad is not None else None),
        text_color=_color_dart(style.text_color),
        font_size=f"{style.font_size}" if style.font_size is not None else None,
        elevation=f"{style.elevation}" if style.elevation is not None else None,
    )
