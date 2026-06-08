from figma_flutter_agent.parser.css import build_css_properties
from figma_flutter_agent.parser.effects import (
    derive_elevation,
    extract_gradient_fill,
    extract_shadow_effects,
)
from figma_flutter_agent.parser.style_refs import resolve_style_name
from figma_flutter_agent.parser.styles import (
    enrich_node_style,
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


def test_enrich_node_style_populates_css_from_rest() -> None:
    """enrich_node_style now auto-builds css_properties from REST data."""
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
    # css_properties is now populated from REST synthesis
    assert style.css_properties["background-color"] == "rgba(255, 0, 0, 1.000)"
    assert style.css_properties["border-radius"] == "12px"   # :g strips .0
    assert style.css_properties["opacity"] == "0.8"


def test_enrich_node_style_blend_mode_extracted() -> None:
    style = enrich_node_style(
        {"fills": [], "blendMode": "MULTIPLY"},
        NodeStyle(),
    )
    assert style.blend_mode == "MULTIPLY"
    assert style.css_properties["mix-blend-mode"] == "multiply"


def test_enrich_node_style_normal_blend_mode_omitted() -> None:
    style = enrich_node_style(
        {"fills": [], "blendMode": "NORMAL"},
        NodeStyle(),
    )
    assert style.blend_mode is None
    assert "mix-blend-mode" not in style.css_properties


def test_resolve_style_name_from_published_styles() -> None:
    name = resolve_style_name(
        {"styles": {"fill": "abc123"}},
        {"abc123": {"name": "Typography/Heading"}},
    )
    assert name == "Typography/Heading"


def test_build_style_paint_index_resolves_style_documents() -> None:
    from figma_flutter_agent.parser.style_refs import build_style_paint_index

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
    assert style.css_properties["background-color"] == "rgba(0, 0, 255, 1.000)"


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


def test_build_css_properties_typography_fields() -> None:
    style = NodeStyle(
        font_family="Inter",
        font_size=16.0,
        font_weight="w700",
        font_style="italic",
        text_align="CENTER",
        line_height=1.5,
        letter_spacing=0.5,
    )
    css = build_css_properties(style)
    assert css["font-family"] == "Inter"
    assert css["font-size"] == "16px"
    assert css["font-weight"] == "700"
    assert css["font-style"] == "italic"
    assert css["text-align"] == "center"
    assert css["line-height"] == "1.5"
    assert css["letter-spacing"] == "0.5px"


def test_build_css_properties_blend_mode() -> None:
    style = NodeStyle(blend_mode="MULTIPLY")
    css = build_css_properties(style)
    assert css["mix-blend-mode"] == "multiply"


def test_build_css_properties_layer_blur() -> None:
    style = NodeStyle(layer_blur=8.0)
    css = build_css_properties(style)
    assert css["filter"] == "blur(8px)"


def test_build_css_properties_normal_blend_mode_omitted() -> None:
    """NORMAL and PASS_THROUGH must not appear in CSS (browser default)."""
    for mode in ("NORMAL", "PASS_THROUGH"):
        style = NodeStyle(blend_mode=mode)
        css = build_css_properties(style)
        assert "mix-blend-mode" not in css


def test_enrich_node_style_ignores_zero_opacity_stroke() -> None:
    style = enrich_node_style(
        {
            "strokes": [
                {
                    "opacity": 0.0,
                    "blendMode": "NORMAL",
                    "type": "SOLID",
                    "color": {"r": 0, "g": 0, "b": 0, "a": 1},
                }
            ],
            "strokeWeight": 1.0,
        },
        NodeStyle(),
    )

    assert style.has_stroke is False
    assert style.border_color is None


def test_extract_blur_effects_splits_layer_and_background() -> None:
    from figma_flutter_agent.parser.effects import extract_blur_effects

    node = {
        "effects": [
            {"type": "LAYER_BLUR", "radius": 12, "visible": True},
            {"type": "BACKGROUND_BLUR", "radius": 24, "visible": True},
        ]
    }
    layer, background = extract_blur_effects(node)
    assert layer == 12.0
    assert background == 24.0
