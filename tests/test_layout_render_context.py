"""Layout render context typing."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.widgets.emit.context import LayoutRenderContext
from figma_flutter_agent.generator.layout.widgets.emit.shell import build_render_ctx


def test_layout_render_context_dict_compat() -> None:
    ctx = build_render_ctx(
        uses_svg=False,
        theme_variant="light",
        cluster_classes=None,
        cluster_vector_variants=None,
        cluster_vector_variant=None,
        skip_cluster_id=None,
        responsive_enabled=True,
        design_artboard_width=390.0,
        bundled_font_families=None,
        dart_weight_overrides_by_family=None,
        text_theme_slot_by_style_name=None,
        text_theme_size_slots=None,
        de_archetype_pass=False,
    )
    assert isinstance(ctx, LayoutRenderContext)
    assert ctx["responsive_enabled"] is True
    assert ctx.design_artboard_width == 390.0
