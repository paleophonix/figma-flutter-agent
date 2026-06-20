"""L6 environment placeholder bindings for OpenCode repair prompts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.plan_validate import compiler_path_catalog
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repo_map import (
    compact_repo_map_json,
    deep_repo_map_json,
    symptom_surface_hints_json,
)
from figma_flutter_agent.dev.opencode.schema_gate import load_step_schema
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_l6_bindings(
    *,
    step: str,
    board: str,
    workspace: RepairWorkspace,
    feature: str,
    project_label: str,
    run_context: dict[str, Any],
    reasoning_chain_json: str,
    chain: ReasoningChain,
    plan: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Build single-brace placeholder values for ``l6-environment.tpl``."""
    worktree = workspace.worktree.as_posix()
    debug_root = workspace.debug_mirror.as_posix()
    schema_path = (
        Path("src/figma_flutter_agent/dev/opencode/schemas") / f"{step}.schema.json"
    ).as_posix()
    state_dir = workspace.state_dir
    bindings: dict[str, str] = {
        "worktree": worktree,
        "project": project_label,
        "feature": feature,
        "case_mode": str(run_context.get("case_mode") or ""),
        "agent_board": board,
        "debug_root": debug_root,
        "manifest_path": workspace.manifest_path.as_posix(),
        "run_manifest_path": str(
            (workspace.debug_mirror / "run_manifest.json").as_posix()
        ),
        "schema_path": schema_path,
        "output_path": str((state_dir / f"{step}.json").as_posix()),
        "detail_log_path": str((state_dir / f"{step}.detail.log").as_posix()),
        "run_context_json": _json_text(run_context),
        "reasoning_chain_json": reasoning_chain_json,
        "repo_map_compact_json": compact_repo_map_json(board=board),
        "repo_map_deep_json": deep_repo_map_json(chain),
        "symptom_surface_hints_json": symptom_surface_hints_json(chain),
        "compiler_path_catalog_json": _json_text(compiler_path_catalog(workspace.worktree)),
        "inspect_preflight_json": _json_text(run_context.get("inspect_preflight") or {}),
        "plan_step_orders": _json_text(
            [item.get("order") for item in (plan or {}).get("steps") or [] if isinstance(item, dict)]
        ),
        "vision_bundle_dir": debug_root,
        "vision_bundle_json": "{}",
        "diff_stats_json": "{}",
        "semantic_hints_json": "{}",
        "check_summary_json": _json_text(chain.steps.get("check") or {}),
        "analyze_errors_json": _json_text(run_context.get("analyze_errors") or []),
        "allowed_edit_files_json": _json_text(run_context.get("allowed_edit_files") or []),
        "frozen_context_json": _json_text(run_context.get("frozen_context") or {}),
        "fix_attempt": str(run_context.get("fix_attempt") or 1),
        "max_fix_attempts": str(run_context.get("max_fix_attempts") or 1),
        "review_rubric_json": "{}",
        "capture_verdict_json": _json_text(chain.steps.get("capture") or {}),
        "symptom_law_matrix_json": "{}",
        "run_manifest_summary_json": _json_text(run_context.get("run_manifest") or {}),
        "review_gate_snapshot_json": "{}",
        "scope_diff_summary_json": "{}",
        "review_summary_json": _json_text(chain.steps.get("review") or {}),
        "task_completed_gate_snapshot_json": "{}",
        "summarize_rubric_json": "{}",
        "law_label_map_ru_json": "{}",
        "ticket_summary_path": str((workspace.repair_root / "reports" / "ticket.md").as_posix()),
        "dev_summary_path": str((workspace.repair_root / "reports" / "dev.md").as_posix()),
        "data_context_path": str((workspace.repair_root / "data_context.json").as_posix()),
    }
    _ = load_step_schema(step)
    return bindings


def render_l6_template(template: str, bindings: dict[str, str]) -> str:
    """Replace ``{placeholder}`` tokens in an L6 environment template."""
    rendered = template
    for key, value in bindings.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered
