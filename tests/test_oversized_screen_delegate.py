"""Oversized screen → layout delegate and dart format skip heuristics."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.dart.project_validation import (
    _filter_dart_format_targets_by_size,
)
from figma_flutter_agent.generator.planned.reconcile import (
    _LARGE_PLANNED_DART_BYTES,
    force_oversized_feature_screens_to_layout,
)


def test_force_oversized_feature_screens_to_layout() -> None:
    padding = "x" * (_LARGE_PLANNED_DART_BYTES + 100)
    screen_path = "lib/features/background/background_screen.dart"
    layout_path = "lib/generated/background_layout.dart"
    planned = {
        screen_path: f"class BackgroundScreen extends StatelessWidget {{ {padding} Stack(children: []) }}",
        layout_path: (
            "class BackgroundLayout extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => Stack(children: []);\n"
            "}\n"
        ),
    }
    updated = force_oversized_feature_screens_to_layout(
        planned,
        package_name="demo_app",
    )
    screen = updated[screen_path]
    assert "GeneratedScreenShell(child: const BackgroundLayout())" in screen
    assert len(screen.encode("utf-8")) < _LARGE_PLANNED_DART_BYTES
    assert padding not in screen
    assert len(screen.encode("utf-8")) < _LARGE_PLANNED_DART_BYTES


def test_filter_dart_format_targets_by_size_skips_huge_valid_file(tmp_path: Path) -> None:
    huge = tmp_path / "lib" / "generated" / "big_layout.dart"
    huge.parent.mkdir(parents=True)
    huge.write_text(
        "class Foo extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext c) => const SizedBox();\n"
        "}\n" + ("// pad\n" * 20_000),
        encoding="utf-8",
    )
    assert huge.stat().st_size >= 100_000
    filtered = _filter_dart_format_targets_by_size(tmp_path, [str(huge)])
    assert filtered == []
