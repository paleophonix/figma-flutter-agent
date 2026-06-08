"""Checkout address screen layout regressions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.normalize import normalize_clean_tree
from figma_flutter_agent.generator.subtree_widgets import build_cluster_render_context
from figma_flutter_agent.parser.tree import build_clean_tree

_DUMP = Path(r"e:/@dev/flutter-demo-project/ataev/.figma_debug/raw/checkout_address_layout.json")


def _checkout_layout(*, with_clusters: bool = True) -> str:
    if not _DUMP.is_file():
        pytest.skip("checkout_address Figma dump not available on this machine")
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
        feature_name="checkout_address",
        uses_svg=True,
        use_geometry_planner=True,
        responsive_enabled=True,
        cluster_classes=cluster_classes,
        cluster_vector_variants=cluster_vector_variants,
    )
    return planned["lib/generated/checkout_address_layout.dart"]


def test_checkout_service_rows_emit_checkboxes_not_input_margin_widget() -> None:
    layout = _checkout_layout()
    assert "Checkbox(" in layout
    assert "InputMarginWidget" not in layout
    assert "labelText: 'Input'" not in layout


def test_checkout_comment_field_emits_multiline_textfield() -> None:
    layout = _checkout_layout()
    assert "hintText: 'Позвонить за 5 минут до доставки.'" in layout
    assert "maxLines: null" in layout
    assert layout.count("TextField(") >= 1


def test_checkout_time_chips_use_fitted_box_labels() -> None:
    layout = _checkout_layout()
    idx = layout.find("figma-281_12730")
    assert idx >= 0
    snippet = layout[idx : idx + 1400]
    assert "FittedBox(fit: BoxFit.scaleDown" in snippet


def test_checkout_add_address_button_skips_asymmetric_auto_padding() -> None:
    layout = _checkout_layout()
    idx = layout.find("figma-281_12724")
    assert idx >= 0
    snippet = layout[idx : idx + 1200]
    assert "Center(child:" in snippet
    assert "18.5947265625" not in snippet
    assert "padding: const EdgeInsets.fromLTRB(20.0, 18.6, 20.0, 18.6)" in snippet


def test_checkout_delivery_chips_keep_horizontal_padding_and_width() -> None:
    layout = _checkout_layout()
    idx = layout.find("figma-281_12704")
    assert idx >= 0
    snippet = layout[max(0, idx - 500) : idx + 900]
    assert "padding: const EdgeInsets.fromLTRB(16.0" in snippet
    assert "width: 84.0" in snippet


def test_checkout_service_checkbox_rows_avoid_touch_target_overflow() -> None:
    layout = _checkout_layout()
    idx = layout.find("Checkbox")
    assert idx >= 0
    snippet = layout[max(0, idx - 600) : idx + 400]
    assert "minHeight: 48" not in snippet
    assert "width: 44.0, height: 44.0" not in snippet


def test_checkout_time_slots_emit_start_aligned_wrap() -> None:
    layout = _checkout_layout()
    idx = layout.find("figma-281_12730")
    assert idx >= 0
    snippet = layout[max(0, idx - 900) : idx + 200]
    assert "Wrap(alignment: WrapAlignment.start" in snippet
    assert "Positioned(left: 0.0, top: 0.0, width: 150.0" not in snippet


def test_checkout_service_checkbox_rows_use_stateful_toggle_and_center_labels() -> None:
    layout = _checkout_layout()
    assert "_GeneratedToggleCheckbox(" in layout
    idx = layout.find("Подъем на этаж без лифта")
    assert idx >= 0
    snippet = layout[max(0, idx - 500) : idx + 200]
    assert "crossAxisAlignment: CrossAxisAlignment.center" in snippet


def test_checkout_root_wraps_page_background() -> None:
    layout = _checkout_layout()
    assert "Material(color: Color(0xFFFCFBF8)" in layout
