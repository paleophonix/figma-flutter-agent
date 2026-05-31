from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@contextmanager
def _patch_toolchain_subprocess() -> Iterator[MagicMock]:
    with patch("figma_flutter_agent.generator.validation.run_subprocess") as run:
        with patch("figma_flutter_agent.generator.codegen.run_subprocess", run):
            yield run

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.validation import (
    _analyze_failure_details,
    _analyze_has_errors,
    _strip_windows_zone_identifier_noise,
    validate_dart_project,
)


def test_validate_dart_project_skips_when_dart_missing(tmp_path: Path) -> None:
    with patch(
        "figma_flutter_agent.generator.validation._toolchain_executables",
        return_value=(None, None),
    ):
        validate_dart_project(tmp_path)


def test_validate_dart_project_runs_commands_when_dart_available(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "main.dart").write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.return_value.returncode = 0
        validate_dart_project(tmp_path, analyze_scope="project")

    assert run.call_count == 1
    analyze_args = run.call_args_list[0][0][0]
    assert analyze_args[0] == "/usr/bin/flutter"
    assert analyze_args[1:3] == ["analyze", "--no-fatal-warnings"]


def test_validate_dart_project_generated_only_analyzes_planned_paths(tmp_path: Path) -> None:
    target = tmp_path / "lib" / "theme" / "app_colors.dart"
    target.parent.mkdir(parents=True)
    target.write_text("const x = 1;", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.return_value.returncode = 0
        validate_dart_project(
            tmp_path,
            analyze_scope="generated_only",
            relative_paths=["lib/theme/app_colors.dart"],
        )

    analyze_args = run.call_args_list[-1][0][0]
    assert analyze_args[0] == "/usr/bin/flutter"
    assert analyze_args[1:3] == ["analyze", "--no-fatal-warnings"]
    assert str(target) in analyze_args


def test_validate_dart_project_runs_pub_get_when_pubspec_present(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text(
        "name: demo_app\nenvironment:\n  sdk: '>=3.3.0 <4.0.0'\n"
        "dependencies:\n  flutter:\n    sdk: flutter\n",
        encoding="utf-8",
    )
    target = tmp_path / "lib" / "main.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        patch(
            "figma_flutter_agent.generator.codegen.shutil.which",
            return_value="/usr/bin/flutter",
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.return_value.returncode = 0
        validate_dart_project(
            tmp_path,
            analyze_scope="generated_only",
            relative_paths=["lib/main.dart"],
        )
    pub_get_calls = [
        call[0][0]
        for call in run.call_args_list
        if call[0][0][:3] == ["/usr/bin/flutter", "pub", "get"]
    ]
    assert len(pub_get_calls) == 1
    assert "--offline" in pub_get_calls[0]


def test_validate_dart_project_skips_pub_get_when_stamp_current(tmp_path: Path) -> None:
    from figma_flutter_agent.generator.pub_get_policy import mark_pubspec_resolved

    (tmp_path / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
    (tmp_path / ".dart_tool").mkdir()
    (tmp_path / ".dart_tool" / "package_config.json").write_text("{}", encoding="utf-8")
    mark_pubspec_resolved(tmp_path)
    target = tmp_path / "lib" / "main.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.return_value.returncode = 0
        validate_dart_project(
            tmp_path,
            analyze_scope="generated_only",
            relative_paths=["lib/main.dart"],
        )
    pub_get_calls = [
        call[0][0]
        for call in run.call_args_list
        if call[0][0][:3] == ["/usr/bin/flutter", "pub", "get"]
    ]
    assert not pub_get_calls


def test_validate_dart_project_ignores_warning_only_exit_code(tmp_path: Path) -> None:
    target = tmp_path / "lib" / "generated" / "screen_layout.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.side_effect = [
            type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            type(
                "R",
                (),
                {
                    "returncode": 2,
                    "stdout": "warning - screen_layout.dart:1:1 - Unused import.",
                    "stderr": "",
                },
            )(),
        ]
        validate_dart_project(
            tmp_path,
            analyze_scope="generated_only",
            relative_paths=["lib/generated/screen_layout.dart"],
        )


def test_validate_dart_project_raises_on_analyzer_errors(tmp_path: Path) -> None:
    target = tmp_path / "lib" / "generated" / "screen_layout.dart"
    target.parent.mkdir(parents=True)
    target.write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.generator.validation._toolchain_executables",
            return_value=("/usr/bin/dart", "/usr/bin/flutter"),
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.side_effect = [
            type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
            type(
                "R",
                (),
                {
                    "returncode": 3,
                    "stdout": "error - screen_layout.dart:1:1 - Unterminated string literal.",
                    "stderr": "Unblock-File: Zone.Identifier.",
                },
            )(),
        ]
        with pytest.raises(GenerationError, match="flutter analyze"):
            validate_dart_project(
                tmp_path,
                analyze_scope="generated_only",
                relative_paths=["lib/generated/screen_layout.dart"],
            )


def test_strip_windows_zone_identifier_noise() -> None:
    noisy = (
        "Unblock-File: cannot find path "
        "'E:\\\\flutter\\\\bin\\\\internal\\\\update_engine_version.ps1:Zone.Identifier'.\n"
    )
    assert _strip_windows_zone_identifier_noise(noisy) == ""


def test_analyze_failure_details_prefers_stdout() -> None:
    result = type(
        "R",
        (),
        {
            "returncode": 3,
            "stdout": "error - file.dart:1:1 - Expected token.",
            "stderr": "Unblock-File: Zone.Identifier.",
        },
    )()
    details = _analyze_failure_details(result)
    assert "Expected token" in details
    assert "Unblock-File" not in details


def test_analyze_has_errors() -> None:
    assert _analyze_has_errors("error - file.dart:1:1 - Expected token.")
    assert not _analyze_has_errors("warning - file.dart:1:1 - Unused import.")


def test_validate_dart_project_uses_flutter_sdk_env(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    (lib / "main.dart").write_text("void main() {}", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.dev.flutter_sdk.resolve_dart_executable",
            return_value="/sdk/dart",
        ) as resolve_dart,
        patch(
            "figma_flutter_agent.dev.flutter_sdk.resolve_flutter_executable",
            return_value="/sdk/flutter",
        ),
        patch(
            "figma_flutter_agent.generator.codegen.shutil.which",
            return_value="/sdk/flutter",
        ),
        _patch_toolchain_subprocess() as run,
    ):
        run.return_value.returncode = 0
        validate_dart_project(tmp_path, analyze_scope="project", flutter_sdk="/opt/flutter")
    resolve_dart.assert_called()
    assert resolve_dart.call_args.kwargs["sdk_root"] == "/opt/flutter"
