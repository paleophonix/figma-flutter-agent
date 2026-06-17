"""Golden test and capture path alignment."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.validation import golden_capture
from figma_flutter_agent.validation.golden_capture import (
    _resolve_host_capture_test,
    capture_planned_flutter_golden_png,
    capture_test_relative_path,
    golden_png_relative_path,
)


def test_capture_test_emitted_for_visual_refine() -> None:
    feature = "choose_topic"
    files = DartRenderer().render_capture_test(
        feature_name=feature,
        screen_class="ChooseTopicScreen",
        package_name="demo_app",
        surface_width=414,
        surface_height=896,
        max_web_width=1200,
        collect_figma_keys=False,
    )
    rel = capture_test_relative_path(feature)
    assert rel in files
    assert "FIGMA_FLUTTER_CAPTURE_OUT" in files[rel]
    assert "import 'dart:ui' show ImageByteFormat;" in files[rel]
    assert "ImageByteFormat.png" in files[rel]
    assert "matchesGoldenFile" not in files[rel]
    assert "package:flutter/painting.dart" not in files[rel]


def test_resolve_host_capture_prefers_capture_test() -> None:
    from pydantic import SecretStr

    from figma_flutter_agent.config import AgentYamlConfig, GenerationConfig, Settings

    planned = {
        capture_test_relative_path("demo"): "// capture",
        "test/golden/demo_screen_test.dart": "// golden",
    }
    settings = Settings(
        FIGMA_ACCESS_TOKEN=SecretStr("x"),
        agent=AgentYamlConfig(
            generation=GenerationConfig(llm_visual_refine_capture_golden=False),
        ),
    )
    rel, fast = _resolve_host_capture_test(planned, "demo", settings)
    assert fast is True
    assert rel == capture_test_relative_path("demo")


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


def test_first_process_line_surfaces_renderflex_overflow() -> None:
    from figma_flutter_agent.validation.golden_capture import _first_process_line

    class _Result:
        stdout = "00:05 +0 -1: Some tests failed.\n"
        stderr = "A RenderFlex overflowed by 15 pixels on the bottom.\n"

    message = _first_process_line(_Result())
    assert "RenderFlex overflowed by 15 pixels" in message


def test_first_process_line_surfaces_test_timeout() -> None:
    from figma_flutter_agent.validation.golden_capture import _first_process_line

    class _Result:
        stdout = ""
        stderr = (
            "TimeoutException after 0:10:00.000000: Test timed out after 10 minutes.\n"
            "package:flutter_test/src/binding.dart:1234:5\n"
        )

    message = _first_process_line(_Result())
    assert "TimeoutException" in message or "Test timed out" in message


def test_first_process_line_prefers_timeout_over_some_tests_failed() -> None:
    from figma_flutter_agent.validation.golden_capture import _first_process_line

    class _Result:
        stdout = (
            "00:00 +0: capture DemoScreen\n"
            "10:00 +0 -1: capture DemoScreen [E]\n"
            "  TimeoutException after 0:10:00.000000: Test timed out after 10 minutes.\n"
            "10:00 +0 -1: Some tests failed.\n"
        )
        stderr = ""

    message = _first_process_line(_Result())
    assert "TimeoutException" in message
    assert "Some tests failed" not in message


def test_prepare_capture_workspace_isolated_from_live_project() -> None:
    capture_dir, handle = golden_capture._prepare_capture_workspace()
    try:
        assert handle is not None
        assert capture_dir.name == "golden_capture"
        assert (capture_dir / "pubspec.yaml").is_file()
    finally:
        handle.cleanup()


def test_prepare_flutter_test_build_dir_removes_stale_build(tmp_path) -> None:
    stale = tmp_path / "build" / "unit_test_assets"
    stale.mkdir(parents=True)
    (stale / "stale.txt").write_text("x", encoding="utf-8")
    assert golden_capture._prepare_flutter_test_build_dir(tmp_path) is True
    assert not (tmp_path / "build").exists()


def test_prepare_flutter_test_build_dir_retries_locked_build(tmp_path, monkeypatch) -> None:
    """Locked build trees should be retried before capture aborts."""
    import shutil as std_shutil

    real_rmtree = std_shutil.rmtree
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    (build_dir / "unit_test_assets").mkdir()
    attempts = {"count": 0}

    def _flaky_rmtree(path, onerror=None):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise OSError("locked")
        return real_rmtree(path, onerror=onerror)

    monkeypatch.setattr(
        "figma_flutter_agent.validation.golden_capture.project.shutil.rmtree",
        _flaky_rmtree,
    )
    monkeypatch.setattr(
        "figma_flutter_agent.validation.golden_capture.project.time.sleep",
        lambda _sec: None,
    )
    assert golden_capture._prepare_flutter_test_build_dir(tmp_path) is True
    assert attempts["count"] == 2


def test_ensure_flutter_test_build_dir_hygienic_clears_file_blocking_unit_test_assets(
    tmp_path: Path,
) -> None:
    blocking = tmp_path / "build" / "unit_test_assets"
    blocking.parent.mkdir(parents=True)
    blocking.write_text("not-a-directory", encoding="utf-8")
    assert golden_capture._ensure_flutter_test_build_dir_hygienic(tmp_path) is True
    assert (tmp_path / "build" / "unit_test_assets").is_dir()


def test_is_flutter_build_permission_error_detects_unwritable_build_dir_message() -> None:
    from figma_flutter_agent.validation.golden_capture.logs import is_flutter_build_permission_error

    message = (
        "flutter test build directory is not writable "
        "(E:/proj/.figma-flutter/capture-sandbox/build); close other dart/flutter processe..."
    )
    assert is_flutter_build_permission_error(message)


def test_is_flutter_build_permission_error_detects_unit_test_assets_message() -> None:
    from figma_flutter_agent.validation.golden_capture.logs import is_flutter_build_permission_error

    message = (
        'Flutter failed to check for directory existence at "build\\unit_test_assets". '
        "The flutter tool cannot access the file or directory."
    )
    assert is_flutter_build_permission_error(message)


def test_materialize_syncs_fonts_and_icon_tree(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    fonts = source / "assets" / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "helvetica_neue_500.otf").write_bytes(b"\x00\x01\x00\x00" + (b"\x00" * 252))
    icons = source / "assets" / "icons"
    icons.mkdir(parents=True)
    (icons / "hero.svg").write_text("<svg/>", encoding="utf-8")
    (source / "pubspec.yaml").write_text(
        "name: demo_app\n"
        "environment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n"
        "flutter:\n  uses-material-design: true\n"
        "  assets:\n    - assets/icons/\n"
        "  fonts:\n    - family: Helvetica Neue\n"
        "      fonts:\n        - asset: assets/fonts/helvetica_neue_500.otf\n"
        "          weight: 500\n",
        encoding="utf-8",
    )
    capture_dir, handle = golden_capture._prepare_capture_workspace()
    try:
        planned = {
            "lib/features/demo/demo_screen.dart": (
                "import 'package:flutter_svg/flutter_svg.dart';\n"
                "SvgPicture.asset('assets/icons/hero.svg');\n"
            ),
        }
        golden_capture._materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=None,
            project_dir=source,
        )
        assert (capture_dir / "assets/fonts/helvetica_neue_500.otf").is_file()
        assert (capture_dir / "assets/icons/hero.svg").is_file()
    finally:
        handle.cleanup()


def test_materialize_capture_workspace_syncs_theme_lib(tmp_path: Path) -> None:
    source = tmp_path / "source"
    theme = source / "lib" / "theme"
    theme.mkdir(parents=True)
    (theme / "app_layout.dart").write_text(
        "class AppBreakpoints { static bool isWideLayout(double w) => false; }\n",
        encoding="utf-8",
    )
    (source / "pubspec.yaml").write_text(
        "name: demo_app\nenvironment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n",
        encoding="utf-8",
    )
    capture_dir, handle = golden_capture._prepare_capture_workspace()
    try:
        planned = {
            "lib/generated/demo_layout.dart": (
                "import 'package:demo_app/theme/app_layout.dart';\n"
                "AppBreakpoints.isWideLayout(400);\n"
            ),
        }
        golden_capture._materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=None,
            project_dir=source,
        )
        assert (capture_dir / "lib" / "theme" / "app_layout.dart").is_file()
    finally:
        handle.cleanup()


def test_capture_passes_flutter_sdk_to_resolver(monkeypatch) -> None:
    """Golden capture must honor ``FIGMA_FLUTTER_SDK``, not only PATH."""
    seen: list[str | None] = []

    def _fake_resolve(*, sdk_root: str | None = None) -> None:
        seen.append(sdk_root)
        return None

    monkeypatch.setattr(
        golden_capture.capture_host_run, "resolve_flutter_executable", _fake_resolve
    )
    outcome = capture_planned_flutter_golden_png(
        {},
        feature_name="sign_in",
        flutter_sdk="/opt/flutter",
    )
    assert not outcome.ok
    assert outcome.reason is not None
    assert "Flutter SDK" in outcome.reason
    assert seen == ["/opt/flutter"]
