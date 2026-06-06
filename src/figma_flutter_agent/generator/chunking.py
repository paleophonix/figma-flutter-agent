"""IR-level widget chunking: split oversized clean-tree nodes into standalone files.

Cost-based, greedy post-order decomposition. Operates on :class:`CleanDesignTreeNode`
*before* Dart emit, so every emitted file stays below the AST-sidecar and
``dart format`` size gates.

Pipeline position: after ``normalize_clean_tree``, before ``render_layout_file``.

Usage Example::

    from figma_flutter_agent.generator.chunking import chunk_ir_tree, CHUNK_TARGET_BYTES

    result = chunk_ir_tree(clean_tree)
    if result.was_chunked:
        # result.root  — modified tree with extracted_widget_ref stubs inserted
        # result.chunks — list[ChunkUnit] to emit as separate Dart files

LLM Context:
    Each ChunkUnit.subtree is a standalone CleanDesignTreeNode ready for
    render_node_body(). Chunk class names are deterministic hashes of node ids —
    safe to cache across re-runs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Final

from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType

# Conservative budget — well below the 80 KB AST-sidecar gate, accounting for
# class/import boilerplate (~1-2 KB) and estimate variance.
CHUNK_TARGET_BYTES: Final[int] = 32_000

# Approximate bytes emitted per IR node (conservative, empirically calibrated).
_BYTES_PER_NODE: Final[int] = 300

# Minimum subtree node count worth extracting — don't shatter tiny subtrees.
_MIN_CHUNK_NODES: Final[int] = 8
_MIN_CHUNK_COST: Final[int] = _MIN_CHUNK_NODES * _BYTES_PER_NODE

# Natural cut-point parent types: layout containers whose children are
# structurally independent and safe to inline-replace with a widget reference.
_CUT_POINT_TYPES: Final[frozenset[NodeType]] = frozenset(
    {NodeType.COLUMN, NodeType.ROW, NodeType.STACK, NodeType.CONTAINER}
)

# Leaf types — no benefit in extracting; always keep inline.
_LEAF_TYPES: Final[frozenset[NodeType]] = frozenset(
    {NodeType.TEXT, NodeType.IMAGE, NodeType.VECTOR}
)


@dataclass(frozen=True)
class ChunkUnit:
    """A subtree extracted from the main layout as a standalone widget.

    Attributes:
        class_name: Public Dart class name (safe Dart identifier, no leading ``_``).
        subtree: The original IR subtree to render as a separate ``StatelessWidget``.
    """

    class_name: str
    subtree: CleanDesignTreeNode


@dataclass
class ChunkingResult:
    """Result of IR-level tree decomposition.

    Attributes:
        root: Possibly modified root node — extracted subtrees replaced by stubs
              (``extracted_widget_ref`` set to the chunk class name).
        chunks: Ordered list of extracted subtrees. Empty when no chunking occurred.
    """

    root: CleanDesignTreeNode
    chunks: list[ChunkUnit] = field(default_factory=list)

    @property
    def was_chunked(self) -> bool:
        """True when at least one chunk was extracted."""
        return bool(self.chunks)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def subtree_node_count(node: CleanDesignTreeNode) -> int:
    """Return the total number of nodes in the subtree rooted at *node*.

    Args:
        node: Root of the subtree to count.

    Returns:
        Integer node count, always ≥ 1.
    """
    count = 1
    for child in node.children:
        count += subtree_node_count(child)
    return count


def estimate_subtree_bytes(node: CleanDesignTreeNode) -> int:
    """Estimate the emitted Dart source bytes for a subtree.

    Uses a linear proxy: ``node_count × _BYTES_PER_NODE``.  Fast (O(n)) and
    conservative — actual emit is usually at this order of magnitude.

    Args:
        node: Root of the subtree to estimate.

    Returns:
        Estimated byte count.
    """
    return subtree_node_count(node) * _BYTES_PER_NODE


def chunk_ir_tree(
    root: CleanDesignTreeNode,
    *,
    budget: int = CHUNK_TARGET_BYTES,
) -> ChunkingResult:
    """Decompose an oversized IR tree into a root + extracted chunk subtrees.

    Applies a greedy post-order DFS: for each layout container whose estimated
    subtree cost exceeds *budget*, large-enough children are extracted as
    :class:`ChunkUnit` entries and replaced in the tree with
    ``extracted_widget_ref`` stubs.  The stub causes the existing emitter to
    emit ``const ClassName()`` at that position — no other emitter changes needed.

    Idempotent: if ``estimate_subtree_bytes(root) <= budget``, returns the root
    unchanged with an empty chunk list.

    Only cuts at natural boundaries (layout container parents with independently
    renderable children).  Never splits inside a single decorated widget.

    Args:
        root: The top-level clean design tree node to process.
        budget: Target maximum estimated bytes per emitted Dart file. Defaults
            to :data:`CHUNK_TARGET_BYTES` (32 KB).

    Returns:
        :class:`ChunkingResult` with the modified root and extracted chunks.

    Raises:
        Nothing — if the tree cannot be decomposed (e.g. single monolithic node),
        returns the root as-is with an empty chunk list.
    """
    if estimate_subtree_bytes(root) <= budget:
        return ChunkingResult(root=root)

    chunks: list[ChunkUnit] = []

    def _process(node: CleanDesignTreeNode) -> tuple[CleanDesignTreeNode, int]:
        """Post-order walk.  Returns (processed_node, estimated_cost)."""
        if not node.children:
            return node, _BYTES_PER_NODE

        # Recurse children first.
        processed: list[tuple[CleanDesignTreeNode, int]] = [
            _process(child) for child in node.children
        ]
        own_cost = _BYTES_PER_NODE
        total_cost = own_cost + sum(c for _, c in processed)

        # Only attempt to cut when we're over budget and at a natural boundary.
        if total_cost <= budget or node.type not in _CUT_POINT_TYPES:
            new_node = node.model_copy(
                update={"children": [pc for pc, _ in processed]}
            )
            return new_node, total_cost

        # Greedy: iterate children left-to-right; extract when running total
        # would exceed budget and child is large enough.
        new_children: list[CleanDesignTreeNode] = []
        running = own_cost

        for pc, child_cost in processed:
            if (
                child_cost >= _MIN_CHUNK_COST
                and running + child_cost > budget
                and _is_extractable(pc)
            ):
                class_name = _stable_chunk_name(pc.id, len(chunks))
                chunks.append(ChunkUnit(class_name=class_name, subtree=pc))
                stub = pc.model_copy(
                    update={"extracted_widget_ref": class_name, "children": []}
                )
                new_children.append(stub)
                running += _BYTES_PER_NODE  # stub is tiny
            else:
                new_children.append(pc)
                running += child_cost

        new_node = node.model_copy(update={"children": new_children})
        return new_node, running

    new_root, _ = _process(root)
    return ChunkingResult(root=new_root, chunks=chunks)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _stable_chunk_name(node_id: str, index: int) -> str:  # noqa: ARG001
    """Deterministic public Dart class name for a chunk.

    Uses an 8-char hex digest of the node id so the name is stable across
    reruns (idempotent).  The ``index`` param is reserved for future collision
    handling but is currently unused.

    Args:
        node_id: Figma node id of the extracted subtree root.
        index: Ordinal of this chunk in the current extraction pass (unused).

    Returns:
        Valid public Dart class name, e.g. ``FigmaChunkA3f9c21b``.
    """
    h = hashlib.sha1(node_id.encode(), usedforsecurity=False).hexdigest()[:8]
    return f"FigmaChunk{h.upper()}"


def _is_extractable(node: CleanDesignTreeNode) -> bool:
    """True when this node is safe to extract as a standalone StatelessWidget.

    Args:
        node: Candidate node for extraction.

    Returns:
        False for leaf types, existing stubs, or nodes that already carry a
        widget reference.
    """
    if node.extracted_widget_ref:
        return False  # already a ref stub — do not double-extract
    if node.type in _LEAF_TYPES:
        return False  # leaf — wrapping adds boilerplate with no benefit
    return True
