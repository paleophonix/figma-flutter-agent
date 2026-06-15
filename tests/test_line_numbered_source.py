"""Tests for repair line-number injection and stripping."""

from __future__ import annotations

from figma_flutter_agent.llm.line_numbered_source import (
    format_line_numbered_source,
    strip_line_number_markers,
    strip_line_number_markers_from_diff,
)
from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.schemas import (
    FlutterGenerationResponse,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
)


def test_format_line_numbered_source_uses_colon_prefix() -> None:
    numbered = format_line_numbered_source("void main() {\n  runApp();\n}")
    assert "1: void main() {" in numbered
    assert "2:   runApp();" in numbered


def test_strip_line_number_markers_removes_colon_and_legacy_pipe() -> None:
    source = "1: class A {}\n002| class B {}"
    assert strip_line_number_markers(source) == "class A {}\nclass B {}"


def test_strip_line_number_markers_from_diff() -> None:
    diff = "@@ -1,2 +1,2 @@\n 1: line one\n-2: line two\n+2: line TWO\n"
    cleaned = strip_line_number_markers_from_diff(diff)
    assert "1: line" not in cleaned
    assert "-line two" in cleaned
    assert "+line TWO" in cleaned


def test_apply_repair_patches_strips_markers_from_diff_hunks() -> None:
    current = FlutterGenerationResponse(
        screen_code="line one\nline two\n",
        extracted_widgets=[],
    )
    diff = "@@ -1,2 +1,2 @@\n 1: line one\n-2: line two\n+2: line TWO\n"
    outcome = apply_repair_patches(
        current,
        FlutterRepairPatchResponse(patches=[FlutterRepairPatch(target="screenCode", code=diff)]),
        base_sources={"lib/features/demo/demo_screen.dart": current.screen_code},
        target_planned_paths={("screenCode", None): "lib/features/demo/demo_screen.dart"},
    )
    assert outcome.patches_applied == 1
    assert "line TWO" in outcome.generation.screen_code
    assert "line two" not in outcome.generation.screen_code
    assert "1:" not in outcome.generation.screen_code
