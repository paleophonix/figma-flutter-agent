"""Per-file dart format timeout budgeting."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.dart.project_validation import (
    _dart_format_batch_timeout,
    _dart_format_file_targets,
    _dart_format_per_file_timeout,
    _dart_format_single_file_timeout,
    _dart_source_is_minified,
    _filter_minified_layout_format_targets,
    _partition_format_targets_by_delimiters,
    _partition_format_targets_by_size,
    _run_dart_format_targets,
    expand_minified_dart_source,
    is_dart_analyze_timeout_detail,
)


def test_small_file_uses_six_second_cap(tmp_path: Path) -> None:
    small = tmp_path / "lib" / "theme.dart"
    small.parent.mkdir(parents=True)
    small.write_text("const k = 1;\n", encoding="utf-8")
    timeout = _dart_format_single_file_timeout(str(small))
    assert timeout == 6.0


def test_large_planned_file_gets_size_scaled_cap(tmp_path: Path) -> None:
    large = tmp_path / "lib" / "features" / "x" / "x_screen.dart"
    large.parent.mkdir(parents=True)
    large.write_text("x" * 60_000, encoding="utf-8")
    timeout = _dart_format_single_file_timeout(str(large))
    assert timeout == 12.0 + 60_000 / 3_500.0


def test_batch_timeout_uses_largest_file_in_set(tmp_path: Path) -> None:
    small = tmp_path / "lib" / "small.dart"
    large = tmp_path / "lib" / "large.dart"
    small.parent.mkdir(parents=True)
    small.write_text("const k = 1;\n", encoding="utf-8")
    large.write_text("x" * 60_000, encoding="utf-8")
    timeout = _dart_format_batch_timeout([str(small), str(large)])
    assert timeout == _dart_format_single_file_timeout(str(large)) + 2.0


def test_batch_timeout_scales_with_file_count_when_paths_unknown() -> None:
    assert _dart_format_per_file_timeout("lib/a.dart", file_count=4) == 26.0
    assert _dart_format_per_file_timeout("lib/a.dart", file_count=12) == 74.0


def test_partition_format_targets_by_size(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir(parents=True)
    small = lib / "theme.dart"
    large = lib / "layout.dart"
    small.write_text("const k = 1;\n", encoding="utf-8")
    large.write_text("x" * 60_000, encoding="utf-8")
    small_paths, large_paths = _partition_format_targets_by_size(
        [str(small), str(large)],
    )
    assert small_paths == [str(small)]
    assert large_paths == [str(large)]


def test_dart_format_file_targets_rejects_directories(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    dart_file = lib / "screen.dart"
    dart_file.write_text("void main() {}", encoding="utf-8")
    files = _dart_format_file_targets(tmp_path, [str(lib), str(dart_file)])
    assert files == [str(dart_file)]


def test_scoped_analyze_command_uses_dart_not_flutter() -> None:
    from figma_flutter_agent.generator.dart.project_validation import _build_analyze_command

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


def test_delimiter_gate_partitions_broken_targets(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir(parents=True)
    good = lib / "good.dart"
    bad = lib / "bad.dart"
    good.write_text("void main() {}\n", encoding="utf-8")
    bad.write_text("void main() {\n", encoding="utf-8")
    ready, broken = _partition_format_targets_by_delimiters(
        tmp_path,
        [str(good), str(bad)],
    )
    assert ready == [str(good)]
    assert broken == ("lib/bad.dart",)


def test_minified_generated_layout_is_detected(tmp_path: Path) -> None:
    layout = tmp_path / "lib" / "generated" / "screen_layout.dart"
    layout.parent.mkdir(parents=True)
    layout.write_text("void main() {}\n" + "x" * 5_000, encoding="utf-8")
    assert _dart_source_is_minified(str(layout))


def test_minified_widget_is_detected_outside_generated(tmp_path: Path) -> None:
    """A minified cluster widget (one 44k-char line) must be caught regardless of path."""
    widget = tmp_path / "lib" / "widgets" / "cluster0_widget.dart"
    widget.parent.mkdir(parents=True)
    widget.write_text("class C {}\n" + "y" * 44_000, encoding="utf-8")
    assert _dart_source_is_minified(str(widget))


def test_multiline_widget_is_not_minified(tmp_path: Path) -> None:
    widget = tmp_path / "lib" / "widgets" / "normal_widget.dart"
    widget.parent.mkdir(parents=True)
    widget.write_text("class C {\n  final int x = 1;\n}\n", encoding="utf-8")
    assert not _dart_source_is_minified(str(widget))


def test_filter_minified_layout_format_targets_skips_valid_minified(
    tmp_path: Path,
) -> None:
    layout = tmp_path / "lib" / "generated" / "screen_layout.dart"
    widget = tmp_path / "lib" / "widgets" / "cluster0_widget.dart"
    theme = tmp_path / "lib" / "theme" / "app_theme.dart"
    layout.parent.mkdir(parents=True)
    widget.parent.mkdir(parents=True)
    theme.parent.mkdir(parents=True)
    layout.write_text("void main() {}\n" + "x" * 5_000, encoding="utf-8")
    widget.write_text("class C {}\n" + "y" * 44_000, encoding="utf-8")
    theme.write_text("const k = 1;\n", encoding="utf-8")
    filtered = _filter_minified_layout_format_targets(
        tmp_path,
        [str(layout), str(widget), str(theme)],
    )
    assert filtered == [str(theme)]


def test_run_dart_format_skips_when_only_directory_given(tmp_path: Path) -> None:
    lib = tmp_path / "lib"
    lib.mkdir()
    outcome = _run_dart_format_targets(
        tmp_path,
        dart="/usr/bin/dart",
        format_target=[str(lib)],
    )
    assert outcome is None


def test_is_dart_analyze_timeout_detail_detects_subprocess_timeout() -> None:
    assert is_dart_analyze_timeout_detail("dart analyze (generated) (2/3) timed out after 120s")
    assert not is_dart_analyze_timeout_detail("dart analyze (generated) reported issues")


def test_expand_minified_dart_source_wraps_long_physical_lines() -> None:
    body = "return Column(children: [" + ", ".join(f"Text('{index}')" for index in range(800)) + "]);"
    expanded = expand_minified_dart_source(body)
    assert expanded != body
    assert max(len(line) for line in expanded.splitlines()) < len(body)
