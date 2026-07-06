"""Payment-plan option row flex emit laws."""

from __future__ import annotations

from figma_flutter_agent.generator.layout.flex_policy.column import wrap_column_child_width_fill
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    NodeStyle,
    NodeType,
    Sizing,
    SizingMode,
)


def test_payment_plan_trailing_price_cluster_skips_rigid_width_pin() -> None:
    """Law: trailing price+radio cluster hugs intrinsic width inside bounded plan rows."""
    price = CleanDesignTreeNode(
        id="1:price",
        name="39,99$",
        type=NodeType.TEXT,
        text="39,99$",
        sizing=Sizing(width=61.0, height=24.0),
    )
    radio = CleanDesignTreeNode(
        id="1:radio",
        name="check_circle",
        type=NodeType.VECTOR,
        sizing=Sizing(width=24.0, height=24.0),
        vector_asset_key="assets/icons/vector_1_radio.svg",
    )
    trailing = CleanDesignTreeNode(
        id="1:trail",
        name="price cluster",
        type=NodeType.ROW,
        spacing=8.0,
        sizing=Sizing(width_mode=SizingMode.FIXED, width=93.0, height=24.0),
        children=[
            CleanDesignTreeNode(
                id="1:body",
                name="Body",
                type=NodeType.COLUMN,
                children=[price],
            ),
            radio,
        ],
    )
    wrapped = wrap_column_child_width_fill("Row(children: [Text('39,99$')])", trailing)
    assert "SizedBox(width: 93.0" not in wrapped.replace("\n", "")
