"""Golden test and capture path alignment."""

from __future__ import annotations

from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.validation import golden_capture
from figma_flutter_agent.validation.golden_capture import (
    capture_planned_flutter_golden_png,
    golden_png_relative_path,
)


def test_golden_test_path_matches_capture_output() -> None:
    """``matchesGoldenFile`` path from ``test/golden/`` must resolve to capture PNG path."""
    feature = "onboarding"
    files = DartRenderer().render_golden_test(
        feature_name=feature,
        screen_class="OnboardingScreen",
        package_name="demo_app",
        surface_width=360,
        surface_height=640,
        max_web_width=480,
    )
    test_rel = f"test/golden/{feature}_screen_test.dart"
    content = files[test_rel]
    assert "../goldens/" in content
    assert golden_png_relative_path(feature) == f"test/goldens/{feature}_screen.png"


def test_first_process_line_prefers_dart_diagnostic() -> None:
    from figma_flutter_agent.validation.golden_capture import _first_process_line

    class _Result:
        stderr = (
            "../../flutter_tools/listener.dart:6:8: Error: Error while loading\n"
            "lib/features/sign_in/sign_in_screen.dart:7:8: Error: Not found: 'x.dart'\n"
        )
        stdout = ""

    message = _first_process_line(_Result())
    assert "sign_in_screen.dart:7:8" in message


def test_capture_passes_flutter_sdk_to_resolver(monkeypatch) -> None:
    """Golden capture must honor ``FIGMA_FLUTTER_SDK``, not only PATH."""
    seen: list[str | None] = []

    def _fake_resolve(*, sdk_root: str | None = None) -> None:
        seen.append(sdk_root)
        return None

    monkeypatch.setattr(golden_capture, "resolve_flutter_executable", _fake_resolve)
    outcome = capture_planned_flutter_golden_png(
        {},
        feature_name="sign_in",
        flutter_sdk="/opt/flutter",
    )
    assert not outcome.ok
    assert outcome.reason is not None
    assert "Flutter SDK" in outcome.reason
    assert seen == ["/opt/flutter"]
