"""IR-level Widget Chunking tests.

Verifies that chunk_ir_tree:
  - leaves small trees unchanged (idempotency below budget)
  - splits oversized trees into valid, connected chunks
  - produces class names that are stable across reruns (deterministic)
  - never cuts at leaf/text nodes
  - emits stubs that render_node_body resolves to const ClassName()
  - when integrated in render_layout_file, every output file stays < budget
"""

from __future__ import annotations

import re

from figma_flutter_agent.generator.chunking import (
    CHUNK_TARGET_BYTES,
    _is_extractable,
    chunk_ir_tree,
    estimate_subtree_bytes,
)
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.layout.widgets import render_node_body
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing

# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _leaf(node_id: str, node_type: NodeType = NodeType.CONTAINER) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=node_type,
        sizing=Sizing(width=100.0, height=50.0),
    )


def _column(*children: CleanDesignTreeNode, node_id: str = "col") -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name=node_id,
        type=NodeType.COLUMN,
        sizing=Sizing(width=360.0, height=800.0),
        children=list(children),
    )


def _small_tree() -> CleanDesignTreeNode:
    """Tree well under CHUNK_TARGET_BYTES."""
    return _column(_leaf("a"), _leaf("b"), _leaf("c"))


def _big_section(section_id: str) -> CleanDesignTreeNode:
    """A realistic section subtree with ~12 nodes (> _MIN_CHUNK_NODES=8)."""
    # STACK with 11 leaf children → 12 nodes × 300 = 3600 bytes > _MIN_CHUNK_COST.
    return CleanDesignTreeNode(
        id=section_id,
        name=section_id,
        type=NodeType.STACK,
        sizing=Sizing(width=360.0, height=200.0),
        children=[_leaf(f"{section_id}_n{j}") for j in range(11)],
    )


def _oversized_tree(n_sections: int = 20) -> CleanDesignTreeNode:
    """Tree whose estimate exceeds CHUNK_TARGET_BYTES with extractable sections.

    Each section has 12 nodes (~3600 bytes) > _MIN_CHUNK_COST.
    20 sections → ~72 300 bytes, well above 32 KB budget.
    """
    return _column(*[_big_section(f"section_{i}") for i in range(n_sections)], node_id="root")


# ---------------------------------------------------------------------------
# Unit: chunk_ir_tree
# ---------------------------------------------------------------------------


def test_small_tree_unchanged() -> None:
    tree = _small_tree()
    result = chunk_ir_tree(tree)
    assert not result.was_chunked
    assert result.root is tree


def test_oversized_tree_produces_chunks() -> None:
    tree = _oversized_tree()
    assert estimate_subtree_bytes(tree) > CHUNK_TARGET_BYTES
    result = chunk_ir_tree(tree)
    assert result.was_chunked
    assert len(result.chunks) >= 1


def test_chunk_class_names_are_valid_dart_identifiers() -> None:
    tree = _oversized_tree()
    result = chunk_ir_tree(tree)
    dart_id = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
    for chunk in result.chunks:
        assert dart_id.match(chunk.class_name), f"Invalid Dart id: {chunk.class_name!r}"
        assert not chunk.class_name.startswith("_"), "Chunk class must be public (no leading _)"


def test_chunk_names_stable_across_reruns() -> None:
    """Same tree → same chunk names (idempotent)."""
    tree = _oversized_tree()
    r1 = chunk_ir_tree(tree)
    r2 = chunk_ir_tree(tree)
    names1 = [c.class_name for c in r1.chunks]
    names2 = [c.class_name for c in r2.chunks]
    assert names1 == names2


def test_root_stubs_reference_chunk_class_names() -> None:
    tree = _oversized_tree()
    result = chunk_ir_tree(tree)
    # Collect all extracted_widget_ref values in the modified root.
    refs: set[str] = set()

    def _collect(node: CleanDesignTreeNode) -> None:
        if node.extracted_widget_ref:
            refs.add(node.extracted_widget_ref)
        for child in node.children:
            _collect(child)

    _collect(result.root)
    chunk_names = {c.class_name for c in result.chunks}
    assert refs == chunk_names, f"Stubs {refs} do not match chunk names {chunk_names}"


def test_no_cut_at_text_leaf() -> None:
    """Text/image leaves must never become chunks."""
    text_child = _leaf("txt", NodeType.TEXT)
    tree = _column(
        *[_leaf(f"n{i}") for i in range(100)],
        text_child,
        node_id="root",
    )
    result = chunk_ir_tree(tree)
    for chunk in result.chunks:
        assert chunk.subtree.type not in (NodeType.TEXT, NodeType.IMAGE, NodeType.VECTOR)


def test_stub_renders_as_const_ref() -> None:
    """extracted_widget_ref stub → render_node_body emits const ClassName()."""
    stub = CleanDesignTreeNode(
        id="s1",
        name="s1",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=100.0, height=50.0),
        extracted_widget_ref="FigmaChunkABCD1234",
    )
    body = render_node_body(stub, uses_svg=False)
    assert "FigmaChunkABCD1234" in body
    assert "const" in body


