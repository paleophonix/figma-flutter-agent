"""L6 context helpers for review and summarize bindings."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain


@lru_cache(maxsize=1)
def load_law_label_map_ru() -> dict[str, str]:
    """Load product-facing RU law labels from OpenCode context."""
    path = agent_repo_root() / ".opencode" / "context" / "law-label-map-ru.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_symptom_law_matrix(chain: ReasoningChain) -> dict[str, Any]:
    """Crosswalk recognise symptoms with diagnose laws."""
    recognise = chain.steps.get("recognise") or {}
    diagnose = chain.steps.get("diagnose") or {}
    symptoms = recognise.get("symptoms") if isinstance(recognise, dict) else []
    laws = diagnose.get("laws") if isinstance(diagnose, dict) else []
    rows: list[dict[str, Any]] = []
    if isinstance(laws, list):
        for law in laws:
            if not isinstance(law, dict):
                continue
            rows.append(
                {
                    "lawId": law.get("id") or law.get("lawId"),
                    "layer": law.get("layer"),
                    "symptomIds": law.get("symptomIds") or [],
                }
            )
    return {
        "symptomCount": len(symptoms) if isinstance(symptoms, list) else 0,
        "lawCount": len(rows),
        "rows": rows,
    }


def build_review_gate_snapshot(
    *,
    check_payload: dict[str, Any] | None,
    capture_payload: dict[str, Any] | None,
    review_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compact gate snapshot for review L6 prompt."""
    return {
        "check": {
            "passed": (check_payload or {}).get("passed"),
            "failure_class": (check_payload or {}).get("failure_class"),
            "route": (check_payload or {}).get("route"),
        },
        "capture": {
            "passed": (capture_payload or {}).get("passed"),
            "kind": (capture_payload or {}).get("kind"),
        },
        "review": {
            "decision": (review_payload or {}).get("decision"),
            "reason_code": (review_payload or {}).get("reason_code"),
            "overridden": (review_payload or {}).get("overridden"),
        },
    }


def build_scope_diff_summary(chain: ReasoningChain) -> dict[str, Any]:
    """Summarize repair/fix scope results from chain steps."""
    repair = chain.steps.get("repair") or {}
    scope = repair.get("scope") if isinstance(repair, dict) else {}
    fix_steps = {
        key: value.get("scope")
        for key, value in chain.steps.items()
        if key.startswith("fix_") and isinstance(value, dict)
    }
    return {
        "repair": scope if isinstance(scope, dict) else {},
        "fixAttempts": fix_steps,
    }


def build_task_completed_gate_snapshot(
    *,
    check_passed: bool,
    capture_passed: bool,
    capture_closure_required: bool,
    review_decision: str,
) -> dict[str, Any]:
    """Snapshot for summarize task-completed gate."""
    decision = review_decision.upper()
    task_completed = (
        decision == "CONTINUE"
        and check_passed
        and (not capture_closure_required or capture_passed)
    )
    return {
        "reviewDecision": decision,
        "checkPassed": check_passed,
        "capturePassed": capture_passed,
        "captureClosureRequired": capture_closure_required,
        "taskCompleted": task_completed,
    }
