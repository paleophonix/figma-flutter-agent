"""Tests for escalation-aware repair patch application."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_apply import (
    apply_repair_patches,
    repair_patch_uses_forbidden_hunks,
)
from figma_flutter_agent.schemas import (
    FlutterGenerationResponse,
    FlutterRepairPatch,
    FlutterRepairPatchResponse,
)


def test_repair_patch_uses_forbidden_hunks_detects_search_replace() -> None:
    assert repair_patch_uses_forbidden_hunks("<<<<<<< SEARCH\nfoo\n=======\nbar\n>>>>>>>")
    assert repair_patch_uses_forbidden_hunks("SEARCH\nold\nREPLACE\nnew")
    assert not repair_patch_uses_forbidden_hunks(
        "@@ -1,1 +1,1 @@\n-old\n+new\n"
    )


def test_apply_repair_patches_rejects_search_replace() -> None:
    current = FlutterGenerationResponse(
        screen_code="class _S extends State<S> { @override Widget build(BuildContext c) => SizedBox(); }",
        extracted_widgets=[],
    )
    patch = FlutterRepairPatchResponse(
        patches=[
            FlutterRepairPatch(
                target="screenCode",
                code="SEARCH\nbroken\nREPLACE\nalso broken",
            )
        ]
    )
    outcome = apply_repair_patches(current, patch)
    assert outcome.patches_applied == 0
    assert outcome.generation.screen_code == current.screen_code


def test_apply_repair_patches_applies_unified_diff_to_screen() -> None:
    current = FlutterGenerationResponse(
        screen_code="line one\nline two\nline three\n",
        extracted_widgets=[],
    )
    diff = (
        "@@ -1,3 +1,3 @@\n"
        " line one\n"
        "-line two\n"
        "+line TWO\n"
        " line three\n"
    )
    patch = FlutterRepairPatchResponse(
        patches=[FlutterRepairPatch(target="screenCode", code=diff)]
    )
    outcome = apply_repair_patches(
        current,
        patch,
        base_sources={"lib/features/demo/demo_screen.dart": current.screen_code},
        target_planned_paths={("screenCode", None): "lib/features/demo/demo_screen.dart"},
    )
    assert outcome.patches_applied == 1
    assert "line TWO" in outcome.generation.screen_code


def test_build_repair_user_payload_unified_diff_mode() -> None:
    from figma_flutter_agent.llm.repair import build_repair_user_payload
    from figma_flutter_agent.llm.repair_scope import RepairScope, RepairTarget

    scope = RepairScope(
        targets=(
            RepairTarget(
                target="screenCode",
                widget_name=None,
                code="x",
                planned_path="lib/features/sign_in/sign_in_screen.dart",
                errors=("err",),
                planned_excerpt="1: x",
            ),
        )
    )
    payload = build_repair_user_payload(
        feature_name="sign_in",
        scope=scope,
        analyze_errors=["err"],
        escalation_level=3,
    )
    assert "unified_diff" in payload
