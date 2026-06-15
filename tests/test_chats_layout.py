"""Chats screen layout regressions (list cards, header chrome, section headings)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.parser.tree import build_clean_tree

_DUMP = Path(r"e:/@dev/flutter-demo-project/ataev/.debug/raw/chats_layout.json")


def _chats_layout(*, with_clusters: bool = False) -> str:
    if not _DUMP.is_file():
        pytest.skip("chats Figma dump not available on this machine")
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
        from figma_flutter_agent.generator.subtree import build_cluster_render_context

        cluster_classes, cluster_vector_variants = build_cluster_render_context(
            root,
            cluster_summary=cluster_summary,
        )
    planned = render_layout_file(
        root,
        feature_name="chats",
        uses_svg=True,
        use_geometry_planner=True,
        responsive_enabled=True,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    return planned["lib/generated/chats_layout.dart"]


def test_chats_list_cards_emit_visible_border_stroke() -> None:
    layout = _chats_layout()
    assert "border: Border.all(" in layout
    assert "width: 1.0" in layout
    assert "width: 0.3333333333333333)" not in layout


def test_chats_list_cards_keep_auto_layout_padding() -> None:
    layout = _chats_layout()
    assert "padding: const EdgeInsets.fromLTRB(16.1, 16.1, 16.1, 16.1)" in layout


def test_chats_header_emits_plus_icon_not_empty_vectors() -> None:
    layout = _chats_layout()
    assert "Icons.add" in layout
    nav = layout[layout.find("figma-281_14337") : layout.find("figma-281_14337") + 400]
    assert "SizedBox.shrink()" not in nav


def test_chats_section_headings_are_not_deduplicated_to_one_label() -> None:
    layout = _chats_layout()
    assert layout.count("Открытые чаты") >= 1
    assert "Закрытые чаты" in layout
    assert "const Heading2Widget()" not in layout


def test_chats_list_cards_do_not_center_composite_row_bodies() -> None:
    layout = _chats_layout()
    assert "figma-281_14263" in layout
    card = layout[layout.find("figma-281_14263") : layout.find("figma-281_14263") + 900]
    assert "padding: const EdgeInsets.fromLTRB(16.1, 16.1, 16.1, 16.1)" in card
    assert "child: Center(child: Row(" not in card


def test_chats_list_cards_do_not_cap_body_column_with_overflow_box() -> None:
    layout = _chats_layout()
    card = layout[layout.find("figma-281_14263") : layout.find("figma-281_14263") + 2000]
    assert "SizedBox(height: 97.0, child: SizedBox(height: 97.0" not in card
    assert "Expanded(child: SizedBox(height: 97.0" not in card
    assert "Expanded(child: Align(alignment: Alignment.topCenter, child: OverflowBox(" not in card
    assert "ConstrainedBox(constraints: BoxConstraints(minHeight: 97.0)" in card


def test_chats_header_icon_buttons_emit_without_invisible_stroke_border() -> None:
    layout = _chats_layout()
    for figma_id in ("figma-281_14332", "figma-281_14337"):
        start = layout.find(figma_id)
        assert start >= 0
        snippet = layout[max(0, start - 250) : start + 200]
        assert "border: Border.all(color: Color(0xFF000000)" not in snippet


def test_chats_pill_labels_scale_down_inside_fixed_chip_bounds() -> None:
    layout = _chats_layout()
    for label in ("Text('Поддержка'", "Text('Заказ'", "Text('Закрыт'"):
        idx = layout.find(label)
        assert idx >= 0, label
        snippet = layout[max(0, idx - 120) : idx + 200]
        assert "FittedBox(fit: BoxFit.scaleDown" in snippet
        assert "overflow: TextOverflow.ellipsis" not in snippet


def test_chats_metadata_column_avoids_positioned_timestamp_slots() -> None:
    layout = _chats_layout()
    idx = layout.find("figma-281_14263")
    assert idx >= 0
    snippet = layout[idx : idx + 5500]
    assert "SizedBox(width: 85.2, child: Column(" in snippet
    assert "Text('Сегодня, 11:42'," in snippet
    assert "FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerRight" in snippet
    assert "Positioned(left: 0.0, top: -1.0, width: 85.2" not in snippet


def test_chats_pill_row_uses_bounded_center_not_flex_row() -> None:
    layout = _chats_layout()
    idx = layout.find("Text('Поддержка'")
    assert idx >= 0
    snippet = layout[max(0, idx - 350) : idx + 120]
    assert "Center(child:" in snippet
    assert "SizedBox(width: 64.0, child: Center(" in snippet


def test_chats_open_panel_grows_instead_of_nested_scroll() -> None:
    layout = _chats_layout()
    idx = layout.find("Открытые чаты")
    assert idx >= 0
    snippet = layout[max(0, idx - 1200) : idx + 3500]
    assert "SingleChildScrollView" not in snippet
    assert "height: 393.4" not in snippet
    assert "OverflowBox" not in snippet
    assert "borderRadius: BorderRadius.circular(28.0)" in snippet


def test_chats_section_blocks_flow_in_column_with_gap() -> None:
    layout = _chats_layout()
    assert "height: 893.3" not in layout
    assert "top: 48.0" not in layout
    assert (
        "Stack(clipBehavior: Clip.none, children: [Positioned(left: 0.0, right: 0.0, top: 48.0"
        not in layout
    )
    assert (
        "Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch"
        in layout
    )
    assert "Закрытые чаты" in layout
    assert "SizedBox(height: 18.9)" in layout
    assert "Align(alignment: Alignment.topCenter, child: SizedBox(width: double.infinity" in layout


def test_chats_title_row_keeps_chip_beside_heading_not_at_date_edge() -> None:
    layout = _chats_layout()
    idx = layout.find("figma-281_14263")
    assert idx >= 0
    snippet = layout[idx : idx + 1200]
    assert (
        "Align(alignment: Alignment.centerLeft, child: Row(mainAxisSize: MainAxisSize.min"
        in snippet
    )
    assert (
        "Expanded(child: ConstrainedBox(constraints: BoxConstraints(minHeight: 23.0)" not in snippet
    )
    assert (
        "SizedBox(width: double.infinity, child: Row(mainAxisAlignment: MainAxisAlignment.start"
        not in snippet[:1200]
    )


def test_chats_card_titles_preserve_figma_truncation_markers() -> None:
    layout = _chats_layout()
    assert "Text('Оплата зак…'," in layout
    assert "Text('Доставка з…'," in layout
    assert "Text('Поддерж…'," in layout


def test_chats_card_metadata_column_uses_width_only_extent() -> None:
    layout = _chats_layout()
    assert "SizedBox(width: 85.2, height: 50.5, child: Column(" not in layout
    assert layout.count("SizedBox(width: 85.2, child: Column(") >= 1
    assert "SizedBox(width: 85.1, height: 18.0, child: Stack(" not in layout
    assert "Text('Сегодня, 12:16'," in layout


def test_chats_card_buttons_use_intrinsic_vertical_extent() -> None:
    layout = _chats_layout()
    assert "SizedBox(width: double.infinity, height: 131.1" not in layout
    assert "SizedBox(width: double.infinity, height: 111.2" not in layout
    assert (
        "fit: StackFit.expand, children: [Padding(padding: const EdgeInsets.fromLTRB(16.1, 16.1, 16.1, 16.1)"
        not in layout
    )


def test_chats_flow_survives_viewport_top_inset() -> None:
    """Pipeline applies status-bar inset before emit; stack-local tops must stay intact."""
    if not _DUMP.is_file():
        pytest.skip("chats Figma dump not available on this machine")
    from figma_flutter_agent.parser.viewport_inset import apply_viewport_top_inset_to_tree

    raw = json.loads(_DUMP.read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(raw)
    root = normalize_clean_tree(
        tree,
        use_geometry_planner=True,
        apply_render_safety=True,
        project_dir=_DUMP.parent.parent.parent,
    )
    apply_viewport_top_inset_to_tree(root, 56.0)
    planned = render_layout_file(
        root,
        skip_layout_reconcile=True,
        feature_name="chats",
        uses_svg=True,
        use_geometry_planner=True,
        responsive_enabled=True,
    )
    layout = planned["lib/generated/chats_layout.dart"]
    assert "height: 893.3" not in layout
    assert "top: 48.0" not in layout
    assert "SizedBox(height: 18.9)" in layout
    assert "SizedBox(height: 104.0," in layout


def test_chats_sticky_header_reserves_full_stack_slot_height() -> None:
    layout = _chats_layout()
    assert "SizedBox(height: 104.0," in layout
    assert "top: 48.0" not in layout


def test_chats_closed_card_metadata_avoids_flexible_timestamp() -> None:
    layout = _chats_layout()
    idx = layout.find("figma-281_14302")
    assert idx >= 0
    snippet = layout[idx : idx + 4500]
    assert "Text('25 марта, 16:20'," in snippet
    assert "FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerRight" in snippet
    assert "Flexible(fit: FlexFit.loose, flex: 0, child: SizedBox(height: 18.0" not in snippet
    assert "SizedBox(height: 18.0, child: Semantics(label: '25 марта, 16:20'" not in snippet
    assert "SizedBox(width: 90.0, child: Align(alignment: Alignment.centerRight" in snippet


def test_chats_card_body_keeps_title_and_metadata_visible() -> None:
    layout = _chats_layout()
    idx = layout.find("figma-281_14263")
    assert idx >= 0
    card = layout[idx : idx + 5000]
    assert "Text('Поддерж…'," in card
    assert "Text('Поддержка'" in card
    assert "Text('Сегодня, 11:42'," in card
    assert "SizedBox(width: 85.2, child: Column(" in card
    assert "SizedBox(width: 85.2, height: 50.5, child: Column(" not in card


def test_chats_status_chips_are_not_expanded_in_title_row() -> None:
    layout = _chats_layout()
    idx = layout.find("Text('Поддержка'")
    assert idx >= 0
    snippet = layout[max(0, idx - 400) : idx + 120]
    assert "Expanded(child: SizedBox(height: 25.0" not in snippet
    assert "SizedBox(width: 64.0, child: Center(" in snippet


def test_chats_duplicate_closed_chip_keeps_label() -> None:
    layout = _chats_layout()
    idx = layout.find("figma-281_14302")
    assert idx >= 0
    snippet = layout[idx : idx + 4500]
    assert snippet.count("Text('Закрыт'") >= 1
    assert "SizedBox.shrink()" not in snippet


def test_chats_counter_badge_uses_centered_glyph_path() -> None:
    layout = _chats_layout()
    idx = layout.find("Semantics(label: '1'")
    assert idx >= 0
    snippet = layout[max(0, idx - 250) : idx + 450]
    assert "Center(child:" in snippet
    assert "BoxShape.circle" in snippet
    assert "Row(mainAxisSize: MainAxisSize.min" not in snippet
    assert "textHeightBehavior" in snippet
    assert "width: 25.0, height: 25.0" in snippet
    assert "width: 24.3, height: 25.0" not in snippet


def test_chats_cluster_pills_stay_inlined_not_widget_delegate() -> None:
    layout = _chats_layout(with_clusters=True)
    idx = layout.find("figma-281_14302")
    assert idx >= 0
    snippet = layout[idx : idx + 4500]
    assert snippet.count("Text('Закрыт'") >= 1
    assert "BackgroundBorderWidget" not in snippet
    assert "SizedBox(width: 41.0, child: Center(" in snippet or "SizedBox(width: 41." in snippet
