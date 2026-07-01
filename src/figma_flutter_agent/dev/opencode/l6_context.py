"""L6 environment placeholder bindings for OpenCode repair prompts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.l6_allowlist import l6_binding_keys_for
from figma_flutter_agent.dev.opencode.l6_bindings import (
    build_review_gate_snapshot,
    build_scope_diff_summary,
    build_symptom_law_matrix,
    build_task_completed_gate_snapshot,
    load_law_label_map_ru,
)
from figma_flutter_agent.dev.opencode.l6_run_context import compact_run_context_for_l6
from figma_flutter_agent.dev.opencode.plan_validate import compiler_path_catalog
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain
from figma_flutter_agent.dev.opencode.repair_prompt import (
    _L6_CATALOG_LIMIT,
    allowed_edit_scope_json,
    diagnose_laws_json_for_repair,
)
from figma_flutter_agent.dev.opencode.repo_map import (
    compact_repo_map_json,
    deep_repo_map_json,
    symptom_surface_hints_json,
)
from figma_flutter_agent.dev.opencode.schema_gate import load_step_schema
from figma_flutter_agent.dev.opencode.workspace import RepairWorkspace


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _plan_step_orders_list(
    run_context: dict[str, Any],
    plan: dict[str, Any] | None,
) -> list[int]:
    raw = run_context.get("planStepOrders")
    if isinstance(raw, list) and raw:
        return [int(x) for x in raw if isinstance(x, (int, float))]
    orders: list[int] = []
    for item in (plan or {}).get("steps") or []:
        if isinstance(item, dict) and item.get("order") is not None:
            orders.append(int(item["order"]))
    return orders


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
    """Build placeholder values for ``l6-environment.tpl`` (step allowlist only)."""
    allowed_keys = l6_binding_keys_for(step, board=board)
    worktree = workspace.worktree.as_posix()
    debug_root = workspace.debug_mirror.as_posix()
    schema_path = (
        Path("src/figma_flutter_agent/dev/opencode/schemas") / f"{step}.schema.json"
    ).as_posix()
    state_dir = workspace.state_dir
    plan_orders = _plan_step_orders_list(run_context, plan)

    pool: dict[str, str] = {
        "worktree": worktree,
        "project": project_label,
        "feature": feature,
        "case_mode": str(run_context.get("case_mode") or ""),
        "agent_board": board,
        "debug_root": debug_root,
        "manifest_path": workspace.manifest_path.as_posix(),
        "run_manifest_path": str((workspace.debug_mirror / "run_manifest.json").as_posix()),
        "schema_path": schema_path,
        "output_path": str((state_dir / f"{step}.json").as_posix()),
        "detail_log_path": str((state_dir / f"{step}.detail.log").as_posix()),
        "run_context_json": _json_text(compact_run_context_for_l6(step, run_context)),
        "reasoning_chain_json": reasoning_chain_json,
        "repo_map_compact_json": compact_repo_map_json(board=board),
        "repo_map_deep_json": deep_repo_map_json(chain),
        "symptom_surface_hints_json": symptom_surface_hints_json(chain),
        "compiler_path_catalog_json": _json_text(
            compiler_path_catalog(workspace.worktree, limit=_L6_CATALOG_LIMIT)
        ),
        "inspect_preflight_json": _json_text(run_context.get("inspect_preflight") or {}),
        "plan_step_orders": _json_text(plan_orders),
        "plan_state_path": str((state_dir / "plan.json").as_posix()),
        "diagnose_state_path": str((state_dir / "diagnose.json").as_posix()),
        "diagnose_laws_json": diagnose_laws_json_for_repair(
            chain.steps,
            plan,
            plan_step_orders=plan_orders,
        ),
        "allowed_edit_scope_json": allowed_edit_scope_json(
            plan,
            plan_step_orders=plan_orders,
        ),
    }

    vision_bundle = run_context.get("vision_bundle") or {}
    check_payload = chain.steps.get("check") if isinstance(chain.steps.get("check"), dict) else {}
    capture_payload = (
        chain.steps.get("capture") if isinstance(chain.steps.get("capture"), dict) else {}
    )
    review_payload = (
        chain.steps.get("review") if isinstance(chain.steps.get("review"), dict) else {}
    )
    capture_closure_required = str(run_context.get("case_mode") or "") == "SCREEN" or bool(
        run_context.get("capture_closure_required")
    )
    task_gate = build_task_completed_gate_snapshot(
        check_passed=bool(check_payload.get("passed")),
        capture_passed=bool(capture_payload.get("passed")),
        capture_closure_required=capture_closure_required,
        review_decision=str(review_payload.get("decision") or ""),
    )

    pool.update(
        {
            "vision_bundle_dir": str(vision_bundle.get("visionDir") or debug_root),
            "vision_bundle_json": _json_text(vision_bundle),
            "diff_stats_json": _json_text(vision_bundle.get("diffStats") or {}),
            "semantic_hints_json": _json_text(vision_bundle.get("semanticHints") or {}),
            "check_summary_json": _json_text(check_payload),
            "analyze_errors_json": _json_text(run_context.get("analyze_errors") or []),
            "allowed_edit_files_json": _json_text(run_context.get("allowed_edit_files") or []),
            "frozen_context_json": _json_text(run_context.get("frozen_context") or {}),
            "fix_attempt": str(run_context.get("fix_attempt") or 1),
            "max_fix_attempts": str(run_context.get("max_fix_attempts") or 1),
            "review_rubric_json": _json_text(run_context.get("review_rubric") or {}),
            "capture_verdict_json": _json_text(capture_payload),
            "symptom_law_matrix_json": _json_text(build_symptom_law_matrix(chain)),
            "run_manifest_summary_json": _json_text(
                compact_run_context_for_l6(step, run_context).get("run_manifest") or {}
            ),
            "review_gate_snapshot_json": _json_text(
                build_review_gate_snapshot(
                    check_payload=check_payload,
                    capture_payload=capture_payload,
                    review_payload=review_payload,
                )
            ),
            "scope_diff_summary_json": _json_text(build_scope_diff_summary(chain)),
            "review_summary_json": _json_text(review_payload),
            "task_completed_gate_snapshot_json": _json_text(task_gate),
            "summarize_rubric_json": _json_text(run_context.get("summarize_rubric") or {}),
            "law_label_map_ru_json": _json_text(load_law_label_map_ru()),
            "ticket_summary_path": str(
                (workspace.repair_root / "reports" / "ticket.md").as_posix()
            ),
            "dev_summary_path": str((workspace.repair_root / "reports" / "dev.md").as_posix()),
            "data_context_path": str((workspace.repair_root / "data_context.json").as_posix()),
        }
    )

    _ = load_step_schema(step)
    return {key: pool[key] for key in allowed_keys if key in pool}


def render_l6_template(template: str, bindings: dict[str, str]) -> str:
    """Replace ``{placeholder}`` tokens in an L6 environment template."""
    rendered = template
    for key, value in bindings.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered
