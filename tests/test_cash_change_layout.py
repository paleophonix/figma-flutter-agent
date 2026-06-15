"""Cash change / checkout payment screen layout regressions."""

from __future__ import annotations

import json

from figma_flutter_agent.fixtures.screens_manifest import fixtures_root
from figma_flutter_agent.generator.ir.passes.planner import apply_layout_passes_for_layout_emit
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.generator.subtree import build_cluster_render_context
from figma_flutter_agent.parser.tree import build_clean_tree

_LAYOUT_PATH = fixtures_root() / "layouts" / "cash_change_layout.json"


def _cash_change_layout(*, with_clusters: bool = True) -> str:
    raw = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
    tree, _, _, cluster_summary = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=fixtures_root().parent.parent,
    )
    root = apply_layout_passes_for_layout_emit(root, macro_height_threshold_px=900)
    cluster_classes = None
    cluster_vector_variants = None
    if with_clusters:
        cluster_classes, cluster_vector_variants = build_cluster_render_context(
            root,
            cluster_summary=cluster_summary,
        )
    planned = render_layout_file(
        root,
        feature_name="cash_change",
        uses_svg=True,
        use_geometry_planner=True,
        responsive_enabled=True,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    return "\n".join(planned.values())


def test_cash_change_payment_section_uses_info_icon() -> None:
    layout = _cash_change_layout()
    assert "Icons.info_outline" in layout
    assert "Icons.calendar_today_outlined" not in layout


def test_cash_change_payment_cards_emit_inline_selection_not_margin_widget() -> None:
    layout = _cash_change_layout(with_clusters=False)
    assert "MarginWidget" not in layout
    assert "Icons.check" in layout
    assert layout.count("Icons.check") <= 2


def test_cash_change_unselected_payment_radio_has_light_fill() -> None:
    layout = _cash_change_layout(with_clusters=False)
    marker = "Border.all(color: Color(0xFFD4D4D8), width: 1.0)"
    idx = layout.find(marker)
    assert idx >= 0
    snippet = layout[max(0, idx - 160) : idx + len(marker)]
    assert "BoxDecoration(" in snippet or "decoration:" in snippet
    assert "shape: BoxShape.circle" in snippet


def test_cash_change_prefix_labeled_currency_input_row() -> None:
    layout = _cash_change_layout()
    assert "Сдача с" in layout
    idx = layout.find("Сдача с")
    snippet = layout[idx : idx + 2500]
    assert "InputBorder.none" in snippet
    assert "keyboardType: TextInputType.number" in snippet
    assert "₽" in snippet


def test_cash_change_summary_rows_avoid_fitted_box_labels() -> None:
    layout = _cash_change_layout()
    idx = layout.find("Адрес")
    assert idx >= 0
    snippet = layout[max(0, idx - 400) : idx + 800]
    assert "FittedBox(fit: BoxFit.scaleDown" not in snippet


def test_cash_change_root_responsive_width_on_mobile() -> None:
    layout = _cash_change_layout()
    assert "width: 350.0" not in layout
    assert "EdgeInsets.fromLTRB(20.0, 0.0, 20.0, 24.0)" in layout


def test_cash_change_payment_cards_drop_content_band_min_width() -> None:
    layout = _cash_change_layout()
    assert "minWidth: 277.0" not in layout


def test_cash_change_payment_cards_center_radio_and_single_line_subtitle() -> None:
    layout = _cash_change_layout()
    idx = layout.find("Онлайн после сборки")
    assert idx >= 0
    snippet = layout[max(0, idx - 500) : idx + 1800]
    assert "crossAxisAlignment: CrossAxisAlignment.center" in snippet
    assert "maxLines: 1" in snippet
    assert "softWrap: false" in snippet
    assert "EdgeInsets.only(top: 4.0)" not in snippet


def test_cash_change_payment_subtitle_single_line_card_copy() -> None:
    layout = _cash_change_layout()
    assert "Основная карта" in layout
    idx = layout.find("Основная карта")
    snippet = layout[idx : idx + 400]
    assert "maxLines: 1" in snippet
    assert "softWrap: false" in snippet


def test_cash_change_multiline_payment_subtitles_preserve_figma_breaks() -> None:
    layout = _cash_change_layout()
    courier_idx = layout.find("Картой курьеру")
    assert courier_idx >= 0
    courier_snippet = layout[courier_idx : courier_idx + 1600]
    assert "когда не\\nхотим" in courier_snippet or "когда не\nхотим" in courier_snippet
    assert "maxLines: 2" in courier_snippet
    assert "softWrap: false" not in courier_snippet

    cash_idx = layout.find("Наличными курьеру")
    assert cash_idx >= 0
    cash_snippet = layout[cash_idx : cash_idx + 1600]
    assert "при\\nполучении" in cash_snippet or "при\nполучении" in cash_snippet
    assert "maxLines: 2" in cash_snippet
    assert "strutStyle" not in cash_snippet


def test_cash_change_quick_sum_row_uses_flex_not_positioned_stack() -> None:
    layout = _cash_change_layout()
    assert "Wrap(" in layout or "Row(" in layout
    quick_sum_idx = layout.find("Без сдачи")
    assert quick_sum_idx >= 0
    snippet = layout[max(0, quick_sum_idx - 400) : quick_sum_idx + 1200]
    assert "spacing:" in snippet
    assert snippet.count("Positioned(") <= snippet.count("Positioned.fill(")


def test_cash_change_tall_root_gets_vertical_scroll_after_passes() -> None:
    raw = json.loads(_LAYOUT_PATH.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=fixtures_root().parent.parent,
    )
    from figma_flutter_agent.generator.artboard import resolve_artboard_height
    from figma_flutter_agent.generator.ir.passes.geometry import content_vertical_extent
    from figma_flutter_agent.generator.ir.passes.layout_criteria import evaluate_scroll_host

    root = apply_layout_passes_for_layout_emit(
        root,
        macro_height_threshold_px=900,
        inject_root_scroll_host=True,
    )
    artboard_height = resolve_artboard_height(root)
    extent = content_vertical_extent(root)
    decision = evaluate_scroll_host(
        root,
        artboard_height=artboard_height,
        fallback_threshold_px=900,
    )
    if decision.activated:
        assert root.scroll_axis == "vertical"
        assert root.sizing.height_mode.value == "HUG"
    elif artboard_height is not None and extent <= artboard_height:
        assert root.scroll_axis == "none"
