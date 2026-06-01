"""Tests for scoped analyze repair helpers."""

from __future__ import annotations

from figma_flutter_agent.generator.ir_tree import default_screen_ir
from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.llm.repair_scope import (
    build_repair_scope,
    format_repair_attempt_record,
    parse_analyze_error_locations,
    repair_scope_planned_paths,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    FlutterGenerationResponse,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
    NodeType,
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


def test_build_repair_scope_uses_screen_ir_target_when_enabled() -> None:
    root = CleanDesignTreeNode(id="1", name="Root", type=NodeType.COLUMN, children=[])
    generation = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        screen_ir=default_screen_ir(root),
    )
    planned = {"lib/features/demo/demo_screen.dart": "class DemoScreen {}"}
    scope = build_repair_scope(
        feature_name="demo",
        planned_files=planned,
        current_generation=generation,
        analyze_errors=["error - lib/features/demo/demo_screen.dart:10:4 - Expected ';'."],
        use_screen_ir=True,
    )
    assert len(scope.targets) == 1
    assert scope.targets[0].target == "screenIr"
    assert scope.screen_included is True
    assert "figmaId" in scope.targets[0].code


def test_repair_scope_planned_paths_normalizes_slashes() -> None:
    scope = build_repair_scope(
        feature_name="demo",
        planned_files={"lib/widgets/foo.dart": "class Foo {}"},
        current_generation=FlutterGenerationResponse(
            screen_code="class DemoScreen {}",
            extracted_widgets=[ExtractedWidget(widget_name="Foo", code="class Foo {}")],
        ),
        analyze_errors=["error - lib/widgets/foo.dart:1:1 - x"],
    )
    paths = repair_scope_planned_paths(scope)
    assert paths == frozenset({"lib/widgets/foo.dart"})


def test_apply_repair_patches_updates_only_patched_widget() -> None:
    current = FlutterGenerationResponse(
        screen_code="class DemoScreen {}",
        extracted_widgets=[
            ExtractedWidget(widget_name="Logo", code="class Logo {}"),
            ExtractedWidget(widget_name="RelaxIllustration", code="class RelaxIllustration { Row() }"),
        ],
    )
    diff = (
        "@@ -1,1 +1,1 @@\n"
        "-class RelaxIllustration { Row() }\n"
        "+class RelaxIllustration { Stack() }\n"
    )
    outcome = apply_repair_patches(
        current,
        FlutterRepairPatchResponse(
            patches=[
                FlutterRepairPatch(
                    target="extractedWidget",
                    widget_name="RelaxIllustration",
                    code=diff,
                )
            ]
        ),
        base_sources={
            "lib/widgets/relax_illustration.dart": "class RelaxIllustration { Row() }",
        },
        target_planned_paths={
            ("extractedWidget", "RelaxIllustration"): "lib/widgets/relax_illustration.dart",
        },
    )
    patched = outcome.generation
    assert outcome.patches_applied == 1
    assert patched.screen_code == current.screen_code
    assert patched.extracted_widgets[0].code == "class Logo {}"
    assert "Stack" in patched.extracted_widgets[1].code


def test_format_repair_attempt_record_allows_null_screen_code() -> None:
    record = format_repair_attempt_record(
        attempt=4,
        patch_codes=[("screenCode", None, None)],
    )
    assert "Attempt 4 (failed):" in record
    assert "(no patch body)" in record
