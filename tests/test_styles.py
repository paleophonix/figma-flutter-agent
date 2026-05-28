from figma_flutter_agent.parser.styles import (
    build_css_properties,
    derive_elevation,
    enrich_node_style,
    extract_gradient_fill,
    extract_shadow_effects,
    resolve_style_name,
)
from figma_flutter_agent.schemas import NodeStyle, ShadowEffect


def test_extract_shadow_effects_and_elevation() -> None:
    effects = extract_shadow_effects(
        {
            "effects": [
                {
                    "type": "DROP_SHADOW",
                    "visible": True,
                    "offset": {"x": 0, "y": 4},
                    "radius": 8,
                    "spread": 0,
                    "color": {"r": 0, "g": 0, "b": 0, "a": 0.25},
                }
            ]
        }
    )

    assert len(effects) == 1
    assert effects[0].kind == "drop"
    assert derive_elevation(effects) == 2.0


def test_extract_gradient_fill_linear() -> None:
    gradient = extract_gradient_fill(
        [
            {
                "type": "GRADIENT_LINEAR",
                "visible": True,
                "gradientStops": [
                    {"position": 0, "color": {"r": 1, "g": 1, "b": 1, "a": 1}},
                    {"position": 1, "color": {"r": 0, "g": 0, "b": 0, "a": 1}},
                ],
                "gradientHandlePositions": [
                    {"x": 0, "y": 0.5},
                    {"x": 1, "y": 0.5},
                ],
            }
        ]
    )

    assert gradient is not None
    assert gradient.type == "linear"
    assert len(gradient.stops) == 2
    assert gradient.angle == 0.0


def test_enrich_node_style_sets_typed_fields_not_css_mirror() -> None:
    style = enrich_node_style(
        {
            "opacity": 0.8,
            "fills": [
                {"type": "SOLID", "visible": True, "color": {"r": 1, "g": 0, "b": 0, "a": 1}}
            ],
            "cornerRadius": 12,
            "styles": {"fill": "style-1"},
        },
        NodeStyle(background_color="0xFFFF0000", border_radius=12),
        published_styles={"style-1": {"name": "Brand/Primary"}},
    )

    assert style.opacity == 0.8
    assert style.style_name == "Brand/Primary"
    assert style.background_color == "0xFFFF0000"
    assert style.border_radius == 12
    assert style.css_properties == {}


def test_resolve_style_name_from_published_styles() -> None:
    name = resolve_style_name(
        {"styles": {"fill": "abc123"}},
        {"abc123": {"name": "Typography/Heading"}},
    )
    assert name == "Typography/Heading"


def test_build_style_paint_index_resolves_style_documents() -> None:
    from figma_flutter_agent.parser.styles import build_style_paint_index

    index = build_style_paint_index(
        {"style-1": {"node_id": "10:1", "name": "Brand/Primary"}},
        {
            "10:1": {
                "fills": [
                    {"type": "SOLID", "visible": True, "color": {"r": 0, "g": 0, "b": 1, "a": 1}}
                ]
            }
        },
    )

    assert "style-1" in index
    assert index["style-1"]["fills"][0]["color"]["b"] == 1


def test_enrich_node_style_resolves_published_fill_style() -> None:
    style = enrich_node_style(
        {
            "fills": [],
            "styles": {"fill": "style-1"},
        },
        NodeStyle(),
        published_styles={"style-1": {"name": "Brand/Primary", "node_id": "10:1"}},
        style_paint_index={
            "style-1": {
                "fills": [
                    {"type": "SOLID", "visible": True, "color": {"r": 0, "g": 0, "b": 1, "a": 1}}
                ]
            }
        },
    )

    assert style.background_color == "0xFF0000FF"
    assert style.style_name == "Brand/Primary"
    assert style.css_properties == {}


def test_build_css_properties_includes_box_shadow() -> None:
    style = NodeStyle(
        effects=[
            ShadowEffect(
                offset_x=0,
                offset_y=2,
                blur=4,
                spread=0,
                color="0x33000000",
            )
        ]
    )
    css = build_css_properties(style)
    assert "box-shadow" in css
