"""Generated Flutter test rendering helpers."""

from __future__ import annotations

from pathlib import Path


def golden_test_harness_dart(templates_root: Path) -> str:
    """Load golden-test harness Dart."""
    harness_path = templates_root / "element_coordinate_mapper.harness"
    return harness_path.read_text(encoding="utf-8")


def render_golden_test(
    *,
    template: object,
    templates_root: Path,
    feature_name: str,
    screen_class: str,
    package_name: str,
    surface_width: int,
    surface_height: int,
    max_web_width: int,
) -> dict[str, str]:
    """Render a Flutter golden test scaffold for the primary screen."""
    golden_file_name = f"../goldens/{feature_name}_screen.png"
    return {
        f"test/golden/{feature_name}_screen_test.dart": template.render(
            feature_name=feature_name,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_width,
            surface_height=surface_height,
            max_web_width=max_web_width,
            golden_file_name=golden_file_name,
        ),
        "test/harness/element_coordinate_mapper.dart": golden_test_harness_dart(templates_root),
    }


def render_capture_test(
    *,
    template: object,
    templates_root: Path,
    feature_name: str,
    screen_class: str,
    package_name: str,
    surface_width: int,
    surface_height: int,
    max_web_width: int,
    collect_figma_keys: bool,
) -> dict[str, str]:
    """Render a lightweight widget test that writes a PNG path from the environment."""
    files = {
        f"test/capture/{feature_name}_screen_capture_test.dart": template.render(
            feature_name=feature_name,
            screen_class=screen_class,
            package_name=package_name,
            surface_width=surface_width,
            surface_height=surface_height,
            max_web_width=max_web_width,
            collect_figma_keys=collect_figma_keys,
        ),
    }
    if collect_figma_keys:
        files["test/harness/element_coordinate_mapper.dart"] = golden_test_harness_dart(
            templates_root
        )
    return files


def render_typography_specimens_test(
    *,
    template: object,
    package_name: str,
    max_web_width: int,
) -> dict[str, str]:
    """Render Flutter golden tests for Table E typography specimens."""
    from figma_flutter_agent.validation.specimens import load_font_specimens

    registry = load_font_specimens()
    return {
        "test/golden/typography_specimens_test.dart": template.render(
            package_name=package_name,
            max_web_width=max_web_width,
            specimens=registry.specimens,
        )
    }
