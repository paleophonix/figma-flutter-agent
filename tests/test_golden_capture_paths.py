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
    golden_capture._prepare_flutter_test_build_dir(tmp_path)
    assert not (tmp_path / "build").exists()


def test_materialize_syncs_fonts_and_icon_tree(tmp_path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    fonts = source / "assets" / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "helvetica_neue_500.otf").write_bytes(
        b"\x00\x01\x00\x00" + (b"\x00" * 252)
    )
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
