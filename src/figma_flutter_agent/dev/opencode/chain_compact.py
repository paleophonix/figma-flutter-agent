"""Executive compaction for reasoning-chain prompt injection."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.dev.opencode.plan_routing import coerce_plan_step_order

_MAX_SYMPTOM_CHARS = 360
_MAX_ENTITY_SUMMARY = 420
_MAX_EVIDENCE_EXCERPT = 220
_MAX_ROLE_CHARS = 140
_MAX_FORBIDDEN_ITEMS = 4
_MAX_ENTITIES = 10
_MAX_LAWS = 8
_MAX_EVIDENCE_PER_LAW = 3


def _truncate(text: object, max_len: int) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."


def compact_recognise(payload: dict[str, Any]) -> dict[str, Any]:
    """Shrink recognise output for downstream prompts."""
    symptoms = payload.get("symptoms") or []
    compact_symptoms: list[Any] = []
    for item in symptoms[:6]:
        if isinstance(item, dict):
            compact_symptoms.append(
                {
                    "id": item.get("id"),
                    "description": _truncate(item.get("description", ""), _MAX_SYMPTOM_CHARS),
                }
            )
        else:
            compact_symptoms.append(_truncate(item, _MAX_SYMPTOM_CHARS))
    return {
        "step": "recognise",
        "symptoms": compact_symptoms,
        "blocked": payload.get("blocked"),
    }


def compact_inspect(payload: dict[str, Any]) -> dict[str, Any]:
    """Shrink inspect entities; drop repeated symptom prose."""
    entities: list[dict[str, Any]] = []
    for entity in (payload.get("entities") or [])[:_MAX_ENTITIES]:
        if not isinstance(entity, dict):
            continue
        entities.append(
            {
                "id": entity.get("id"),
                "kind": entity.get("kind"),
                "role": entity.get("role"),
                "summary": _truncate(entity.get("summary", ""), _MAX_ENTITY_SUMMARY),
                "artifactRefs": list(entity.get("artifactRefs") or [])[:6],
                "repoPaths": list(entity.get("repoPaths") or [])[:4],
                "confidence": entity.get("confidence"),
                "blocked": entity.get("blocked"),
            }
        )
    return {
        "step": "inspect",
        "entities": entities,
        "blocked": payload.get("blocked"),
    }


def _compact_evidence(items: list[Any]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in items[:_MAX_EVIDENCE_PER_LAW]:
        if not isinstance(item, dict):
            continue
        entry: dict[str, Any] = {
            "ref": item.get("ref"),
            "kind": item.get("kind"),
            "excerpt": _truncate(item.get("excerpt", ""), _MAX_EVIDENCE_EXCERPT),
        }
        role = item.get("role")
        if role:
            entry["role"] = _truncate(role, _MAX_ROLE_CHARS)
        compact.append(entry)
    return compact


def compact_diagnose(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep law ids, layers, repairShape, and capped evidence excerpts."""
    laws: list[dict[str, Any]] = []
    for law in (payload.get("laws") or [])[:_MAX_LAWS]:
        if not isinstance(law, dict):
            continue
        shape = law.get("repairShape")
        compact_shape = shape if isinstance(shape, dict) else _truncate(shape, 280)
        laws.append(
            {
                "id": law.get("id"),
                "priority": law.get("priority"),
                "layer": law.get("layer"),
                "entityIds": law.get("entityIds"),
                "repairShape": compact_shape,
                "forbidden": list(law.get("forbidden") or [])[:_MAX_FORBIDDEN_ITEMS],
                "proposedLaw": law.get("proposedLaw"),
                "evidence": _compact_evidence(list(law.get("evidence") or [])),
            }
        )
    return {
        "step": "diagnose",
        "laws": laws,
        "blocked": payload.get("blocked"),
        "escalate": payload.get("escalate"),
    }


def compact_plan_for_repair(
    plan_payload: dict[str, Any],
    *,
    plan_step_orders: list[int] | None = None,
) -> dict[str, Any]:
    """Keep only assigned CODE_CHANGE steps with paths needed for repair."""
    allowed_orders = set(plan_step_orders or [])
    steps: list[dict[str, Any]] = []
    for item in plan_payload.get("steps") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or "CODE_CHANGE").upper() != "CODE_CHANGE":
            continue
        order = coerce_plan_step_order(item)
        if allowed_orders and (order is None or order not in allowed_orders):
            continue
        tests: list[str] = []
        for entry in item.get("tests") or []:
            if isinstance(entry, str) and entry.strip():
                tests.append(entry.strip())
            elif isinstance(entry, dict):
                path = entry.get("path") or entry.get("name")
                if isinstance(path, str) and path.strip():
                    tests.append(path.strip())
        steps.append(
            {
                "order": order,
                "lawId": item.get("lawId"),
                "repairClass": item.get("repairClass"),
                "targetFiles": list(item.get("targetFiles") or [])[:6],
                "tests": tests[:4],
                "expectedChange": _truncate(item.get("expectedChange", ""), 320),
            }
        )
    return {
        "step": "plan",
        "steps": steps,
        "blocked": plan_payload.get("blocked"),
    }


