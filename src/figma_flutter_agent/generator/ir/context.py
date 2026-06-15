"""IR emission context and policy."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.config.models import SemanticsSettings
from figma_flutter_agent.generator.cluster_variants import ClusterVectorVariant


@dataclass(frozen=True)
class IrEmitPolicy:
    """Controls IR validation and auto-guards before Dart emission."""

    apply_guards: bool = True
    validate: bool = True


@dataclass(frozen=True)
class IrEmitContext:
    """Codegen context shared with deterministic layout rendering."""

    semantic_report_only: bool | None = None
    semantics: SemanticsSettings = field(default_factory=SemanticsSettings)
    uses_svg: bool = False
    cluster_classes: dict[str, str] | None = None
    cluster_vector_variants: dict[str, ClusterVectorVariant] | None = None
    theme_variant: str = "material_3"
    responsive_enabled: bool = True
    is_layout_root: bool = True
    bundled_font_families: frozenset[str] | None = None
    dart_weight_overrides_by_family: dict[str, dict[str, str]] | None = None
    text_theme_slot_by_style_name: dict[str, str] | None = None
    text_theme_size_slots: list[tuple[float, str]] | None = None
    strict_fidelity: bool = False
    strict_l10n: bool = False
    strict_a11y: bool = False
    strict_contrast: bool = False
    policy: IrEmitPolicy = IrEmitPolicy()


def render_kwargs(ctx: IrEmitContext) -> dict[str, object]:
    return {
        "uses_svg": ctx.uses_svg,
        "cluster_classes": ctx.cluster_classes,
        "cluster_vector_variants": ctx.cluster_vector_variants,
        "theme_variant": ctx.theme_variant,
        "responsive_enabled": ctx.responsive_enabled,
        "bundled_font_families": ctx.bundled_font_families,
        "dart_weight_overrides_by_family": ctx.dart_weight_overrides_by_family,
        "text_theme_slot_by_style_name": ctx.text_theme_slot_by_style_name,
        "text_theme_size_slots": ctx.text_theme_size_slots,
    }
