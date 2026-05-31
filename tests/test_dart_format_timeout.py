"""Per-file dart format timeout budgeting."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.validation import (
    _dart_format_file_targets,
    _dart_format_per_file_timeout,
    _run_dart_format_targets,
)


def test_small_file_uses_five_second_cap(tmp_path: Path) -> None:
    small = tmp_path / "lib" / "theme.dart"
    small.parent.mkdir(parents=True)
    small.write_text("const k = 1;\n", encoding="utf-8")
    timeout = _dart_format_per_file_timeout(str(small), file_count=1)
    assert timeout == 5.0


def test_large_planned_file_gets_extended_cap(tmp_path: Path) -> None:
    large = tmp_path / "lib" / "features" / "x" / "x_screen.dart"
    large.parent.mkdir(parents=True)
    large.write_text("x" * 60_000, encoding="utf-8")
    timeout = _dart_format_per_file_timeout(str(large), file_count=1)
    assert timeout == 20.0


def test_batch_timeout_scales_with_file_count() -> None:
    assert _dart_format_per_file_timeout("lib/a.dart", file_count=4) == 30.0
    assert _dart_format_per_file_timeout("lib/a.dart", file_count=12) == 60.0


def test_dart_format_file_targets_rejects_directories(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    dart_file = lib / "screen.dart"
    dart_file.write_text("void main() {}", encoding="utf-8")
    files = _dart_format_file_targets(tmp_path, [str(lib), str(dart_file)])
    assert files == [str(dart_file)]


def test_scoped_analyze_command_uses_dart_not_flutter() -> None:
    from figma_flutter_agent.generator.validation import _build_analyze_command

    command, label = _build_analyze_command(
        dart="/bin/dart",
        flutter="/bin/flutter",
        scope_path_list=True,
        dart_targets=[Path("lib/a.dart")],
        project_dir=Path("."),
    )
    assert command[0] == "/bin/dart"
    assert "flutter" not in command[0]
    assert label == "dart analyze (generated)"


def test_run_dart_format_skips_when_only_directory_given(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    outcome = _run_dart_format_targets(
        tmp_path,
        dart="/usr/bin/dart",
        format_target=[str(lib)],
    )
    assert outcome is None