def test_no_double_extraction() -> None:
    """A node already bearing extracted_widget_ref must not be re-extracted."""
    already_stubbed = CleanDesignTreeNode(
        id="already",
        name="already",
        type=NodeType.COLUMN,
        sizing=Sizing(width=360.0, height=400.0),
        extracted_widget_ref="FigmaChunkEXISTING",
        children=[],
    )
    assert not _is_extractable(already_stubbed)


# ---------------------------------------------------------------------------
# Integration: render_layout_file with oversized tree
# ---------------------------------------------------------------------------


def _oversized_layout_tree(n_sections: int = 20) -> CleanDesignTreeNode:
    """Oversized tree with extractable sections for render_layout_file integration tests."""
    return CleanDesignTreeNode(
        id="root",
        name="root",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[_big_section(f"section_{i}") for i in range(n_sections)],
    )


def test_render_layout_file_all_chunks_under_budget() -> None:
    """render_layout_file must produce files all below CHUNK_TARGET_BYTES."""
    tree = _oversized_layout_tree()
    files = render_layout_file(
        tree,
        feature_name="oversized_test",
        uses_svg=False,
        package_name="demo_app",
    )
    assert len(files) > 1, "Expected multiple files for oversized tree"
    for path, content in files.items():
        size = len(content.encode("utf-8"))
        assert size <= CHUNK_TARGET_BYTES, (
            f"{path} is {size} bytes, exceeds budget {CHUNK_TARGET_BYTES}"
        )


def test_render_layout_file_chunk_imports_in_layout() -> None:
    """Layout file must import every chunk file it references."""
    tree = _oversized_layout_tree()
    files = render_layout_file(
        tree,
        feature_name="oversized_test",
        uses_svg=False,
        package_name="demo_app",
    )
    layout_content = files.get("lib/generated/oversized_test_layout.dart", "")
    chunk_paths = [p for p in files if "chunk" in p]
    for chunk_path in chunk_paths:
        # Chunk file stem appears as import in layout.
        stem = chunk_path.split("/")[-1].replace(".dart", "")
        assert stem in layout_content, f"Layout missing import for chunk {chunk_path}"


def test_render_layout_file_class_names_not_broken() -> None:
    """Every chunk file must contain exactly one valid StatelessWidget class."""
    tree = _oversized_layout_tree()
    files = render_layout_file(
        tree,
        feature_name="oversized_test",
        uses_svg=False,
        package_name="demo_app",
    )
    class_re = re.compile(r"class\s+(FigmaChunk\w+)\s+extends\s+StatelessWidget")
    for path, content in files.items():
        if "chunk" not in path:
            continue
        matches = class_re.findall(content)
        assert len(matches) == 1, f"{path}: expected exactly 1 chunk class, got {matches}"


def test_render_layout_file_small_tree_unchanged() -> None:
    """Small trees must produce a single layout file (no chunking)."""
    tree = CleanDesignTreeNode(
        id="root",
        name="simple",
        type=NodeType.COLUMN,
        sizing=Sizing(width=390.0, height=844.0),
        children=[_leaf("a"), _leaf("b")],
    )
    files = render_layout_file(
        tree,
        feature_name="simple_test",
        uses_svg=False,
        package_name="demo_app",
    )
    assert len(files) == 1
    assert "lib/generated/simple_test_layout.dart" in files


def test_widget_import_lines_for_body_cluster_reference() -> None:
    """Chunk bodies must resolve widget imports from cluster class references."""
    from figma_flutter_agent.generator.layout.file_preamble import (
        widget_import_lines_for_body,
    )
    from figma_flutter_agent.generator.paths import ImportContext

    import_context = ImportContext(
        package_name="demo_app",
        use_package_imports=True,
        source_file="lib/generated/cart_chunk_aa.dart",
    )
    lines = widget_import_lines_for_body(
        "children: [const Cluster7Widget(), const Cluster15Widget()]",
        import_context=import_context,
        cluster_classes={"c7": "Cluster7Widget", "c15": "Cluster15Widget"},
    )
    assert "widgets/cluster7_widget.dart" in lines
    assert "widgets/cluster15_widget.dart" in lines


def test_render_layout_file_chunk_includes_widget_imports() -> None:
    """Chunk files must import cluster widgets they reference."""
    tree = _oversized_layout_tree()
    cluster_classes = {f"cluster_{i}": f"Cluster{i}Widget" for i in range(1, 4)}
    files = render_layout_file(
        tree,
        feature_name="oversized_clusters",
        uses_svg=False,
        package_name="demo_app",
        cluster_classes=cluster_classes,
        widget_imports=["cluster1_widget", "cluster2_widget", "cluster3_widget"],
    )
    chunk_paths = [p for p in files if "_chunk_" in p]
    assert chunk_paths, "Expected chunked output for oversized tree"
    for chunk_path in chunk_paths:
        content = files[chunk_path]
        for class_name in cluster_classes.values():
            if f"{class_name}(" in content:
                stem = class_name.replace("Widget", "").lower()
                assert f"widgets/{stem}_widget.dart" in content, (
                    f"{chunk_path} missing import for {class_name}"
                )
