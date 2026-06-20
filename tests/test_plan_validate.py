"""Tests for repair plan target validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.plan_validate import (
    collect_invalid_plan_targets,
    validate_plan,
)
from figma_flutter_agent.errors import FigmaFlutterError


def _plan_with_targets(targets: list[str]) -> dict:
    return {
        "step": "plan",
        "steps": [
            {
                "order": 1,
                "lawId": "law_a",
                "actionKind": "CODE_CHANGE",
                "targetFiles": targets,
                "tests": ["tests/test_debug_pipeline_models.py"],
            }
        ],
    }


def test_validate_plan_rejects_missing_compiler_targets(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    compiler_root = worktree / "src" / "figma_flutter_agent" / "generator" / "layout"
    compiler_root.mkdir(parents=True)
    (compiler_root / "common.py").write_text("# ok\n", encoding="utf-8")
    plan = _plan_with_targets(
        [
            "src/figma_flutter_agent/lib/emitter/row_emitter.dart",
            "src/figma_flutter_agent/generator/layout/common.py",
        ]
    )
    invalid = collect_invalid_plan_targets(plan, worktree=worktree)
    assert "src/figma_flutter_agent/lib/emitter/row_emitter.dart" in invalid
    with pytest.raises(FigmaFlutterError, match="plan blocked"):
        validate_plan(plan, worktree=worktree)


def test_validate_plan_accepts_existing_python_targets(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    target = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "widgets" / "emit"
    target.mkdir(parents=True)
    rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    (worktree / rel).write_text("# flex\n", encoding="utf-8")
    plan = _plan_with_targets([rel])
    validate_plan(plan, worktree=worktree)
