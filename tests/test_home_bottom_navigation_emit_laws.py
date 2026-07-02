"""Regression tests for 9_a_home_bottom_navigation emit laws."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.dev.opencode.capture_passport import flutter_capture_trusted
from figma_flutter_agent.dev.opencode.failure_class import FailureClass
from figma_flutter_agent.generator.layout.flex_policy.stack import (
    stack_dense_absolute_overlays_preserve_stack,
    stack_should_flow_as_column,
)
from figma_flutter_agent.generator.widget_extractor import _bound_cluster_widget_root
from figma_flutter_agent.schemas import CleanDesignTreeNode, ScreenIr

_HOME_DEBUG = Path(".debug/screen/limbo/9_a_home_bottom_navigation")


def _load_home_root() -> CleanDesignTreeNode:
    path = _HOME_DEBUG / "processed.json"
    if not path.is_file():
        pytest.skip("9_a_home_bottom_navigation debug bundle unavailable")
    processed = json.loads(path.read_text(encoding="utf-8"))
    root = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    from figma_flutter_agent.parser.dedup.hydrate import hydrate_pruned_cluster_instances

    hydrate_pruned_cluster_instances(root)
    return root


def _load_home_screen_ir() -> ScreenIr | None:
    path = _HOME_DEBUG / "pre_emit.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    screen_ir = payload.get("screenIr")
    if not isinstance(screen_ir, dict):
        return None
    return ScreenIr.model_validate(screen_ir)


def _find_node(root: CleanDesignTreeNode, node_id: str) -> CleanDesignTreeNode | None:
    if root.id == node_id:
        return root
    for child in root.children:
        found = _find_node(child, node_id)
        if found is not None:
            return found
    return None


def test_absolute_overlay_density_preservation_law_blocks_home_column_flow() -> None:
    """Law: AbsoluteOverlayDensityPreservationLaw — dense dashboards stay Stack."""
    root = _load_home_root()
    assert stack_dense_absolute_overlays_preserve_stack(root)
    assert stack_should_flow_as_column(root) is False


def test_extracted_widget_fixed_bounds_law_wraps_notification_icon() -> None:
    """Law: ExtractedWidgetFixedBoundsLaw — icon badge widgets get finite bounds."""
    root = _load_home_root()
    notification = _find_node(root, "7342:2848")
    assert notification is not None
    bounded = _bound_cluster_widget_root(notification, "const Inner()")
    assert "SizedBox(width: 30.0, height: 30.0" in bounded


def test_home_replay_layout_preserves_stack_and_bottom_nav() -> None:
    """Law: orchestration replay — home screen keeps Stack geometry and docked nav."""
    from figma_flutter_agent.generator.layout import render_layout_file

    root = _load_home_root()
    screen_ir = _load_home_screen_ir()
    files = render_layout_file(
        root,
        feature_name="9_a_home_bottom_navigation_laws",
        uses_svg=True,
        screen_ir=screen_ir,
        responsive_enabled=True,
    )
    compact = "".join(files.values()).replace("\n", "")
    assert "_LayoutIconNav" in compact
    assert "figma-7342_2848" in compact
    assert compact.count("Align(alignment: Alignment.centerLeft, child: Positioned(") == 0
    layout_key = next(
        (path for path in files if path.endswith("_layout.dart")),
        None,
    )
    assert layout_key is not None
    layout = files[layout_key]
    assert "Stack(clipBehavior:" in layout
    assert "Positioned(right: 36.0, width: 30.0, top: 61.0, height: 30.0" in layout
    assert "RenderFlex overflowed" not in compact


def test_capture_pending_is_not_visual_success() -> None:
    """Law: CAPTURE_PENDING cannot count as a successful visual repair."""
    manifest_path = _HOME_DEBUG / "run_manifest.json"
    if not manifest_path.is_file():
        pytest.skip("run_manifest.json unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("verdict") == FailureClass.CAPTURE_PENDING.value
    passport = manifest.get("capture_passport") or {}
    assert flutter_capture_trusted(passport) is False
    assert passport.get("capture_verified") is False
