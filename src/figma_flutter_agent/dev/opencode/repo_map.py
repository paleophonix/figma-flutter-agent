"""Curated repo navigation map for repair pipeline L6 prompts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.dev.opencode.reasoning_chain import ReasoningChain

_REPO_MAP_REL = Path(".opencode") / "context" / "repo-map.yaml"
_EMITTER_SURFACES = (
    "generator/layout/widgets/emit/flex.py",
    "generator/layout/widgets/emit/stack.py",
    "generator/layout/widgets/emit/text.py",
    "generator/layout/common.py",
    "generator/ir/validate.py",
)
_ROW_OVERFLOW_SURFACES = (
    "generator/layout/flex_policy/row.py",
)
_OVERFLOW_KEYWORDS = (
    "overflow",
    "renderflex",
    "row",
    "flex",
    "unbounded",
    "constraint",
)


@lru_cache(maxsize=1)
def load_repo_map() -> dict[str, Any]:
    """Load ``.opencode/context/repo-map.yaml`` from the agent repo."""
    path = agent_repo_root() / _REPO_MAP_REL
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _compact_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def compact_repo_map_json(*, board: str) -> str:
    """Return global + board-specific navigation slice for inspect steps."""
    data = load_repo_map()
    compact: dict[str, Any] = {
        "repoMapVersion": data.get("repoMapVersion"),
        "global": data.get("global") or {},
    }
    if board == "forensic":
        compact["forensicSurfaces"] = data.get("forensicSurfaces") or {}
    else:
        compact["screenSymptomHints"] = data.get("screenSymptomHints") or {}
    return _compact_json(compact)


def symptom_surface_hints_json(chain: ReasoningChain) -> str:
    """Map recognise symptoms to curated repo surface hints when possible."""
    data = load_repo_map()
    hints = data.get("screenSymptomHints") or {}
    recognise = chain.steps.get("recognise") or {}
    selected: dict[str, Any] = {}
    for symptom in recognise.get("symptoms") or []:
        if not isinstance(symptom, dict):
            continue
        for key in hints:
            if key in str(symptom.get("description") or "").lower().replace(" ", "_"):
                selected[key] = hints[key]
    return _compact_json(selected)


def _chain_text_blob(chain: ReasoningChain) -> str:
    return json.dumps(chain.steps, ensure_ascii=False).lower()


def _repair_shape_target(law: dict[str, Any]) -> str:
    """Normalize diagnose law repairShape to a lowercase target token."""
    raw_shape = law.get("repairShape")
    if isinstance(raw_shape, dict):
        for key in ("target", "layer", "description"):
            value = raw_shape.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return ""
    if isinstance(raw_shape, str):
        return raw_shape.strip().lower()
    layer = law.get("layer")
    if isinstance(layer, str):
        return layer.strip().lower()
    return ""


def resolve_deep_module_paths(chain: ReasoningChain) -> list[str]:
    """Choose deep module paths from inspect/diagnose outputs and symptom keywords."""
    paths: set[str] = set()
    inspect = chain.steps.get("inspect") or {}
    for entity in inspect.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        for ref in entity.get("repoPaths") or []:
            token = str(ref).strip().replace("\\", "/")
            if token:
                paths.add(token)
    diagnose = chain.steps.get("diagnose") or {}
    if isinstance(diagnose, dict):
        for law in diagnose.get("laws") or []:
            if not isinstance(law, dict):
                continue
            target = _repair_shape_target(law)
            if target in {"emitter", "layout", "ir"}:
                paths.update(_EMITTER_SURFACES)
                paths.update(_ROW_OVERFLOW_SURFACES)
    blob = _chain_text_blob(chain)
    if any(keyword in blob for keyword in _OVERFLOW_KEYWORDS):
        paths.update(_EMITTER_SURFACES)
        paths.update(_ROW_OVERFLOW_SURFACES)
    if not paths:
        paths.update(_EMITTER_SURFACES[:3])
    return sorted(paths)


def deep_repo_map_json(chain: ReasoningChain) -> str:
    """Return deepModules slice for selected compiler paths."""
    data = load_repo_map()
    deep_modules = data.get("deepModules") or {}
    selected_paths = resolve_deep_module_paths(chain)
    sliced: dict[str, Any] = {}
    for path in selected_paths:
        if path in deep_modules:
            sliced[path] = deep_modules[path]
        else:
            sliced[path] = {"role": "Listed by inspect/diagnose; read file in worktree."}
    return _compact_json(
        {
            "selectedPaths": selected_paths,
            "deepModules": sliced,
            "pathPrefix": "src/figma_flutter_agent/",
        }
    )


def plan_scoped_repo_map_json(plan: dict[str, Any] | None) -> str:
    """Return deepModules slice for plan targetFiles only (not whole emitter fan-out)."""
    data = load_repo_map()
    deep_modules = data.get("deepModules") or {}
    paths: set[str] = set()
    for item in (plan or {}).get("steps") or []:
        if not isinstance(item, dict):
            continue
        for raw in item.get("targetFiles") or []:
            token = str(raw).strip().replace("\\", "/")
            if token.startswith("src/figma_flutter_agent/"):
                token = token.removeprefix("src/figma_flutter_agent/")
            if token:
                paths.add(token)
    selected_paths = sorted(paths)[:6]
    sliced: dict[str, Any] = {}
    for path in selected_paths:
        if path in deep_modules:
            sliced[path] = deep_modules[path]
        else:
            sliced[path] = {"role": "Plan target; read file in worktree."}
    return _compact_json(
        {
            "selectedPaths": selected_paths,
            "deepModules": sliced,
            "pathPrefix": "src/figma_flutter_agent/",
        }
    )
