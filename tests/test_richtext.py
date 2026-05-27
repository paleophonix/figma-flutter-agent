"""Rich text span extraction tests."""

from figma_flutter_agent.parser.richtext import extract_text_span_parts
from figma_flutter_agent.parser.tree import build_clean_tree


def test_extract_text_span_parts_mixed_colors() -> None:
    node = {
        "id": "1",
        "name": "Footer",
        "type": "TEXT",
        "characters": "ALREADY HAVE AN ACCOUNT? SIGN UP",
        "characterStyleOverrides": [0] * 25 + [1] * 7,
        "styleOverrideTable": {
            "1": {
                "fills": [
                    {"type": "SOLID", "color": {"r": 0.557, "g": 0.584, "b": 0.698, "a": 1.0}}
                ],
                "style": {"fontWeight": 700},
            }
        },
        "style": {"fontSize": 14, "fontWeight": 400},
        "fills": [{"type": "SOLID", "color": {"r": 0.631, "g": 0.643, "b": 0.698, "a": 1.0}}],
    }

    spans = extract_text_span_parts(node)

    assert spans is not None
    assert len(spans) == 2
    assert spans[0].text == "ALREADY HAVE AN ACCOUNT? "
    assert spans[1].text == "SIGN UP"
    assert spans[1].text_color is not None
    assert spans[1].font_weight == "w700"
    assert spans[1].is_link is True


def test_build_clean_tree_attaches_text_spans() -> None:
    root = {
        "id": "0",
        "name": "Frame",
        "type": "FRAME",
        "layoutMode": "NONE",
        "absoluteBoundingBox": {"width": 200, "height": 40},
        "children": [
            {
                "id": "1",
                "name": "Footer",
                "type": "TEXT",
                "characters": "Hello World",
                "characterStyleOverrides": [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1],
                "styleOverrideTable": {
                    "1": {
                        "fills": [
                            {"type": "SOLID", "color": {"r": 1.0, "g": 0.0, "b": 0.0, "a": 1.0}}
                        ],
                    }
                },
                "style": {"fontSize": 12},
                "fills": [{"type": "SOLID", "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 1.0}}],
            }
        ],
    }

    tree, _, _, _ = build_clean_tree(root)
    text_node = tree.children[0]

    assert len(text_node.text_spans) == 2
    assert text_node.text_spans[0].text == "Hello "
    assert text_node.text_spans[1].text == "World"
