"""Tests for plan target registry and CREATE validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.plan_target_registry import enrich_plan_targets
from figma_flutter_agent.dev.opencode.plan_validate import (
    collect_invalid_plan_targets,
    validate_plan,
)
from figma_flutter_agent.errors import FigmaFlutterError


def test_registry_appends_row_companion_for_typed_law_id() -> None:
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "lawId": "FlexRowOverflowLaw",
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
                ],
                "tests": ["tests/test_flex.py"],
            }
        ]
    }
    diagnose = {
        "laws": [
            {
                "lawId": "FlexRowOverflowLaw",
                "layer": "emit",
            }
        ]
    }
    assert enrich_plan_targets(plan, diagnose_payload=diagnose) is True
    targets = plan["steps"][0]["targetFiles"]
    assert "src/figma_flutter_agent/generator/layout/flex_policy/row.py" in targets


def test_create_module_target_allowed_under_existing_package(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    pkg = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "flex_policy"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (worktree / "src" / "figma_flutter_agent" / "__init__.py").write_text("", encoding="utf-8")
    (worktree / "src" / "figma_flutter_agent" / "generator" / "__init__.py").write_text(
        "", encoding="utf-8"
    )
    (worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "__init__.py").write_text(
        "", encoding="utf-8"
    )

    plan = {
        "steps": [
            {
                "actionKind": "CREATE_MODULE",
                "lawId": "FlexRowOverflowLaw",
                "createTarget": True,
                "targetFiles": [
                    "src/figma_flutter_agent/generator/layout/flex_policy/row_overflow.py"
                ],
                "tests": ["tests/test_row_overflow.py"],
            }
        ]
    }
    invalid = collect_invalid_plan_targets(plan, worktree=worktree)
    assert "row_overflow.py" not in ",".join(invalid)


def test_random_src_path_still_invalid(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    worktree.mkdir()
    plan = {
        "steps": [
            {
                "actionKind": "CODE_CHANGE",
                "lawId": "X",
                "targetFiles": ["src/foo.py"],
                "tests": ["tests/test_x.py"],
            }
        ]
    }
    invalid = collect_invalid_plan_targets(plan, worktree=worktree)
    assert "src/foo.py" in invalid
