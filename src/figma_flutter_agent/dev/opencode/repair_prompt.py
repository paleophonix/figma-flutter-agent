"""Compact OpenCode repair write prompts (L6 overlays, file-first repair)."""

from __future__ import annotations

import json
from typing import Any

from figma_flutter_agent.dev.opencode.chain_compact import (
    compact_chain_for_step,
    compact_diagnose,
    compact_plan_for_repair,
)
from figma_flutter_agent.dev.opencode.scope_enforcement import (
    collect_plan_target_files_for_orders,
)

_MAX_REPAIR_WRITE_PROMPT_CHARS = 48_000
_L6_CATALOG_LIMIT = 24


def sanitize_prompt_blob(text: str) -> str:
    """Escape fenced-code patterns in untrusted artifact excerpts."""
    return text.replace("```", "'''")


_REPAIR_RUN_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "case_mode",
        "agent_board",
        "verdict",
        "writeback",
        "planStepOrders",
        "capture_passport",
        "run_manifest",
        "pivot",
        "plan_validation_error",
        "diagnose_validation_error",
    }
)


def compact_run_context_for_write(run_context: dict[str, Any]) -> dict[str, Any]:
    """Keep only orchestrator facts repair needs; drop vision/rubric blobs."""
    compact: dict[str, Any] = {}
    for key in _REPAIR_RUN_CONTEXT_KEYS:
        if key not in run_context:
            continue
        value = run_context[key]
        if key == "run_manifest" and isinstance(value, dict):
            compact[key] = {
                k: value[k]
                for k in (
                    "pipeline_run_id",
                    "verdict",
                    "writeback",
                    "flutterCaptureOk",
                    "capture_kind",
                    "failure_class",
                )
                if k in value
            }
        elif key == "capture_passport" and isinstance(value, dict):
            compact[key] = {
                k: value[k]
                for k in (
                    "flutterCaptureOk",
                    "capture_verified",
                    "capture_kind",
                    "failure_class",
                    "warnings",
                )
                if k in value
            }
        else:
            compact[key] = value
    return compact


def repair_reasoning_chain_json(
    steps: dict[str, dict[str, Any]],
    *,
    plan_step_orders: list[int],
    pivot: dict[str, Any] | None = None,
) -> str:
    """Executive chain slice for repair including assigned plan steps only."""
    compact = compact_chain_for_step(steps, "repair", pivot)
    plan_payload = steps.get("plan")
    if isinstance(plan_payload, dict):
        compact["plan"] = compact_plan_for_repair(
            plan_payload,
            plan_step_orders=plan_step_orders,
        )
    return json.dumps(compact, ensure_ascii=False, separators=(",", ":"))


def diagnose_laws_json_for_repair(
    chain_steps: dict[str, dict[str, Any]],
    plan: dict[str, Any] | None,
    *,
    plan_step_orders: list[int],
) -> str:
    """Compact diagnose laws referenced by assigned plan steps."""
    diagnose = chain_steps.get("diagnose")
    if not isinstance(diagnose, dict):
        return "{}"
    law_ids: set[str] = set()
    allowed_orders = {int(order) for order in plan_step_orders}
    for item in (plan or {}).get("steps") or []:
        if not isinstance(item, dict):
            continue
        if allowed_orders and item.get("order") not in allowed_orders:
            continue
        law_id = item.get("lawId")
        if isinstance(law_id, str) and law_id.strip():
            law_ids.add(law_id.strip())
    compact = compact_diagnose(diagnose)
    if law_ids:
        compact["laws"] = [
            law
            for law in compact.get("laws") or []
            if isinstance(law, dict) and law.get("id") in law_ids
        ]
    return json.dumps(compact, ensure_ascii=False, indent=2)


def allowed_edit_scope_json(
    plan: dict[str, Any] | None,
    *,
    plan_step_orders: list[int],
) -> str:
    """Allowed compiler + test paths for assigned CODE_CHANGE steps."""
    if not isinstance(plan, dict):
        return "[]"
    paths = sorted(collect_plan_target_files_for_orders(plan, plan_step_orders))
    return json.dumps(paths, ensure_ascii=False, indent=2)


def cap_repair_write_prompt(text: str) -> str:
    """Hard cap repair OpenCode user message size."""
    text = sanitize_prompt_blob(text)
    if len(text) <= _MAX_REPAIR_WRITE_PROMPT_CHARS:
        return text
    return text[:_MAX_REPAIR_WRITE_PROMPT_CHARS] + "\n\n[truncated by orchestrator]"
