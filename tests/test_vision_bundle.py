"""Tests for recognise vision bundle completeness."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.dev.opencode.vision_bundle import build_vision_bundle


def test_screen_bundle_incomplete_without_figma_png(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    repair_root = tmp_path / ".repair"
    repair_root.mkdir()
    bundle = build_vision_bundle(
        debug_mirror=mirror,
        repair_root=repair_root,
        case_mode="SCREEN",
    )
    assert bundle["complete"] is False
    assert bundle["blockedReason"] == "VISION_BUNDLE_INCOMPLETE"


def test_screen_bundle_requires_flutter_render_when_requested(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "figma.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    repair_root = tmp_path / ".repair"
    repair_root.mkdir()
    bundle = build_vision_bundle(
        debug_mirror=mirror,
        repair_root=repair_root,
        case_mode="SCREEN",
        require_flutter_render=True,
    )
    assert bundle["complete"] is False
    assert bundle["blockedReason"] == "VISION_FLUTTER_RENDER_MISSING"


def test_screen_bundle_complete_with_figma_and_flutter_render(tmp_path: Path) -> None:
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    (mirror / "figma.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (mirror / "flutter_render.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    repair_root = tmp_path / ".repair"
    repair_root.mkdir()
    bundle = build_vision_bundle(
        debug_mirror=mirror,
        repair_root=repair_root,
        case_mode="SCREEN",
        require_flutter_render=True,
    )
    assert bundle["complete"] is True
    assert bundle["blockedReason"] is None
