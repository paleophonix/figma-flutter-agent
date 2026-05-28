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


def test_first_process_line_prefers_stack_layout_error_over_pub_get_noise() -> None:
    from figma_flutter_agent.validation.golden_capture import _first_process_line

    class _Result:
        stdout = "Resolving dependencies...\nGot dependencies!\n"
        stderr = (
            "A Stack requires bounded constraints from its parent. "
            "This error commonly occurs when a Stack is\n"
        )

    message = _first_process_line(_Result())
    assert "Stack requires bounded constraints" in message
    assert "Resolving dependencies" not in message


def test_prepare_capture_workspace_isolated_from_live_project(tmp_path) -> None:
    project = tmp_path / "demo_app"
    project.mkdir()
    (project / "pubspec.yaml").write_text("name: demo_app\n")
    capture_dir, handle, enable_backup = golden_capture._prepare_capture_workspace(
        {},
        feature_name="sign_in",
        project_dir=project,
        layout_tree=None,
    )
    try:
        assert handle is not None
        assert enable_backup is False
        assert capture_dir.resolve() != project.resolve()
        assert capture_dir.name == "golden_capture"
    finally:
        if handle is not None:
            handle.cleanup()


def test_prepare_flutter_test_build_dir_creates_unit_test_assets(tmp_path) -> None:
    golden_capture._prepare_flutter_test_build_dir(tmp_path)
    assets_dir = tmp_path / "build" / "unit_test_assets"
    assert assets_dir.is_dir()


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
