"""Theme rendering for Dart code generation."""

from __future__ import annotations

from jinja2 import Environment

from figma_flutter_agent.schemas import ColorToken, DesignTokens, SpacingToken


def render_theme_files(
    env: Environment,
    tokens: DesignTokens,
    *,
    max_web_width: int = 480,
    generate_dark_mode: bool = False,
    theme_variant: str = "material_3",
) -> dict[str, str]:
    """Render deterministic theme files from design tokens."""
    colors = list(tokens.colors)
    if not colors:
        colors = [ColorToken(name="primary", value="0xFF6750A4")]
    spacing = list(tokens.spacing)
    if not spacing:
        spacing = [
            SpacingToken(name="sm", value=8.0),
            SpacingToken(name="medium", value=16.0),
            SpacingToken(name="md", value=16.0),
        ]
    seed_color_name = colors[0].name
    files = {
        "lib/theme/app_layout.dart": env.get_template("app_layout.dart.j2").render(),
        "lib/theme/app_colors.dart": env.get_template("app_colors.dart.j2").render(colors=colors),
        "lib/theme/app_spacing.dart": env.get_template("app_spacing.dart.j2").render(
            spacing=spacing
        ),
        "lib/theme/app_typography.dart": env.get_template("app_typography.dart.j2").render(
            typography=tokens.typography
        ),
        "lib/theme/app_radius.dart": env.get_template("app_radius.dart.j2").render(
            radii=tokens.radii
        ),
        "lib/theme/app_elevation.dart": env.get_template("app_elevation.dart.j2").render(
            elevations=tokens.elevations
        ),
        "lib/theme/app_theme.dart": env.get_template("app_theme.dart.j2").render(
            seed_color_name=seed_color_name,
            max_web_width=max_web_width,
            generate_dark_mode=generate_dark_mode,
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
