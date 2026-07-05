"""Regression tests for mobile_settings cluster delegate reconcile clobber."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from figma_flutter_agent.config.models import WidgetExtractionConfig
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.generator.widget_extraction.collect import collect_widget_specs
from figma_flutter_agent.generator.widget_extraction.enrich import apply_widget_enrich_response
from figma_flutter_agent.generator.widget_extractor import render_cluster_widgets
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.schemas.reusable_candidates import WidgetEnrichResponse

_FIXTURE = Path(".debug/screen/limbo/mobile_settings/processed.json")
_ENRICH = Path(".debug/screen/limbo/mobile_settings/widget_enrich.json")


def _load_root() -> CleanDesignTreeNode:
    if not _FIXTURE.is_file():
        pytest.skip("mobile_settings debug dumps not available")
    processed = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    return CleanDesignTreeNode.model_validate(processed["cleanTree"])


def _cluster_summary(root: CleanDesignTreeNode) -> dict[str, int]:
    counts: Counter[str] = Counter()

    def walk(node: CleanDesignTreeNode) -> None:
        if node.cluster_id:
            counts[node.cluster_id] += 1
        for child in node.children:
            walk(child)

    walk(root)
    return dict(counts)


def _collect_enriched_specs(root: CleanDesignTreeNode):
    if not _ENRICH.is_file():
        pytest.skip("mobile_settings widget_enrich.json not available")
    config = WidgetExtractionConfig()
    specs = collect_widget_specs(
        root,
        cluster_summary=_cluster_summary(root),
        config=config,
        llm_candidates=None,
    )
    enrich_raw = json.loads(_ENRICH.read_text(encoding="utf-8"))
    enrich = WidgetEnrichResponse.model_validate(enrich_raw["response"])
    return apply_widget_enrich_response(specs, enrich, widget_suffix="Widget")


def _planned_mobile_settings_bundle(root: CleanDesignTreeNode) -> tuple[dict[str, str], dict[str, str], list]:
    specs = _collect_enriched_specs(root)
    cluster_result = render_cluster_widgets(specs, uses_svg=True, clean_trees=[root])
    layout_files = render_layout_file(
        root,
        feature_name="mobile_settings",
        cluster_classes=cluster_result.cluster_classes,
        uses_svg=True,
        theme_variant="material",
    )
    planned = dict(cluster_result.files)
    planned.update(layout_files)
    return planned, cluster_result.cluster_classes, specs


def test_mobile_settings_list_item_uses_chevron_delegate_after_reconcile() -> None:
    root = _load_root()
    planned, cluster_classes, specs = _planned_mobile_settings_bundle(root)
    reconciled = reconcile_planned_dart_files(
        planned,
        clean_tree=root,
        cluster_summary=_cluster_summary(root),
        widget_suffix="Widget",
        uses_svg=True,
        incremental=False,
        cluster_classes=cluster_classes,
        cluster_widget_specs=specs,
    )
    list_item = reconciled["lib/widgets/settings_list_item_widget.dart"]
    assert "ChevronButtonWidget" in list_item
    assert "const DividerWidget()" not in list_item


def test_mobile_settings_divider_and_tab_bar_stay_separate_after_reconcile() -> None:
    root = _load_root()
    planned, cluster_classes, specs = _planned_mobile_settings_bundle(root)
    reconciled = reconcile_planned_dart_files(
        planned,
        clean_tree=root,
        cluster_summary=_cluster_summary(root),
        widget_suffix="Widget",
        uses_svg=True,
        incremental=False,
        cluster_classes=cluster_classes,
        cluster_widget_specs=specs,
    )
    divider = reconciled["lib/widgets/settings_divider_widget.dart"]
    tab_bar = reconciled["lib/widgets/settings_tab_bar_widget.dart"]
    assert "_LayoutChromeNav" not in divider
    assert "_LayoutChromeNav" in tab_bar


def test_mobile_settings_layout_references_profile_avatar_delegate() -> None:
    root = _load_root()
    planned, cluster_classes, _specs = _planned_mobile_settings_bundle(root)
    layout = planned["lib/generated/mobile_settings_layout.dart"]
    assert "ProfileAvatarWidget" in layout
    assert layout.count("const DividerWidget()") < layout.count("ChevronButtonWidget")
