from figma_flutter_agent.parser.layout import infer_container_type
from figma_flutter_agent.schemas import NodeType


def test_infer_container_type_maps_horizontal_wrap_to_wrap() -> None:
    node = {"layoutMode": "HORIZONTAL", "layoutWrap": "WRAP"}

    assert infer_container_type(node) == NodeType.WRAP


def test_infer_container_type_maps_vertical_wrap_to_wrap() -> None:
    node = {"layoutMode": "VERTICAL", "layoutWrap": "WRAP"}

    assert infer_container_type(node) == NodeType.WRAP


def test_infer_container_type_keeps_horizontal_without_wrap_as_row() -> None:
    node = {"layoutMode": "HORIZONTAL", "layoutWrap": "NO_WRAP"}

    assert infer_container_type(node) == NodeType.ROW


def test_infer_container_type_maps_grid_layout_mode() -> None:
    node = {"layoutMode": "GRID"}

    assert infer_container_type(node) == NodeType.GRID
