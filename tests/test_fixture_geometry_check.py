"""Fixture geometry check module."""

from __future__ import annotations

from unittest.mock import MagicMock

from figma_flutter_agent.fixtures.geometry_check import check_fixture_geometry
from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest
from figma_flutter_agent.validation.runtime_geometry import GeometryMismatch, RuntimeBounds


def _mock_capture(*, figma_key_rects: dict | None) -> MagicMock:
    capture = MagicMock()
    capture.ok = True
    capture.figma_key_rects = figma_key_rects
    capture.reason = None
    capture.renderflex_overflows = ()
    return capture


def test_check_fixture_geometry_skips_without_figma_keys() -> None:
    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == "sign_up_and_sign_in")
    result = check_fixture_geometry(
        entry,
        min_iou=0.95,
        existing_capture=_mock_capture(figma_key_rects=None),
    )
    assert result.skipped
    assert "figma_keys" in (result.reason or "")


def test_check_fixture_geometry_ok_when_no_mismatches(monkeypatch) -> None:
    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == "sign_up_and_sign_in")
    capture = _mock_capture(
        figma_key_rects={"1_3972": {"left": 1.0, "top": 2.0, "width": 10.0, "height": 10.0}},
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.geometry_feedback_from_mapper_payload",
        lambda *args, **kwargs: "",
    )
    result = check_fixture_geometry(entry, min_iou=0.95, existing_capture=capture)
    assert result.ok
    assert not result.skipped


def test_check_fixture_geometry_fails_on_renderflex_overflow(monkeypatch) -> None:
    from figma_flutter_agent.config import apply_signoff_profile
    from figma_flutter_agent.config.settings import Settings
    from figma_flutter_agent.validation.golden_capture import GoldenCaptureResult

    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == "sign_up_and_sign_in")
    settings = apply_signoff_profile(Settings())
    capture = GoldenCaptureResult(
        png=b"png",
        figma_key_rects={"1_3972": {"left": 1.0, "top": 2.0, "width": 10.0, "height": 10.0}},
        renderflex_overflows=("RenderFlex overflowed by 11px at history_layout.dart:31",),
    )
    result = check_fixture_geometry(
        entry,
        settings=settings,
        min_iou=0.95,
        existing_capture=capture,
    )
    assert not result.ok
    assert "RenderFlex overflow" in (result.reason or "")


def test_check_fixture_geometry_fails_when_feedback_present(monkeypatch) -> None:
    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == "sign_up_and_sign_in")
    mismatch = GeometryMismatch(
        figma_id="1:3972",
        iou=0.0,
        giou=0.0,
        diou=-1.0,
        expected=RuntimeBounds(0, 0, 10, 10),
        runtime=None,
        delta_left=0,
        delta_top=0,
        missing=True,
    )
    capture = _mock_capture(
        figma_key_rects={"1_3972": {"left": 0, "top": 0, "width": 10, "height": 10}},
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.geometry_feedback_from_mapper_payload",
        lambda *args, **kwargs: mismatch.format_feedback_line(),
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.load_runtime_bounds_json",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.compare_runtime_to_figma",
        lambda *args, **kwargs: [mismatch],
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.collect_subtree_widget_specs",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "figma_flutter_agent.fixtures.geometry_check.collect_interactive_placement_ids",
        lambda root: ["1:3972"],
    )
    result = check_fixture_geometry(entry, min_iou=0.95, existing_capture=capture)
    assert not result.ok
    assert result.mismatch_count == 1
    assert "IoU" in result.feedback
