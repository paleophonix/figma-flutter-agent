"""Screen IR presence injection for large subtree widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.presence import (
    _build_clean_parent_map,
    _stack_visual_node_requires_ir,
    _subtree_root_ids,
    ensure_presence_subtrees_in_screen_ir,
    ensure_stack_visual_nodes_in_screen_ir,
    normalize_screen_ir_presence,
    validate_stack_visual_ir_coverage,
)
from figma_flutter_agent.generator.ir.tree import index_clean_tree
from figma_flutter_agent.generator.ir.validate import validate_extracted_widgets, validate_screen_ir
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    ExtractedWidget,
    NodeStyle,
    NodeType,
    ScreenIr,
    Sizing,
    StackPlacement,
    WidgetIrKind,
    WidgetIrNode,
    WidgetIrRef,
)


def _vector_subtree(
    node_id: str,
    *,
    width: float,
    height: float,
    top: float,
    count: int = 10,
) -> CleanDesignTreeNode:
    return CleanDesignTreeNode(
        id=node_id,
        name="Group",
        type=NodeType.STACK,
        sizing=Sizing(width=width, height=height),
        stack_placement=StackPlacement(left=40.0, top=top, width=width, height=height),
        children=[
            CleanDesignTreeNode(id=f"{node_id}:v", name="Vector", type=NodeType.VECTOR)
            for _ in range(count)
        ],
    )


def test_ensure_presence_injects_missing_subtree_nodes() -> None:
    illustration = _vector_subtree("1:3677", width=332.0, height=243.0, top=160.0)
    logo = _vector_subtree("1:3665", width=168.0, height=30.0, top=6.0, count=10)
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            logo,
            illustration,
            CleanDesignTreeNode(
                id="1:99",
                name="Title",
                type=NodeType.TEXT,
                text="We are what we do",
                stack_placement=StackPlacement(left=58.0, top=534.0, width=300.0, height=42.0),
            ),
        ],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:1",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="1:99", kind=WidgetIrKind.TEXT, children=[]),
            ],
        ),
    )
    patched = ensure_presence_subtrees_in_screen_ir(screen_ir, root, widget_suffix="Widget")
    child_ids = {child.figma_id for child in patched.root.children}
    assert "1:3665" in child_ids
    assert "1:3677" in child_ids


def test_ensure_stack_visual_injects_missing_vector_nodes() -> None:
    vector = CleanDesignTreeNode(
        id="1:50",
        name="Icon",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=10.0, top=20.0, width=24.0, height=24.0),
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[vector],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.STACK, children=[]),
    )
    patched = ensure_stack_visual_nodes_in_screen_ir(screen_ir, root)
    child_ids = {child.figma_id for child in patched.root.children}
    assert "1:50" in child_ids


def test_normalize_creates_missing_stack_parent_frame() -> None:
    v1 = CleanDesignTreeNode(
        id="1:3663",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=3.0, top=-1.0, width=415.0, height=503.0),
    )
    frame = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=423.0, height=504.0),
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[v1],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[frame],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:1", kind=WidgetIrKind.STACK, children=[]),
    )
    patched = normalize_screen_ir_presence(screen_ir, root)
    child_ids = {child.figma_id for child in patched.root.children}
    assert "1:3662" in child_ids
    frame_ir = next(c for c in patched.root.children if c.figma_id == "1:3662")
    assert "1:3663" in {c.figma_id for c in frame_ir.children}
    validate_stack_visual_ir_coverage(patched, root)


def test_normalize_injects_nested_stack_vectors_and_passes_coverage() -> None:
    v1 = CleanDesignTreeNode(
        id="1:3663",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=3.0, top=-1.0, width=415.0, height=503.0),
    )
    v2 = CleanDesignTreeNode(
        id="1:3664",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=0.0, top=0.0, width=423.0, height=70.7),
    )
    frame = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=423.0, height=504.0),
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[v1, v2],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[frame],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:1",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(figma_id="1:3662", kind=WidgetIrKind.STACK, children=[]),
            ],
        ),
    )
    patched = normalize_screen_ir_presence(screen_ir, root)
    frame_ir = next(c for c in patched.root.children if c.figma_id == "1:3662")
    child_ids = {c.figma_id for c in frame_ir.children}
    assert "1:3663" in child_ids
    assert "1:3664" in child_ids
    validate_stack_visual_ir_coverage(patched, root)


def test_sync_downgrades_phantom_extracted_and_injects_vectors() -> None:
    v1 = CleanDesignTreeNode(
        id="1:3663",
        name="Vector",
        type=NodeType.VECTOR,
        vector_asset_key="assets/icons/vector_1_3663.svg",
        stack_placement=StackPlacement(left=3.0, top=-1.0, width=415.0, height=503.0),
    )
    frame = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=423.0, height=504.0),
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[v1],
    )
    root = CleanDesignTreeNode(
        id="1:1",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[frame],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:1",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="1:3662",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="MissingWidget"),
                    children=[],
                ),
            ],
        ),
    )
    patched = normalize_screen_ir_presence(screen_ir, root, extracted_widget_names=frozenset())
    frame_ir = next(c for c in patched.root.children if c.figma_id == "1:3662")
    assert frame_ir.kind == WidgetIrKind.STACK
    assert "1:3663" in {c.figma_id for c in frame_ir.children}
    validate_stack_visual_ir_coverage(patched, root, extracted_widget_names=frozenset())


def test_phantom_extracted_on_frame_downgrades_and_passes_coverage() -> None:
    v1 = CleanDesignTreeNode(
        id="1:3663",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=3.0, top=-1.0, width=415.0, height=503.0),
    )
    frame = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=423.0, height=504.0),
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[v1],
    )
    logo = _vector_subtree("1:3665", width=168.0, height=30.0, top=6.0, count=10)
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[frame, logo],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(
            figma_id="1:3661",
            kind=WidgetIrKind.STACK,
            children=[
                WidgetIrNode(
                    figma_id="1:3662",
                    kind=WidgetIrKind.EXTRACTED,
                    ref=WidgetIrRef(widget_name="Group17Widget"),
                    children=[],
                ),
            ],
        ),
    )
    extracted = frozenset({"Group17Widget"})
    patched = normalize_screen_ir_presence(screen_ir, root, extracted_widget_names=extracted)
    frame_ir = next(c for c in patched.root.children if c.figma_id == "1:3662")
    assert frame_ir.kind == WidgetIrKind.STACK
    assert "1:3663" in {c.figma_id for c in frame_ir.children}
    validate_stack_visual_ir_coverage(patched, root, extracted_widget_names=extracted)


def test_ir_emitter_imports_stack_visual_presence_helper() -> None:
    from figma_flutter_agent.generator.ir.presence import (  # noqa: PLC0415
        ensure_stack_visual_nodes_in_screen_ir,
    )

    assert callable(ensure_stack_visual_nodes_in_screen_ir)


def test_home_indicator_line_does_not_require_stack_visual_ir() -> None:
    line = CleanDesignTreeNode(
        id="1:3977",
        name="Line 2",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=143.0, height=0.0),
        style=NodeStyle(border_width=5.0, border_color="0xFFE6E6E6", has_stroke=True),
        vector_asset_key="assets/icons/line_2_1_3977.svg",
        stack_placement=StackPlacement(
            left=136.0,
            top=838.0,
            right=135.0,
            bottom=14.0,
            width=143.0,
        ),
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[line],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:3661", kind=WidgetIrKind.STACK, children=[]),
    )
    tree_by_id = index_clean_tree(root)
    parent_by_id = _build_clean_parent_map(tree_by_id)
    assert not _stack_visual_node_requires_ir(
        line,
        screen_ir=screen_ir,
        node_id="1:3977",
        parent_by_id=parent_by_id,
        extracted_widget_names=frozenset(),
        subtree_root_ids=_subtree_root_ids(root),
    )


def test_validate_extracted_widgets_skips_screen_stack_visual_coverage() -> None:
    v1 = CleanDesignTreeNode(
        id="1:3663",
        name="Vector",
        type=NodeType.VECTOR,
        stack_placement=StackPlacement(left=3.0, top=-1.0, width=415.0, height=503.0),
    )
    frame = CleanDesignTreeNode(
        id="1:3662",
        name="Frame",
        type=NodeType.STACK,
        sizing=Sizing(width=423.0, height=504.0),
        stack_placement=StackPlacement(left=-3.0, top=0.0, width=423.0, height=504.0),
        children=[v1],
    )
    line = CleanDesignTreeNode(
        id="1:3977",
        name="Line 2",
        type=NodeType.CONTAINER,
        sizing=Sizing(width=143.0, height=0.0),
        style=NodeStyle(border_width=5.0, has_stroke=True),
        vector_asset_key="assets/icons/line_2_1_3977.svg",
        stack_placement=StackPlacement(left=136.0, top=838.0, width=143.0),
    )
    root = CleanDesignTreeNode(
        id="1:3661",
        name="Screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[frame, line],
    )
    screen_ir = ScreenIr(
        root=WidgetIrNode(figma_id="1:3661", kind=WidgetIrKind.STACK, children=[]),
    )
    extracted = [
        ExtractedWidget(
            widget_name="Group17Widget",
            widget_ir=WidgetIrNode(figma_id="1:3665", kind=WidgetIrKind.STACK, children=[]),
        ),
    ]
    ext = frozenset({"Group17Widget"})
    patched = normalize_screen_ir_presence(screen_ir, root, extracted_widget_names=ext)
    validate_screen_ir(
        patched,
        root,
        extracted_widget_names=ext,
        skip_presence_normalize=True,
    )
    validate_extracted_widgets(extracted, root)
