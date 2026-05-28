from figma_flutter_agent.parser.text_line_height import (
    flutter_text_style_height_ratio,
    resolve_line_height,
)


def test_resolve_line_height_pixels_divides_by_font_size() -> None:
    ratio = resolve_line_height(
        {"lineHeightPx": 17.1, "fontSize": 14.0},
        font_size=14.0,
    )
    assert ratio == 1.22


def test_resolve_line_height_object_pixels_unit() -> None:
    ratio = resolve_line_height(
        {"lineHeight": {"unit": "PIXELS", "value": 17.1}, "fontSize": 14.0},
        font_size=14.0,
    )
    assert ratio == 1.22


def test_resolve_line_height_percent_font_size() -> None:
    ratio = resolve_line_height(
        {"lineHeightPercentFontSize": 120.0, "fontSize": 10.0},
        font_size=10.0,
    )
    assert ratio == 1.2


def test_flutter_text_style_height_ratio_divides_pixel_values() -> None:
    assert flutter_text_style_height_ratio(17.1, font_size=14.0) == 1.22
    assert flutter_text_style_height_ratio(1.22, font_size=14.0) == 1.22
