"""Theme rendering for Dart code generation."""

from __future__ import annotations

import re
from collections.abc import Mapping

from jinja2 import Environment
from loguru import logger

from figma_flutter_agent.generator.theme_typography import TEXT_THEME_SLOTS
from figma_flutter_agent.schemas import DesignTokens

_THEME_PREFIX = "lib/theme/"
_APP_TYPOGRAPHY_REF_RE = re.compile(r"AppTypography\.(\w+)")
_APP_TYPOGRAPHY_STYLE_RE = re.compile(r"static const TextStyle (\w+) =")


def _token_entries(flat: dict[str, float | str]) -> list[dict[str, float | str]]:
    return [{"name": name, "value": value} for name, value in flat.items()]


def missing_app_typography_style_refs(planned: Mapping[str, str]) -> tuple[str, ...]:
    """Return ``AppTypography`` names referenced by ``app_theme`` but not declared."""
    theme_source = planned.get("lib/theme/app_theme.dart")
    typography_source = planned.get("lib/theme/app_typography.dart")
    if not theme_source or not typography_source:
        return ()
    refs = set(_APP_TYPOGRAPHY_REF_RE.findall(theme_source))
    if not refs:
        return ()
    declared = set(_APP_TYPOGRAPHY_STYLE_RE.findall(typography_source))
    return tuple(sorted(refs - declared))


def ensure_theme_typography_coherence(
    planned: dict[str, str],
    tokens: DesignTokens,
    env: Environment,
    *,
    max_web_width: int = 1200,
    generate_dark_mode: bool = False,
    theme_variant: str = "material_3",
) -> bool:
    """Re-render ``lib/theme/*`` when ``app_theme`` and ``app_typography`` drift apart.

    Args:
        planned: Planned project-relative Dart paths.
        tokens: Design tokens used for theme rendering.
        env: Jinja environment for theme templates.
        max_web_width: Responsive shell width passed to ``app_theme``.
        generate_dark_mode: Whether to emit dark theme variant.
        theme_variant: Theme template variant (``material_3`` or ``cupertino``).

    Returns:
        True when the theme bundle was re-rendered into ``planned``.
    """
    missing = missing_app_typography_style_refs(planned)
    if not missing:
        return False
    logger.warning(
        "Theme typography drift detected (missing AppTypography: {}); re-rendering lib/theme/*",
        ", ".join(missing[:8]),
    )
    planned.update(
        render_theme_files(
            env,
            tokens,
            max_web_width=max_web_width,
            generate_dark_mode=generate_dark_mode,
            theme_variant=theme_variant,
        )
    )
    return True


def expand_theme_bundle_writes(
    selected: dict[str, str],
    planned_files: Mapping[str, str],
) -> dict[str, str]:
    """When any theme file is written, include the full ``lib/theme`` bundle."""
    if not any(path.startswith(_THEME_PREFIX) for path in selected):
        return selected
    expanded = dict(selected)
    for path, content in planned_files.items():
        if path.startswith(_THEME_PREFIX):
            expanded[path] = content
    return expanded


def _text_theme_mappings(
    typography: list[dict[str, float | str]],
) -> list[dict[str, str]]:
    """Map Figma typography tokens to Material ``TextTheme`` slots (largest first)."""
    if not typography:
        return []
    ordered = sorted(typography, key=lambda item: float(item["font_size"]), reverse=True)
    return [
        {"slot": slot, "style_name": str(style["style_name"])}
        for slot, style in zip(TEXT_THEME_SLOTS, ordered, strict=False)
    ]


def render_theme_files(
    env: Environment,
    tokens: DesignTokens,
    *,
    max_web_width: int = 480,
    generate_dark_mode: bool = False,
    theme_variant: str = "material_3",
) -> dict[str, str]:
    """Render deterministic theme files from design tokens."""
    colors = _token_entries(tokens.colors)
    if not colors:
        colors = [{"name": "primary", "value": "0xFF6750A4"}]
    spacing = _token_entries(tokens.spacing)
    if not spacing:
        spacing = [
            {"name": "sm", "value": 8.0},
            {"name": "medium", "value": 16.0},
            {"name": "md", "value": 16.0},
        ]
    elevations = _token_entries(tokens.elevations)
    if not elevations:
        elevations = [{"name": "md", "value": 2.0}]
    radii = _token_entries(tokens.radii)
    if not radii:
        radii = [{"name": "md", "value": 8.0}]
    edge_insets = [
        {
            "name": name,
            "left": inset.left,
            "top": inset.top,
            "right": inset.right,
            "bottom": inset.bottom,
        }
        for name, inset in tokens.edge_insets.items()
    ]
    typography = [
        {"style_name": name, "font_size": style.font_size, "font_weight": style.font_weight}
        for name, style in tokens.typography.items()
    ]
    seed_color_name = str(colors[0]["name"])
    files = {
        "lib/theme/app_layout.dart": env.get_template("app_layout.dart.j2").render(),
        "lib/theme/app_colors.dart": env.get_template("app_colors.dart.j2").render(colors=colors),
        "lib/theme/app_spacing.dart": env.get_template("app_spacing.dart.j2").render(
            spacing=spacing
        ),
        "lib/theme/app_typography.dart": env.get_template("app_typography.dart.j2").render(
            typography=typography
        ),
        "lib/theme/app_radius.dart": env.get_template("app_radius.dart.j2").render(radii=radii),
        **(
            {
                "lib/theme/app_edge_insets.dart": env.get_template(
                    "app_edge_insets.dart.j2"
                ).render(edge_insets=edge_insets)
            }
            if edge_insets
            else {}
        ),
        "lib/theme/app_elevation.dart": env.get_template("app_elevation.dart.j2").render(
            elevations=elevations
        ),
        "lib/theme/app_theme.dart": env.get_template("app_theme.dart.j2").render(
            seed_color_name=seed_color_name,
            max_web_width=max_web_width,
            generate_dark_mode=generate_dark_mode,
            text_theme_mappings=_text_theme_mappings(typography),
        ),
    }
    if theme_variant == "cupertino":
        files["lib/theme/app_cupertino_theme.dart"] = env.get_template(
            "app_cupertino_theme.dart.j2"
        ).render(
            seed_color_name=seed_color_name,
            max_web_width=max_web_width,
            generate_dark_mode=generate_dark_mode,
        )
    return files


def render_design_gallery(
    env: Environment,
    tokens: DesignTokens,
    *,
    package_name: str,
) -> dict[str, str]:
    """Render an in-app design token gallery screen."""
    colors = _token_entries(tokens.colors)
    spacing = _token_entries(tokens.spacing)
    radii = _token_entries(tokens.radii)
    elevations = _token_entries(tokens.elevations)
    typography = [
        {"style_name": name, "font_size": style.font_size, "font_weight": style.font_weight}
        for name, style in tokens.typography.items()
    ]
    edge_insets = [
        {
            "name": name,
            "left": inset.left,
            "top": inset.top,
            "right": inset.right,
            "bottom": inset.bottom,
        }
        for name, inset in tokens.edge_insets.items()
    ]
    icons = [{"name": name, "asset_key": key} for name, key in tokens.icons.items()]
    return {
        "lib/dev/design_gallery_screen.dart": env.get_template(
            "app_design_gallery.dart.j2"
        ).render(
            package_name=package_name,
            colors=colors,
            spacing=spacing,
            radii=radii,
            elevations=elevations,
            typography=typography,
            edge_insets=edge_insets,
            icons=icons,
        )
    }
