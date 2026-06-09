"""Cash change / checkout payment screen layout regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.generator.subtree import build_cluster_render_context
from figma_flutter_agent.parser.tree import build_clean_tree

_DUMP = Path(r"e:/@dev/flutter-demo-project/ataev/.figma_debug/raw/cash_change_layout.json")


def _cash_change_layout(*, with_clusters: bool = True) -> str:
    if not _DUMP.is_file():
        pytest.skip("cash_change Figma dump not available on this machine")
    raw = json.loads(_DUMP.read_text(encoding="utf-8"))
    tree, _, _, cluster_summary = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=False,
        project_dir=_DUMP.parent.parent.parent,
    )
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
    assert "color: Color(0xFFFFFFFF)" in snippet
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


def test_cash_change_root_scrolls_horizontally_on_mobile() -> None:
    layout = _cash_change_layout()
    assert "LayoutBuilder(" in layout
    assert "SizedBox(width:constraints.maxWidth" in layout.replace(" ", "")
    assert "constraints.maxWidth < 390.0" not in layout
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
