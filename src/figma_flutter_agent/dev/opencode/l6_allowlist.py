"""Per-step L6 binding allowlists (executive compact / file-first doctrine)."""

from __future__ import annotations

_L6_CORE: frozenset[str] = frozenset(
    {
        "worktree",
        "project",
        "feature",
        "case_mode",
        "agent_board",
        "schema_path",
        "output_path",
        "detail_log_path",
    }
)

_RECOGNISE_FORENSIC: frozenset[str] = _L6_CORE | frozenset(
    {
        "debug_root",
        "run_manifest_path",
        "run_context_json",
    }
)

_RECOGNISE_SCREEN: frozenset[str] = _RECOGNISE_FORENSIC | frozenset(
    {
        "vision_bundle_dir",
        "vision_bundle_json",
        "diff_stats_json",
        "semantic_hints_json",
    }
)

_INSPECT_FORENSIC: frozenset[str] = _L6_CORE | frozenset(
    {
        "debug_root",
        "manifest_path",
        "run_context_json",
        "reasoning_chain_json",
        "inspect_preflight_json",
        "repo_map_compact_json",
    }
)

_INSPECT_SCREEN: frozenset[str] = _INSPECT_FORENSIC | frozenset(
    {
        "symptom_surface_hints_json",
    }
)

_DIAGNOSE: frozenset[str] = _L6_CORE | frozenset(
    {
        "debug_root",
        "manifest_path",
        "run_context_json",
        "reasoning_chain_json",
        "repo_map_deep_json",
    }
)

_PLAN: frozenset[str] = _DIAGNOSE | frozenset(
    {
        "compiler_path_catalog_json",
    }
)

_REPAIR: frozenset[str] = _L6_CORE | frozenset(
    {
        "debug_root",
        "run_context_json",
        "plan_step_orders",
        "plan_state_path",
        "diagnose_state_path",
        "diagnose_laws_json",
        "allowed_edit_scope_json",
    }
)

_FIX: frozenset[str] = _L6_CORE | frozenset(
    {
        "check_summary_json",
        "analyze_errors_json",
        "allowed_edit_files_json",
        "frozen_context_json",
        "fix_attempt",
        "max_fix_attempts",
        "reasoning_chain_json",
    }
)

_REVIEW: frozenset[str] = _L6_CORE | frozenset(
    {
        "run_context_json",
        "reasoning_chain_json",
        "review_rubric_json",
        "capture_verdict_json",
        "symptom_law_matrix_json",
        "check_summary_json",
        "review_gate_snapshot_json",
        "scope_diff_summary_json",
        "repo_map_compact_json",
    }
)

_SUMMARIZE: frozenset[str] = _L6_CORE | frozenset(
    {
        "ticket_summary_path",
        "dev_summary_path",
        "data_context_path",
        "review_summary_json",
        "task_completed_gate_snapshot_json",
        "summarize_rubric_json",
        "law_label_map_ru_json",
        "reasoning_chain_json",
    }
)

_STEP_ALLOWLIST: dict[str, frozenset[str]] = {
    "recognise": _RECOGNISE_FORENSIC,
    "inspect": _INSPECT_FORENSIC,
    "diagnose": _DIAGNOSE,
    "plan": _PLAN,
    "repair": _REPAIR,
    "fix": _FIX,
    "review": _REVIEW,
    "summarize": _SUMMARIZE,
}

_BOARD_OVERRIDES: dict[tuple[str, str], frozenset[str]] = {
    ("recognise", "screen"): _RECOGNISE_SCREEN,
    ("inspect", "screen"): _INSPECT_SCREEN,
}


def l6_binding_keys_for(step: str, *, board: str) -> frozenset[str]:
    """Return L6 placeholder keys allowed for one pipeline step."""
    override = _BOARD_OVERRIDES.get((step, board))
    if override is not None:
        return override
    allowed = _STEP_ALLOWLIST.get(step)
    if allowed is None:
        raise KeyError(f"Unknown L6 step: {step}")
    return allowed
