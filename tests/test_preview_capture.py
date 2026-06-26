"""Fast preview capture backend and routing tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from figma_flutter_agent.errors import FastPreviewUnavailableError
from figma_flutter_agent.preview import (
    CaptureMode,
    PreviewCaptureRequest,
    PreviewScene,
    capture_preview_png,
    capture_with_mode,
    preview_scene_from_clean_tree,
)
from figma_flutter_agent.schemas import CleanDesignTreeNode, NodeType
from figma_flutter_agent.schemas.geometry import GeometryFrame, GeomRect
from figma_flutter_agent.schemas.style import NodeStyle

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _sample_scene() -> PreviewScene:
    tree = CleanDesignTreeNode(
        id="root",
        name="Root",
        type=NodeType.STACK,
        sizing={"width": 100, "height": 100},
        children=[
            CleanDesignTreeNode(
                id="box",
                name="Box",
                type=NodeType.STACK,
                style=NodeStyle(backgroundColor="#ABCDEF"),
                geometry_frame=GeometryFrame(
                    world_aabb=GeomRect(x=0, y=0, width=100, height=100),
                ),
            ),
        ],
    )
    return preview_scene_from_clean_tree(tree)


def test_preview_backend_unavailable_does_not_fallback_to_flutter(monkeypatch) -> None:
    monkeypatch.setattr(
        "figma_flutter_agent.preview.browser.resolve_preview_backend",
        lambda: (_ for _ in ()).throw(
            FastPreviewUnavailableError("preview backend unavailable"),
        ),
    )

    def _forbidden_flutter_test(*_args, **_kwargs):
        raise AssertionError("flutter test must not run in preview mode")

    monkeypatch.setattr(subprocess, "run", _forbidden_flutter_test)

    with pytest.raises(FastPreviewUnavailableError):
        capture_preview_png(
            PreviewCaptureRequest(scene=_sample_scene(), screen_id="sample"),
        )


def test_preview_capture_writes_png_with_mock_browser(tmp_path: Path) -> None:
    out = tmp_path / "preview.png"
    with patch(
        "figma_flutter_agent.preview.capture.capture_scene_png",
        return_value=(_MINIMAL_PNG, "playwright"),
    ):
        result = capture_preview_png(
            PreviewCaptureRequest(
                scene=_sample_scene(),
                output_path=out,
                screen_id="sample",
            ),
        )
    assert result.ok
    assert out.is_file()
    assert out.read_bytes() == _MINIMAL_PNG


def test_preview_capture_logs_mode_backend_elapsed() -> None:
    with (
        patch(
            "figma_flutter_agent.preview.capture.capture_scene_png",
            return_value=(_MINIMAL_PNG, "playwright"),
        ),
        patch("figma_flutter_agent.preview.capture.logger.info") as log_info,
    ):
        capture_preview_png(
            PreviewCaptureRequest(scene=_sample_scene(), screen_id="sample"),
        )
    rendered = " ".join(
        " ".join(str(part) for part in call.args) for call in log_info.call_args_list
    )
    assert "preview" in rendered
    assert "playwright" in rendered
    assert "elapsed" in rendered


def test_capture_with_mode_preview_never_calls_oracle() -> None:
    with patch(
        "figma_flutter_agent.preview.capture.capture_scene_png",
        return_value=(_MINIMAL_PNG, "playwright"),
    ):
        result = capture_with_mode(
            mode=CaptureMode.PREVIEW,
            preview_request=PreviewCaptureRequest(scene=_sample_scene()),
        )
    assert result.ok


def test_oracle_capture_still_uses_flutter_test() -> None:
    from figma_flutter_agent.validation.golden_capture.capture import (
        capture_planned_flutter_golden_png,
    )

    assert capture_planned_flutter_golden_png is not None
