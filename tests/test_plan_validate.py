"""Tests for repair plan target validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.plan_validate import (
    collect_invalid_plan_targets,
    resolve_compiler_target,
    validate_plan,
)
from figma_flutter_agent.errors import FigmaFlutterError


def _seed_worktree_test(worktree: Path, rel: str = "tests/test_debug_pipeline_models.py") -> str:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# stub\n", encoding="utf-8")
    return rel


def _plan_with_targets(targets: list[str], *, worktree: Path | None = None) -> dict:
    test_path = "tests/test_debug_pipeline_models.py"
    if worktree is not None:
        _seed_worktree_test(worktree, test_path)
    return {
        "step": "plan",
        "steps": [
            {
                "order": 1,
                "lawId": "law_a",
                "actionKind": "CODE_CHANGE",
                "targetFiles": targets,
                "tests": [test_path],
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
        ],
        worktree=worktree,
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
    plan = _plan_with_targets([rel], worktree=worktree)
    validate_plan(plan, worktree=worktree)


def test_resolve_legacy_module_path_to_package_init(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    package = worktree / "src" / "figma_flutter_agent" / "generator" / "ir" / "validate"
    package.mkdir(parents=True)
    init_rel = "src/figma_flutter_agent/generator/ir/validate/__init__.py"
    (worktree / init_rel).write_text("# validate package\n", encoding="utf-8")
    legacy = "src/figma_flutter_agent/generator/ir/validate.py"
    assert resolve_compiler_target(worktree, legacy) == init_rel
    plan = _plan_with_targets([legacy], worktree=worktree)
    validate_plan(plan, worktree=worktree)
    assert plan["steps"][0]["targetFiles"] == [init_rel]


def test_compiler_path_catalog_includes_ir_validate_package() -> None:
    from figma_flutter_agent.dev.opencode.plan_validate import compiler_path_catalog

    catalog = compiler_path_catalog(Path(__file__).resolve().parents[1])
    validate_paths = [path for path in catalog if "/generator/ir/validate/" in path]
    assert validate_paths


def test_validate_plan_accepts_executive_blocked_plan(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    plan = {
        "step": "plan",
        "steps": [],
        "blocked": True,
        "blockedItems": [
            {
                "lawId": "law-flex-overflow",
                "reason": "REPAIR_NOOP: no file edits in prior repair cycle",
                "missing_evidence": "none",
            }
        ],
        "notes": "No actionable steps after repair noop.",
    }
    validate_plan(plan, worktree=worktree)


def test_validate_plan_accepts_report_only_without_tests(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    target = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "widgets" / "emit"
    target.mkdir(parents=True)
    rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    (worktree / rel).write_text("# flex\n", encoding="utf-8")
    test_rel = "tests/test_flex_overflow_guards.py"
    _seed_worktree_test(worktree, test_rel)
    plan = {
        "step": "plan",
        "steps": [
            {
                "order": 1,
                "lawId": "forensic-writeback-identity-mismatch",
                "actionKind": "REPORT_ONLY",
                "repairClass": "REPORT_ONLY",
                "targetFiles": [],
                "tests": [],
            },
            {
                "order": 2,
                "lawId": "emitter-flex-constraint-overflow-law",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [rel],
                "tests": [test_rel],
            },
        ],
    }
    validate_plan(plan, worktree=worktree)


def test_validate_plan_rejects_invalid_test_paths(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    target = worktree / "src" / "figma_flutter_agent" / "generator" / "layout"
    target.mkdir(parents=True)
    rel = "src/figma_flutter_agent/generator/layout/common.py"
    (worktree / rel).write_text("# ok\n", encoding="utf-8")
    plan = _plan_with_targets([rel], worktree=worktree)
    plan["steps"][0]["tests"] = ["sandbox/not_a_test.py"]
    with pytest.raises(FigmaFlutterError, match="tests\\[\\] must name tests"):
        validate_plan(plan, worktree=worktree)


def test_validate_plan_normalizes_hallucinated_test_prefix(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    target = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "widgets" / "emit"
    target.mkdir(parents=True)
    rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    (worktree / rel).write_text("# flex\n", encoding="utf-8")
    plan = {
        "step": "plan",
        "steps": [
            {
                "order": 2,
                "lawId": "emitter-flex-constraint-overflow-law",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [rel],
                "tests": [
                    "src/figma_flutter_agent/tests/generator/layout/test_flex_emitter.py"
                ],
            },
        ],
    }
    validate_plan(plan, worktree=worktree)
    assert plan["steps"][0]["tests"] == ["tests/generator/layout/test_flex_emitter.py"]
