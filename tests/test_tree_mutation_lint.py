"""Grandfather lint: tree child mutations outside managed pass modules."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "figma_flutter_agent"

MUTATION_PATTERN = re.compile(r"\bnode\.children\s*=")

ALLOWLIST_PREFIXES = (
    "generator/ir/passes/",
    "parser/layout/reconcilers_",
    "parser/dedup/prune.py",
    "parser/dedup/hydrate.py",
    "parser/tree.py",
    "parser/boundaries/",
    "parser/stack_paint.py",
    "parser/subtree.py",
    "generator/subtree.py",
    "generator/subtree/",
    "generator/planner/cluster_subtree.py",
    "generator/tree_copy.py",
    "generator/ir/tree.py",
    "generator/ir/passes/sync.py",
    "generator/geometry/",
    "pipeline/",
    "stages/",
    "fixtures/",
    "debug/",
    "validation/",
    "audit/",
)


def _relative(path: Path) -> str:
    return path.relative_to(SRC_ROOT).as_posix()


def test_no_unmanaged_node_children_assignment_in_src() -> None:
    """Fail when new ad-hoc ``node.children =`` appears outside the allowlist."""
    offenders: list[str] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        rel = _relative(path)
        if rel.startswith("generator/ir/passes/"):
            continue
        if any(rel.startswith(prefix) or rel == prefix for prefix in ALLOWLIST_PREFIXES):
            continue
        text = path.read_text(encoding="utf-8")
        if MUTATION_PATTERN.search(text):
            offenders.append(rel)
    assert offenders == [], f"Unmanaged tree mutations: {offenders}"
