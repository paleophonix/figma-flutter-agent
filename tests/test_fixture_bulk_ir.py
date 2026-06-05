"""Bulk IR guardrail validation for offline screen fixtures."""

from __future__ import annotations

import pytest

from figma_flutter_agent.fixtures.bulk_ir_validate import validate_all_fixture_screens
from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.llm.repair_apply import apply_repair_patches
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    FlutterRepairIrPatch,
    FlutterRepairPatchResponse,
    NodeType,
    WidgetIrOverrides,
)
from figma_flutter_agent.stages.llm_repair import (
    _repair_generation_unchanged,
    _snapshot_generation,
)


@pytest.mark.parametrize("screen_id", ["sign_up_and_sign_in", "reminders", "music_v2", "music_v2_ru_dirty"])
def test_fixture_screen_passes_ir_guardrails(screen_id: str) -> None:
    results = validate_all_fixture_screens(screen_ids=[screen_id])
    assert len(results) == 1
    assert results[0].ok, results[0].error


def test_all_manifest_screens_structure_only_without_guards() -> None:
    results = validate_all_fixture_screens(apply_guards=False, validate=True)
    failed = [item for item in results if not item.ok]
    assert not failed, "; ".join(f"{item.screen_id}: {item.error}" for item in failed)


def test_all_manifest_screens_listed() -> None:
    manifest = load_screens_manifest()
    results = validate_all_fixture_screens()
    assert len(results) == len(manifest.screens)
    failed = [item for item in results if not item.ok]
    assert not failed, "; ".join(f"{item.screen_id}: {item.error}" for item in failed)


def test_repair_generation_unchanged_detects_ir_patch() -> None:
    root = CleanDesignTreeNode(
        id="1",
        name="Col",
        type=NodeType.COLUMN,
        children=[
            CleanDesignTreeNode(id="2", name="T", type=NodeType.TEXT, text="Hi"),
        ],
    )
    before = FlutterGenerationResponse(screen_ir=default_screen_ir(root))
    before_snap = _snapshot_generation(before)
    outcome = apply_repair_patches(
        before,
        FlutterRepairPatchResponse(
            ir_patches=[
                FlutterRepairIrPatch(
                    figmaId="2",
                    overrides=WidgetIrOverrides(text="Bye"),
                )
            ],
        ),
        clean_tree=root,
        use_screen_ir=True,
    )
    assert not _repair_generation_unchanged(
        before_snap,
        outcome.generation,
        use_screen_ir=True,
    )


def test_repair_generation_unchanged_ignores_stale_screen_code_under_ir() -> None:
    root = CleanDesignTreeNode(id="1", name="R", type=NodeType.ROW, children=[])
    generation = FlutterGenerationResponse(
        screen_ir=default_screen_ir(root),
        screen_code="stale dart body",
    )
    snap = _snapshot_generation(generation)
    clone = FlutterGenerationResponse(
        screen_ir=default_screen_ir(root),
        screen_code="different stale dart",
    )
    assert _repair_generation_unchanged(snap, clone, use_screen_ir=True)
