"""Tests for repair plan target validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.plan_validate import (
    collect_invalid_plan_targets,
    enrich_plan_row_overflow_targets,
    enrich_plan_writeback_targets,
    resolve_compiler_target,
    sanitize_plan_forbidden_target_overlap,
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
                "lawId": "row-overflow-law",
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
                "lawId": "row-overflow-law",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [rel],
                "tests": ["src/figma_flutter_agent/tests/generator/layout/test_flex_emitter.py"],
            },
        ],
    }
    validate_plan(plan, worktree=worktree)
    assert plan["steps"][0]["tests"] == ["tests/generator/layout/test_flex_emitter.py"]


def test_enrich_plan_row_overflow_targets_adds_flex_policy_row(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    emit_dir = (
        worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "widgets" / "emit"
    )
    row_dir = worktree / "src" / "figma_flutter_agent" / "generator" / "layout" / "flex_policy"
    emit_dir.mkdir(parents=True)
    row_dir.mkdir(parents=True)
    flex_rel = "src/figma_flutter_agent/generator/layout/widgets/emit/flex.py"
    row_rel = "src/figma_flutter_agent/generator/layout/flex_policy/row.py"
    (worktree / flex_rel).write_text("# flex\n", encoding="utf-8")
    (worktree / row_rel).write_text("# row policy\n", encoding="utf-8")
    test_rel = "tests/test_flex_emitter.py"
    _seed_worktree_test(worktree, test_rel)
    plan = {
        "step": "plan",
        "steps": [
            {
                "order": 2,
                "lawId": "FlexRowOverflowLaw",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [flex_rel],
                "tests": [test_rel],
            }
        ],
    }
    diagnose = {
        "laws": [
            {
                "id": "FlexRowOverflowLaw",
                "lawText": "RenderFlex overflow on divider row gaps",
                "layer": "emit",
            }
        ]
    }
    assert enrich_plan_row_overflow_targets(plan, diagnose_payload=diagnose, worktree=worktree)
    assert row_rel in plan["steps"][0]["targetFiles"]
    validate_plan(plan, worktree=worktree, diagnose_payload=diagnose)


def test_plan_test_path_recognizes_test_file_key() -> None:
    from figma_flutter_agent.dev.opencode.scope_enforcement import _plan_test_path

    path = _plan_test_path(
        {
            "testFile": "tests/generator/flex_policy/test_row_overflow.py",
            "regressionProof": "overflow regression",
        }
    )
    assert path == "tests/generator/flex_policy/test_row_overflow.py"


def test_enrich_plan_writeback_targets_adds_pipeline_companions(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    write_dir = worktree / "src" / "figma_flutter_agent" / "stages"
    commit_dir = worktree / "src" / "figma_flutter_agent" / "pipeline" / "run"
    result_dir = worktree / "src" / "figma_flutter_agent" / "pipeline"
    write_dir.mkdir(parents=True)
    commit_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    write_rel = "src/figma_flutter_agent/stages/write.py"
    commit_rel = "src/figma_flutter_agent/pipeline/run/commit.py"
    result_rel = "src/figma_flutter_agent/pipeline/result.py"
    (worktree / write_rel).write_text("# write\n", encoding="utf-8")
    (worktree / commit_rel).write_text("# commit\n", encoding="utf-8")
    (worktree / result_rel).write_text("# result\n", encoding="utf-8")
    plan = {
        "step": "plan",
        "steps": [
            {
                "order": 2,
                "lawId": "WritebackCaptureLaw",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [write_rel],
                "tests": [
                    {
                        "testFile": "tests/stages/test_write_rollback_on_capture_fail.py",
                    }
                ],
            }
        ],
    }
    diagnose = {
        "laws": [
            {
                "id": "WritebackCaptureLaw",
                "lawText": "writeback committed before capture verification rollback",
                "layer": "capture",
            }
        ]
    }
    assert enrich_plan_writeback_targets(plan, diagnose_payload=diagnose, worktree=worktree)
    targets = plan["steps"][0]["targetFiles"]
    assert write_rel in targets
    assert commit_rel in targets
    assert result_rel in targets
    validate_plan(plan, worktree=worktree, diagnose_payload=diagnose)
    tests = plan["steps"][0]["tests"]
    assert "tests/stages/test_write_rollback_on_capture_fail.py" in (
        tests if isinstance(tests[0], str) else [t.get("path") or t.get("testFile") for t in tests]
    )


def test_sanitize_plan_forbidden_target_overlap_removes_duplicates() -> None:
    plan = {
        "steps": [
            {
                "order": 1,
                "actionKind": "CODE_CHANGE",
                "lawId": "LAW-WRITE",
                "targetFiles": [
                    "src/figma_flutter_agent/stages/write.py",
                    "src/figma_flutter_agent/pipeline/run/commit.py",
                ],
                "forbiddenFiles": [
                    "lib/**",
                    "src/figma_flutter_agent/pipeline/run/commit.py",
                ],
                "tests": ["tests/test_debug_pipeline_models.py"],
            }
        ]
    }
    assert sanitize_plan_forbidden_target_overlap(plan)
    forbidden = plan["steps"][0]["forbiddenFiles"]
    assert forbidden == ["lib/**"]
    assert "src/figma_flutter_agent/pipeline/run/commit.py" not in forbidden


def test_validate_plan_coerces_string_order(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    rel = "src/figma_flutter_agent/generator/layout/common.py"
    (worktree / rel).parent.mkdir(parents=True)
    (worktree / rel).write_text("# ok\n", encoding="utf-8")
    test_rel = _seed_worktree_test(worktree)
    plan = {
        "step": "plan",
        "steps": [
            {
                "order": "1",
                "lawId": "law_a",
                "actionKind": "CODE_CHANGE",
                "targetFiles": [rel],
                "tests": [test_rel],
            }
        ],
    }
    validate_plan(plan, worktree=worktree)
    assert plan["steps"][0]["order"] == 1


def test_validate_plan_rejects_invented_law_id(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    rel = "src/figma_flutter_agent/generator/layout/common.py"
    (worktree / rel).parent.mkdir(parents=True)
    (worktree / rel).write_text("# ok\n", encoding="utf-8")
    plan = _plan_with_targets([rel], worktree=worktree)
    diagnose = {"laws": [{"id": "real-law"}]}
    with pytest.raises(FigmaFlutterError, match="not declared in diagnose.laws"):
        validate_plan(plan, worktree=worktree, diagnose_payload=diagnose)