def compact_plan_revise_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Minimal prior-plan hint for plan revise loops (avoid re-injecting full steps)."""
    law_ids: list[str] = []
    for item in payload.get("steps") or []:
        if not isinstance(item, dict):
            continue
        law_id = item.get("lawId")
        if isinstance(law_id, str) and law_id.strip():
            law_ids.append(law_id.strip())
    return {
        "step": "plan",
        "blocked": payload.get("blocked"),
        "lawIds": law_ids[:8],
        "notes": _truncate(payload.get("notes", ""), 200),
    }


def compact_plan_prior(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize a prior plan for revise loops."""
    steps: list[dict[str, Any]] = []
    for item in payload.get("steps") or []:
        if not isinstance(item, dict):
            continue
        steps.append(
            {
                "order": item.get("order"),
                "lawId": item.get("lawId"),
                "actionKind": item.get("actionKind"),
                "repairClass": item.get("repairClass"),
                "targetFiles": item.get("targetFiles"),
                "tests": item.get("tests"),
                "expectedChange": _truncate(item.get("expectedChange", ""), 320),
            }
        )
    return {
        "step": "plan",
        "steps": steps,
        "blockedItems": payload.get("blockedItems"),
    }


def compact_repair_prior(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize a prior repair attempt."""
    return {
        "step": "repair",
        "noop": payload.get("noop"),
        "filesTouched": payload.get("filesTouched"),
        "scope": payload.get("scope"),
        "gates": {
            "passed": (payload.get("gates") or {}).get("passed")
            if isinstance(payload.get("gates"), dict)
            else None
        },
    }


def compact_check_prior(payload: dict[str, Any]) -> dict[str, Any]:
    """Summarize check output without analyzer dumps."""
    return {
        "step": "check",
        "passed": payload.get("passed"),
        "failure_class": payload.get("failure_class"),
        "route": payload.get("route"),
        "evidence": list(payload.get("evidence") or [])[:6],
        "same_root_hash": payload.get("same_root_hash"),
    }


def compact_chain_for_step(
    steps: dict[str, dict[str, Any]],
    step: str,
    pivot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an executive chain slice for one read/write step."""
    compact: dict[str, Any] = {}
    recognise = steps.get("recognise")
    inspect = steps.get("inspect")
    diagnose = steps.get("diagnose")

    if step in {"inspect", "diagnose", "plan", "repair", "review"} and isinstance(
        recognise, dict
    ):
        compact["recognise"] = compact_recognise(recognise)
    if step in {"diagnose", "plan", "repair", "review"} and isinstance(inspect, dict):
        compact["inspect"] = compact_inspect(inspect)
    if step in {"plan", "repair", "review"} and isinstance(diagnose, dict):
        compact["diagnose"] = compact_diagnose(diagnose)

    if pivot:
        compact["pivot"] = pivot

    if step in {"plan", "repair"}:
        repair = steps.get("repair")
        if isinstance(repair, dict) and (pivot or repair.get("noop")):
            compact["prior_repair"] = compact_repair_prior(repair)
        prior_plan = steps.get("plan")
        if isinstance(prior_plan, dict) and pivot:
            if step == "plan":
                compact["prior_plan"] = compact_plan_revise_summary(prior_plan)
            else:
                compact["prior_plan"] = compact_plan_prior(prior_plan)
        check = steps.get("check")
        if isinstance(check, dict) and pivot:
            compact["prior_check"] = compact_check_prior(check)

    if step == "review":
        for name in ("plan", "repair", "check", "capture"):
            payload = steps.get(name)
            if not isinstance(payload, dict):
                continue
            if name == "plan":
                compact["plan"] = compact_plan_prior(payload)
            elif name == "repair":
                compact["repair"] = compact_repair_prior(payload)
            elif name == "check":
                compact["check"] = compact_check_prior(payload)
            else:
                compact["review_capture"] = {
                    key: payload[key]
                    for key in ("passed", "failure_class", "same_root_hash")
                    if key in payload
                }

    return compact
