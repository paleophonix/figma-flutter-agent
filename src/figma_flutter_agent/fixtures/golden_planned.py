"""Build planned Dart files from offline layout fixtures for golden capture."""

from __future__ import annotations

from figma_flutter_agent.fixtures.screens_manifest import ScreenFixtureEntry, load_layout_tree
from figma_flutter_agent.generator.layout_common import to_pascal_case
from figma_flutter_agent.generator.layout_renderer import (
    render_deterministic_screen_files,
    render_layout_file,
)
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


def _screen_class_name(feature_name: str) -> str:
    return f"{to_pascal_case(feature_name)}Screen"


def fixture_design_tokens() -> DesignTokens:
    """Minimal tokens referenced by deterministic layout fixtures."""
    return DesignTokens(
        colors={"primary": "0xFF1A1A1A", "color2": "0xFF664FA3"},
        spacing={"xs": 4.0, "sm": 8.0, "md": 16.0, "lg": 24.0},
        elevations={"md": 2.0},
    )


def _surface_size(tree: CleanDesignTreeNode) -> tuple[int, int]:
    width = int(tree.sizing.width or 414)
    height = int(tree.sizing.height or 896)
    return width, height


def build_fixture_planned_files(
    entry: ScreenFixtureEntry | str,
    *,
    package_name: str = "demo_app",
    use_package_imports: bool = True,
) -> dict[str, str]:
    """Render deterministic planned files for a manifest screen entry.

    Args:
        entry: Manifest entry or screen id.
        package_name: Flutter package name (must match golden skeleton pubspec).
        use_package_imports: Use package imports in generated Dart.

    Returns:
        Relative path → Dart source map (before reconcile).
    """
    tree = load_layout_tree(entry)
    if isinstance(entry, str):
        from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest

        manifest = load_screens_manifest()
        resolved = next(item for item in manifest.screens if item.id == entry)
        feature = resolved.feature
    else:
        feature = entry.feature

    screen_class = _screen_class_name(feature)
    tokens = fixture_design_tokens()
    renderer = DartRenderer()
    planned: dict[str, str] = {}

    planned.update(
        renderer.render_theme_files(
            tokens,
            max_web_width=1200,
            generate_dark_mode=False,
            theme_variant="material_3",
        )
    )
    planned.update(
        render_layout_file(
            tree,
            feature_name=feature,
            uses_svg=True,
            package_name=package_name,
            use_package_imports=use_package_imports,
            responsive_enabled=False,
        )
    )
    planned.update(
        render_deterministic_screen_files(
            feature_name=feature,
            screen_class=screen_class,
            uses_svg=True,
            use_auto_route=False,
            responsive_enabled=False,
            max_web_width=1200,
            package_name=package_name,
            use_package_imports=use_package_imports,
            use_scaffold=True,
        )
    )
    surface_w, surface_h = _surface_size(tree)
    planned.update(
        renderer.render_golden_test(
            feature_name=feature,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_w,
            surface_height=surface_h,
            max_web_width=1200,
        )
    )
    return planned
