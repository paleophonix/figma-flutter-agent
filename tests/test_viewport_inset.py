from figma_flutter_agent.config import Settings
from figma_flutter_agent.parser.viewport_inset import (
    apply_viewport_top_inset_to_tree,
    compute_viewport_top_inset_px,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType, Sizing, StackPlacement


def test_compute_viewport_top_inset_for_responsive_phone_stack() -> None:
    root = CleanDesignTreeNode(
        id="1:1",
        name="screen",
        type=NodeType.STACK,
        sizing=Sizing(width=414.0, height=896.0),
        children=[
            CleanDesignTreeNode(
                id="1:2",
                name="back",
                type=NodeType.BUTTON,
                stack_placement=StackPlacement(left=38.0, top=64.0, width=55.0, height=55.0),
            ),
        ],
    )
    settings = Settings()
    inset = compute_viewport_top_inset_px(settings, root, use_scaffold=False)
    assert inset == settings.agent.responsive.status_bar_inset_px


def test_apply_viewport_top_inset_shifts_top_placement() -> None:
    node = CleanDesignTreeNode(
        id="1:2",
        name="back",
        type=NodeType.BUTTON,
        stack_placement=StackPlacement(left=38.0, top=64.0, width=55.0, height=55.0),
    )
    apply_viewport_top_inset_to_tree(node, 44.0)
    assert node.stack_placement is not None
    assert node.stack_placement.top == 20.0
