"""Unit tests for golden/capture and Chrome render surface resolution."""

from __future__ import annotations

from figma_flutter_agent.config.models import ResponsiveConfig
from figma_flutter_agent.dev.preview_size import (
    ARTBOARD_PREVIEW_HEIGHT_DEFINE,
    ARTBOARD_PREVIEW_WIDTH_DEFINE,
)
from figma_flutter_agent.generator.capture_screen_test import infer_test_surface_size
from figma_flutter_agent.generator.render_surface import (
    capture_render_dart_defines,
    chrome_preview_dart_defines_for_responsive,
    resolve_capture_surface_size,
    resolve_chrome_preview_size,
)


def test_resolve_capture_surface_size_always_uses_artboard() -> None:
    responsive = ResponsiveConfig(adaptive_render=True, max_web_width=1200)
    assert resolve_capture_surface_size(artboard_width=390, artboard_height=844) == (390, 844)
    _ = responsive


def test_resolve_chrome_preview_size_uses_artboard_when_not_adaptive() -> None:
    responsive = ResponsiveConfig(adaptive_render=False, max_web_width=1200)
    assert resolve_chrome_preview_size(
        artboard_width=390,
        artboard_height=844,
        responsive=responsive,
    ) == (390, 844)


def test_resolve_chrome_preview_size_expands_width_when_adaptive() -> None:
    responsive = ResponsiveConfig(adaptive_render=True, max_web_width=1200)
    assert resolve_chrome_preview_size(
        artboard_width=390,
        artboard_height=844,
        responsive=responsive,
    ) == (1200, 844)


def test_capture_render_dart_defines_always_artboard_locked() -> None:
    defines = capture_render_dart_defines(surface_width=390, surface_height=844)
    assert f"--dart-define={ARTBOARD_PREVIEW_WIDTH_DEFINE}=390" in defines
    assert f"--dart-define={ARTBOARD_PREVIEW_HEIGHT_DEFINE}=844" in defines


def test_chrome_preview_dart_defines_omitted_when_adaptive() -> None:
    responsive = ResponsiveConfig(adaptive_render=True)
    assert (
        chrome_preview_dart_defines_for_responsive(
            surface_width=1200,
            surface_height=844,
            responsive=responsive,
        )
        == []
    )


def test_infer_test_surface_size_parses_capture_test() -> None:
    source = """
    await tester.binding.setSurfaceSize(const Size(428, 926));
    """
    assert infer_test_surface_size(source) == (428, 926)


def test_infer_test_surface_size_default_when_missing() -> None:
    assert infer_test_surface_size("// no surface") == (390, 844)
