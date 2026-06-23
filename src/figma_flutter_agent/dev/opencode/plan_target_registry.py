"""Typed diagnose law → plan companion target registry."""

from __future__ import annotations

from typing import Any

_COMPILER_PREFIX = "src/figma_flutter_agent/"

# (lawId, layer) → companion targetFiles (repo-relative).
_LAW_COMPANION_TARGETS: dict[tuple[str, str], tuple[str, ...]] = {
    ("capture_runtime_overflow_no_verified_capture", "capture"): (
        "src/figma_flutter_agent/generator/layout/flex_policy/row.py",
    ),
    ("FlexRowOverflowLaw", "emit"): (
        "src/figma_flutter_agent/generator/layout/flex_policy/row.py",
    ),
    ("RowFlexOverflowLaw", "emit"): (
        "src/figma_flutter_agent/generator/layout/flex_policy/row.py",
    ),
    ("WritebackCaptureLaw", "capture"): (
        "src/figma_flutter_agent/pipeline/run/commit.py",
        "src/figma_flutter_agent/pipeline/result.py",
        "src/figma_flutter_agent/stages/write.py",
    ),
    ("CaptureWritebackLaw", "capture"): (
        "src/figma_flutter_agent/pipeline/run/commit.py",
        "src/figma_flutter_agent/pipeline/result.py",
        "src/figma_flutter_agent/stages/write.py",
    ),
}

_LAYER_ALIASES: dict[str, str] = {
    "parser": "parse",
    "parse": "parse",
    "ir": "ir",
    "emitter": "emit",
    "emit": "emit",
    "layout": "emit",
    "capture": "capture",
    "writeback": "capture",
}


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _law_key(law: dict[str, Any]) -> tuple[str, str] | None:
    law_id = ""
    for key in ("lawId", "id", "law_id"):
        raw = law.get(key)
        if isinstance(raw, str) and raw.strip():
            law_id = raw.strip()
            break
    layer_raw = str(law.get("layer") or "").strip().lower()
    layer = _LAYER_ALIASES.get(layer_raw, layer_raw)
    if not law_id:
        return None
    return law_id, layer


def companion_targets_for_law(law: dict[str, Any]) -> tuple[str, ...]:
    """Return companion compiler paths for one diagnose law entry."""
    key = _law_key(law)
    if key is None:
        return ()
    return _LAW_COMPANION_TARGETS.get(key, ())


def companion_modules_for_diagnose(diagnose_payload: dict[str, Any] | None) -> frozenset[str]:
    """Return compiler module prefixes implied by diagnose laws."""
    if not isinstance(diagnose_payload, dict):
        return frozenset()
    laws = diagnose_payload.get("laws")
    if not isinstance(laws, list):
        return frozenset()
    modules: set[str] = set()
    for law in laws:
        if not isinstance(law, dict):
            continue
        for target in companion_targets_for_law(law):
            normalized = _normalize_repo_path(target)
            if normalized.startswith(_COMPILER_PREFIX):
                modules.add(normalized)
    return frozenset(modules)


def enrich_plan_targets(
    plan_payload: dict[str, Any],
    *,
    diagnose_payload: dict[str, Any] | None,
) -> bool:
    """Append registry companion targets to matching CODE_CHANGE plan steps.

    Args:
        plan_payload: Mutable executive plan JSON.
        diagnose_payload: Parsed diagnose step JSON.

    Returns:
        True when at least one plan step gained a companion target.
    """
    if not isinstance(diagnose_payload, dict):
        return False
    laws = diagnose_payload.get("laws")
    if not isinstance(laws, list) or not laws:
        return False
    companions: set[str] = set()
    for law in laws:
        if isinstance(law, dict):
            companions.update(companion_targets_for_law(law))
    if not companions:
        return False

    enriched = False
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return False
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or "CODE_CHANGE").upper() != "CODE_CHANGE":
            continue
        targets = [
            _normalize_repo_path(str(raw))
            for raw in (item.get("targetFiles") or [])
            if isinstance(raw, str) and raw.strip()
        ]
        for companion in sorted(companions):
            if companion not in targets:
                targets.append(companion)
                enriched = True
        if enriched:
            item["targetFiles"] = sorted(set(targets))
    return enriched
