"""Tests for scoped analyze repair helpers."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.llm.repair_scope import build_repair_scope, parse_analyze_error_locations
from figma_flutter_agent.schemas import (
    ExtractedWidget,
    FlutterGenerationResponse,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
)


def test_parse_analyze_error_locations() -> None:
    errors = ["error - lib/widgets/logo.dart:12:4 - Undefined name 'x'."]
    locations = parse_analyze_error_locations(errors)
    assert len(locations) == 1
    assert locations[0].file_path == "lib/widgets/logo.dart"
    assert locations[0].line == 12


def test_parse_format_error_absolute_temp_path() -> None:
    errors = [
        "line 32, column 4 of c:/Users/me/AppData/Local/Temp/"
        "figma-flutter-spec23-abc/analyze_check/lib/widgets/group_widget.dart: "
        "Expected to find '}'."
    ]
    locations = parse_analyze_error_locations(errors)
    assert len(locations) == 1
    assert locations[0].line == 32


def test_build_repair_scope_maps_absolute_widget_path() -> None:
    generation = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        extracted_widgets=[
            ExtractedWidget(widget_name="GroupWidget", code="class GroupWidget {"),
        ],
    )
    planned = {
        "lib/features/demo/demo_screen.dart": "class DemoScreen {}",
        "lib/widgets/group_widget.dart": "class GroupWidget {",
    }
    format_error = (
        "line 32, column 4 of c:/Users/me/AppData/Local/Temp/"
        "figma-flutter-spec/analyze_check/lib/widgets/group_widget.dart: "
        "Expected to find '}'."
    )
    scope = build_repair_scope(
        feature_name="demo",
        planned_files=planned,
        current_generation=generation,
        analyze_errors=[format_error],
    )
    assert len(scope.targets) == 1
    assert scope.targets[0].widget_name == "GroupWidget"
    assert scope.targets[0].planned_path == "lib/widgets/group_widget.dart"
    assert scope.screen_included is False


def test_build_repair_scope_targets_only_failed_widget() -> None:
    generation = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        extracted_widgets=[
            ExtractedWidget(widget_name="Logo", code="class Logo {}"),
            ExtractedWidget(widget_name="RelaxIllustration", code="class RelaxIllustration {}"),
        ],
    )
    planned = {
        "lib/features/demo/demo_screen.dart": "import ...\nclass DemoScreen {}",
        "lib/widgets/logo.dart": "class Logo {}",
        "lib/widgets/relax_illustration.dart": "class RelaxIllustration { Row(...) }",
    }
    scope = build_repair_scope(
        feature_name="demo",
        planned_files=planned,
        current_generation=generation,
        analyze_errors=["error - lib/widgets/relax_illustration.dart:76:18 - overflow"],
    )
    assert len(scope.targets) == 1
    assert scope.targets[0].widget_name == "RelaxIllustration"
    assert scope.unchanged_widget_names == ("Logo",)
    assert "Row" in scope.targets[0].planned_excerpt or scope.targets[0].planned_excerpt == ""


def test_apply_repair_patches_updates_only_patched_widget() -> None:
    current = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        extracted_widgets=[
            ExtractedWidget(widget_name="Logo", code="class Logo {}"),
            ExtractedWidget(widget_name="RelaxIllustration", code="class RelaxIllustration { Row() }"),
        ],
    )
    patched = apply_repair_patches(
        current,
        FlutterRepairPatchResponse(
            patches=[
                FlutterRepairPatch(
                    target="extractedWidget",
                    widget_name="RelaxIllustration",
                    code="class RelaxIllustration { Stack() }",
                )
            ]
        ),
    )
    assert patched.screen_code == current.screen_code
    assert patched.extracted_widgets[0].code == "class Logo {}"
    assert "Stack" in patched.extracted_widgets[1].code
