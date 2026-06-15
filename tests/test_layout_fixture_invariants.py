"""Geometry invariant gate for offline layout fixtures (planner=on)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.geometry.invariants.reporting import (
    partition_geometry_violations,
)
from figma_flutter_agent.generator.geometry.invariants.validate import (
    validate_geometry_invariants,
)
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import CleanDesignTreeNode

_LAYOUT_FIXTURES = sorted((Path(__file__).resolve().parent / "fixtures" / "layouts").glob("*.json"))
_SOFT_VIOLATION_BUDGET = 64


def _is_raw_figma_fixture(payload: dict) -> bool:
    return "layoutMode" in payload or (
        isinstance(payload.get("absoluteBoundingBox"), dict) and "type" not in payload
    )


def _load_fixture_tree(path: Path) -> CleanDesignTreeNode:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if _is_raw_figma_fixture(payload):
        tree, _, _, _ = build_clean_tree(payload)
        return tree
    return CleanDesignTreeNode.model_validate(payload)


@pytest.mark.parametrize("fixture_path", _LAYOUT_FIXTURES, ids=lambda p: p.name)
def test_layout_fixture_passes_geometry_invariants(fixture_path: Path) -> None:
    tree = _load_fixture_tree(fixture_path)
    normalized = normalize_clean_tree(
        tree,
        apply_render_safety=False,
        use_geometry_planner=True,
    )
    violations = validate_geometry_invariants(normalized, require_layout_slots=True)
    hard, soft = partition_geometry_violations(violations)
    assert not hard, "; ".join(f"{v.code}@{v.node_id}" for v in hard)
    assert len(soft) <= _SOFT_VIOLATION_BUDGET, (
        f"soft budget exceeded ({len(soft)} > {_SOFT_VIOLATION_BUDGET}): "
        + "; ".join(f"{v.code}@{v.node_id}" for v in soft[:8])
    )
