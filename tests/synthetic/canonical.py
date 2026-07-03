"""Canonical JSON helpers for synthetic replay."""

from __future__ import annotations

import json
from typing import Any

from figma_flutter_agent.schemas import CleanDesignTreeNode


def canonical_tree_dict(tree: CleanDesignTreeNode) -> dict[str, Any]:
    return tree.model_dump(mode="json", by_alias=True)


def canonical_tree_json(tree: CleanDesignTreeNode) -> str:
    return json.dumps(canonical_tree_dict(tree), sort_keys=True, separators=(",", ":"))
