"""Runtime geometry gate after analyze passes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.generator.validation import PlannedAnalyzeOutcome
from figma_flutter_agent.stages.runtime_geometry_check import evaluate_runtime_geometry
from figma_flutter_agent.validation.geometry_metrics import GeometryTierThresholds


def test_evaluate_runtime_geometry_detects_shift(tmp_path: Path) -> None:
    tree = load_layout_tree("sign_up_and_sign_in")
    keys_dir = tmp_path / "test" / "goldens"
    keys_dir.mkdir(parents=True)
    payload = {
        "1_3972": {"left": 200.0, "top": 50.0, "width": 74.0, "height": 17.0},
    }
    (keys_dir / "sign_up_and_sign_in_figma_keys.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    class _Settings:
        flutter_sdk = None

        class agent:
            class generation:
                runtime_geometry_gate = True
                runtime_geometry_min_iou = 0.95
                runtime_geometry_capture_if_missing = False

    errors, feedback = evaluate_runtime_geometry(
        clean_tree=tree,
        planned_files={},
        feature_name="sign_up_and_sign_in",
        project_dir=tmp_path,
        settings=_Settings(),
        min_iou=0.95,
        tier_thresholds=GeometryTierThresholds(),
        use_tier_thresholds=True,
        capture_if_missing=False,
    )
    assert errors
    assert "GIoU" in feedback


def test_planned_analyze_outcome_replace_for_geometry_gate() -> None:
    outcome = PlannedAnalyzeOutcome(
        skipped=False,
        passed=True,
        detail="ok",
        errors=(),
    )
    patched = replace(
        outcome,
        passed=False,
        errors=("ERROR: Widget missing",),
        detail="runtime_geometry_gate",
    )
    assert not patched.passed
    assert patched.detail == "runtime_geometry_gate"
