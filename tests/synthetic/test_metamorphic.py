"""Metamorphic rename tests (Program 08 P0-4)."""

from __future__ import annotations

import copy

from figma_flutter_agent.generator.geometry.invariants.conservation import (
    check_node_multiset_preserved,
)
from tests.synthetic.builders import column_tree
from tests.synthetic.canonical import canonical_tree_json
from tests.synthetic.replay import write_failure_artifact


def _rename_non_evidence(tree, mapping: dict[str, str]):
    cloned = copy.deepcopy(tree)

    def walk(node):
        node.name = mapping.get(node.id, node.name)
        for child in node.children:
            walk(child)

    walk(cloned)
    return cloned


def test_rename_non_evidence_preserves_multiset() -> None:
    tree = column_tree(depth=2)
    renamed = _rename_non_evidence(tree, {"leaf-0": "Decorative Glyph", "leaf-1": "Plate"})
    violations = check_node_multiset_preserved(tree, renamed)
    if violations:
        write_failure_artifact(
            test_name="rename_non_evidence",
            payload={"before": canonical_tree_json(tree), "after": canonical_tree_json(renamed)},
        )
    assert violations == []


def test_alpha_id_remap_changes_ids() -> None:
    tree = column_tree(depth=2)
    remapped = copy.deepcopy(tree)
    id_map = {"root": "n0", "leaf-0": "n1", "leaf-1": "n2"}

    def walk(node):
        node.id = id_map.get(node.id, node.id)
        for child in node.children:
            walk(child)

    walk(remapped)
    from tests.synthetic.validity import node_ids

    assert node_ids(tree) != node_ids(remapped)
