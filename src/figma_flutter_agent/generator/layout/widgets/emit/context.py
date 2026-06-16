"""Typed render context for layout widget emitters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.schemas import WidgetIrNode


@dataclass(frozen=True)
class LayoutRenderContext:
    """Shared compile-time context for layout widget emission."""

    uses_svg: bool
    theme_variant: str
    cluster_classes: dict[str, str] | None
    cluster_vector_variants: dict | None
    cluster_vector_variant: object
    skip_cluster_id: str | None
    responsive_enabled: bool
    design_artboard_width: float | None
    bundled_font_families: frozenset[str] | None
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None
    text_theme_slot_by_style_name: dict[str, str] | None
    text_theme_size_slots: list[tuple[float, str]] | None
    de_archetype_pass: bool
    ir_by_id: dict[str, WidgetIrNode] | None = None

    def __getitem__(self, key: str) -> Any:
        """Dict-compatible access for transitional emit call sites."""
        return getattr(self, key)
