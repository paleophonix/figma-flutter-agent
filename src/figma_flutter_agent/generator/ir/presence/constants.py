"""IR presence constants."""

from __future__ import annotations

from figma_flutter_agent.schemas import NodeType

STACK_VISUAL_NODE_TYPES = frozenset(
    {
        NodeType.VECTOR,
        NodeType.IMAGE,
        NodeType.CONTAINER,
    }
)
MIN_STACK_VISUAL_IR_COVERAGE = 0.95
MAX_STACK_VISUAL_IR_INSERTS = 40
MAX_PRESENCE_SUBTREE_IR_INSERTS = 40
MAX_SYNC_STACK_IR_NODES = 120
STRUCTURAL_IR_SYNC_TYPES = frozenset(
    {
        NodeType.STACK,
        NodeType.COLUMN,
        NodeType.ROW,
        NodeType.TEXT,
        NodeType.BUTTON,
        NodeType.INPUT,
        NodeType.CHECKBOX,
        NodeType.SWITCH,
        NodeType.RADIO,
        NodeType.RADIO_GROUP,
        NodeType.DROPDOWN,
        NodeType.SLIDER,
        NodeType.TABS,
        NodeType.BOTTOM_NAV,
        NodeType.CARD,
    }
)
