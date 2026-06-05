"""Typography normalization tests."""

from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.parser.typography import (
    resolve_font_family,
    resolve_font_weight,
    resolve_letter_spacing,
)


def test_resolve_font_weight_prefers_medium_face_over_numeric_400() -> None:
    style = {
        "fontWeight": 400,
        "fontPostScriptName": "HelveticaNeueMedium",
        "fontStyle": "Medium",
    }

    assert resolve_font_weight(style) == "w500"


def test_resolve_font_weight_maps_light_face_to_w300() -> None:
    style = {
        "fontWeight": 300,
        "fontPostScriptName": "HelveticaNeueLight",
        "fontStyle": "Light",
    }

    assert resolve_font_weight(style) == "w300"


def test_resolve_font_weight_maps_extrabold_face_to_w800_not_w700() -> None:
    style = {
        "fontWeight": 800,
        "fontPostScriptName": None,
        "fontStyle": "ExtraBold",
        "fontFamily": "Golos Text",
    }

    assert resolve_font_weight(style) == "w800"


def test_build_clean_tree_uses_extrabold_weight_for_golos_heading() -> None:
    root = {
        "id": "0",
        "name": "Frame",
        "type": "FRAME",
        "layoutMode": "NONE",
        "absoluteBoundingBox": {"width": 200, "height": 40},
        "children": [
            {
                "id": "1",
                "name": "Heading 1",
                "type": "TEXT",
                "characters": "Личные данные",
                "style": {
                    "fontFamily": "Golos Text",
                    "fontPostScriptName": None,
                    "fontStyle": "ExtraBold",
                    "fontWeight": 800,
                    "fontSize": 17.0,
                },
                "fills": [{"type": "SOLID", "color": {"r": 0, "g": 0, "b": 0, "a": 1}}],
            }
        ],
    }

    tree, _, _, _ = build_clean_tree(root)
    text_node = tree.children[0]

    assert text_node.style.font_weight == "w800"


def test_resolve_font_family_normalizes_helvetica_neue() -> None:
    assert resolve_font_family({"fontFamily": "HelveticaNeue"}) == "Helvetica Neue"


def test_resolve_letter_spacing_rounds_pixel_tracking() -> None:
    spacing = resolve_letter_spacing({"letterSpacing": 0.7000000000000001}, font_size=14.0)

    assert spacing == 0.7


def test_build_clean_tree_uses_medium_weight_for_facebook_label() -> None:
    root = {
        "id": "0",
        "name": "Frame",
        "type": "FRAME",
        "layoutMode": "NONE",
        "absoluteBoundingBox": {"width": 200, "height": 40},
        "children": [
            {
                "id": "1",
                "name": "CONTINUE WITH FACEBOOK",
                "type": "TEXT",
                "characters": "CONTINUE WITH FACEBOOK",
                "style": {
                    "fontFamily": "HelveticaNeue",
                    "fontPostScriptName": "HelveticaNeueMedium",
                    "fontStyle": "Medium",
                    "fontWeight": 400,
                    "fontSize": 14.0,
                    "letterSpacing": 0.7000000000000001,
                },
                "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1, "a": 1}}],
            }
        ],
    }

    tree, _, _, _ = build_clean_tree(root)
    text_node = tree.children[0]

    assert text_node.style.font_weight == "w500"
    assert text_node.style.font_family == "Helvetica Neue"
    assert text_node.style.letter_spacing == 0.7
