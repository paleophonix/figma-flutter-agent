"""Tests for AST sidecar preflight and build helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.ast_sidecar_build import (
    ast_sidecar_preflight,
    ensure_ast_sidecar_binary,
)


def test_ast_sidecar_preflight_none_when_prebuilt_exists(tmp_path: Path) -> None:
    bin_dir = tmp_path / "tools" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ast_compiler.exe").write_text("", encoding="utf-8")
    settings = Settings()
    with (
        patch("figma_flutter_agent.dev.ast_sidecar_build.agent_repo_root", return_value=tmp_path),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.prebuilt_compiler_path",
            return_value=bin_dir / "ast_compiler.exe",
        ),
    ):
        assert ast_sidecar_preflight(settings) is None


def test_ast_sidecar_preflight_when_binary_missing(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "build_sidecars.ps1").write_text("", encoding="utf-8")
    settings = Settings()
    with (
        patch("figma_flutter_agent.dev.ast_sidecar_build.agent_repo_root", return_value=tmp_path),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.prebuilt_compiler_path", return_value=None
        ),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.resolve_dart_executable",
            return_value=r"F:\flutter\bin\dart.bat",
        ),
    ):
        preflight = ast_sidecar_preflight(settings)
    assert preflight is not None
    assert preflight.can_build is True
    assert preflight.expected_binary.name == "ast_compiler.exe"


def test_ensure_ast_sidecar_binary_build_if_missing(tmp_path: Path) -> None:
    bin_dir = tmp_path / "tools" / "bin"
    bin_dir.mkdir(parents=True)
    built = bin_dir / "ast_compiler.exe"
    settings = Settings()
    messages: list[str] = []

    def fake_build(*, sdk_root: str | None = None) -> Path:
        built.write_text("exe", encoding="utf-8")
        return built

    with (
        patch("figma_flutter_agent.dev.ast_sidecar_build.agent_repo_root", return_value=tmp_path),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.prebuilt_compiler_path",
            side_effect=[None, built],
        ),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.resolve_dart_executable",
            return_value=r"F:\flutter\bin\dart.bat",
        ),
        patch(
            "figma_flutter_agent.dev.ast_sidecar_build.build_ast_sidecar",
            side_effect=fake_build,
        ),
    ):
        ok = ensure_ast_sidecar_binary(
            settings,
            build_if_missing=True,
            print_hint=False,
            console_print=messages.append,
        )
    assert ok is True
    assert any("Built AST" in message for message in messages)
