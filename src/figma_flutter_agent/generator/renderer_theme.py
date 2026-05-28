"""Theme rendering for Dart code generation."""

from __future__ import annotations

from jinja2 import Environment

from figma_flutter_agent.generator.theme_typography import TEXT_THEME_SLOTS
from figma_flutter_agent.schemas import DesignTokens


def _token_entries(flat: dict[str, float | str]) -> list[dict[str, float | str]]:
    return [{"name": name, "value": value} for name, value in flat.items()]


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
