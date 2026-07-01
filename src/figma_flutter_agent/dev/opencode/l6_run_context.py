"""Step-scoped run_context compaction before L6 JSON injection."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.dev.opencode.repair_prompt import compact_run_context_for_write

_L6_RUN_CONTEXT_OMIT_KEYS: frozenset[str] = frozenset({"_l6_bindings"})


def run_context_for_l6_json(run_context: dict[str, Any]) -> dict[str, Any]:
    """Drop orchestrator-only keys before embedding run_context into L6."""
    return {
        key: value for key, value in run_context.items() if key not in _L6_RUN_CONTEXT_OMIT_KEYS
    }


_MANIFEST_SUMMARY_KEYS: frozenset[str] = frozenset(
    {
        "pipeline_run_id",
        "verdict",
        "writeback",
        "flutterCaptureOk",
        "capture_kind",
        "failure_class",
        "case_mode",
        "agent_board",
    }
)

_READ_CONTEXT_KEYS: dict[str, frozenset[str]] = {
    "recognise": frozenset(
        {
            "case_mode",
            "agent_board",
            "initial_gate_verdict",
            "require_flutter_capture_verify",
            "loop_budget",
            "allowed_questions",
            "forbidden_questions",
        }
    ),
    "inspect": frozenset(
        {
            "case_mode",
            "agent_board",
            "initial_gate_verdict",
            "loop_budget",
            "inspect_preflight",
        }
    ),
    "diagnose": frozenset(
        {
            "case_mode",
            "agent_board",
            "loop_budget",
            "diagnose_validation_error",
        }
    ),
    "plan": frozenset(
        {
            "case_mode",
            "agent_board",
            "loop_budget",
            "plan_validation_error",
            "planStepOrders",
            "pivot",
        }
    ),
    "review": frozenset(
        {
            "case_mode",
            "agent_board",
            "loop_budget",
            "capture_closure_required",
            "review_rubric",
        }
    ),
    "summarize": frozenset(
        {
            "case_mode",
            "agent_board",
            "summarize_rubric",
        }
    ),
}


def _summarize_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        return {}
    return {key: manifest[key] for key in _MANIFEST_SUMMARY_KEYS if key in manifest}


def compact_run_context_for_l6(step: str, run_context: dict[str, Any]) -> dict[str, Any]:
    """Whitelist orchestrator facts per step; never embed vision or full manifest twice."""
    if step in {"repair", "fix"}:
        return compact_run_context_for_write(run_context_for_l6_json(run_context))

    base = run_context_for_l6_json(run_context)
    allowed = _READ_CONTEXT_KEYS.get(step)
    if allowed is None:
        return base

    compact: dict[str, Any] = {key: base[key] for key in allowed if key in base}
    manifest = _summarize_manifest(base.get("run_manifest"))
    if manifest:
        compact["run_manifest"] = manifest
    passport = base.get("capture_passport")
    if isinstance(passport, dict) and step in {"recognise", "inspect", "diagnose", "plan"}:
        compact["capture_passport"] = {
            key: passport[key]
            for key in (
                "flutterCaptureOk",
                "capture_verified",
                "capture_kind",
                "failure_class",
            )
            if key in passport
        }
    return compact
