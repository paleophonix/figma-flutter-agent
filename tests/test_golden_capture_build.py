"""Tests for golden-capture Docker image preflight."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.dev.golden_capture_build import (
    GOLDEN_CAPTURE_IMAGE,
    ensure_golden_capture_image,
    golden_capture_preflight,
)


def test_golden_capture_preflight_none_when_image_present() -> None:
    with (
        patch(
            "figma_flutter_agent.dev.golden_capture_build.docker_cli_available",
            return_value=True,
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.golden_capture_image_present",
            return_value=True,
        ),
    ):
        assert golden_capture_preflight() is None


def test_golden_capture_preflight_when_image_missing(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.dev.golden_capture_build.docker_cli_available",
            return_value=True,
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.golden_capture_image_present",
            return_value=False,
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.golden_compose_file",
            return_value=compose,
        ),
    ):
        preflight = golden_capture_preflight()
    assert preflight is not None
    assert preflight.image_name == GOLDEN_CAPTURE_IMAGE


def test_ensure_golden_capture_image_build_if_missing(tmp_path: Path) -> None:
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")
    with (
        patch(
            "figma_flutter_agent.dev.golden_capture_build.docker_cli_available",
            return_value=True,
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.golden_capture_image_present",
            side_effect=[False, True],
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.golden_compose_file",
            return_value=compose,
        ),
        patch(
            "figma_flutter_agent.dev.golden_capture_build.build_golden_capture_image",
            return_value=GOLDEN_CAPTURE_IMAGE,
        ) as build_mock,
    ):
        ok = ensure_golden_capture_image(build_if_missing=True, print_hint=False)
    assert ok is True
    build_mock.assert_called_once()


def test_capture_ensures_docker_image_before_compose(monkeypatch) -> None:
    from figma_flutter_agent.validation import golden_capture as gc_mod

    calls: list[bool] = []

    def _ensure(settings=None):
        del settings
        calls.append(True)
        return None

    monkeypatch.setattr(
        gc_mod.capture,
        "resolve_golden_runtime",
        lambda *a, **k: type(
            "Sel",
            (),
            {"runtime": "docker", "configured": "docker", "fallback_from_docker": False},
        )(),
    )
    monkeypatch.setattr(gc_mod.capture, "_ensure_docker_golden_image", _ensure)
    monkeypatch.setattr(
        gc_mod.capture,
        "capture_planned_flutter_golden_png_docker",
        lambda *a, **k: gc_mod.GoldenCaptureResult(reason="docker stub"),
    )

    gc_mod.capture_planned_flutter_golden_png({}, feature_name="x")
    assert calls == [True]
