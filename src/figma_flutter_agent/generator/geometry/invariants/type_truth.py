"""Type immutability baseline and legacy semantic type tracking."""

from __future__ import annotations

from figma_flutter_agent.schemas import NodeType


def capture_type_baseline(tree) -> dict[str, NodeType]:
    """Capture ``node.id -> node.type`` for the full clean-tree walk."""
    baseline: dict[str, NodeType] = {}

    def walk(node) -> None:
        baseline[node.id] = node.type
        for child in node.children:
            walk(child)

    walk(tree)
    return baseline


def set_parse_type_baseline(tree) -> None:
    """Store post-parse type baseline on the conservation session."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        get_conservation_session,
    )

    session = get_conservation_session()
    if session is None:
        return
    session.type_baseline = capture_type_baseline(tree)


def note_legacy_semantic_type(node_id: str) -> None:
    """Mark a node whose type was assigned by a grandfathered parser policy."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        activate_conservation_session,
        get_conservation_session,
    )

    session = get_conservation_session()
    if session is None:
        session = activate_conservation_session()
    session.legacy_semantic_type_ids.add(node_id)

    from figma_flutter_agent.debug.provenance import get_provenance_recorder

    recorder = get_provenance_recorder()
    if recorder is not None:
        recorder.record_mutation(
            checkpoint="CP0_parse",
            transform="legacy_semantic_type",
            node_id=node_id,
            field="type",
            old=None,
            new=None,
            policy="legacy_semantic_type",
        )


def is_legacy_semantic_type_node(node_id: str) -> bool:
    """Return True when parser applied a legacy semantic type mutation."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        get_conservation_session,
    )

    session = get_conservation_session()
    if session is None:
        return False
    return node_id in session.legacy_semantic_type_ids


def clear_legacy_semantic_type_registry() -> None:
    """Reset legacy type registry on the active conservation session (tests only)."""
    from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
        get_conservation_session,
    )

    session = get_conservation_session()
    if session is not None:
        session.legacy_semantic_type_ids.clear()
