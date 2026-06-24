"""Tests for release web preview static serving."""

from __future__ import annotations

from pathlib import Path

from control_panel.config.models import PreviewConfig
from control_panel.preview.release import (
    _release_build_argv,
    read_release_preview_file,
    release_build_ready,
    release_output_root,
    release_preview_enabled,
    resolve_release_asset_path,
)


def test_release_build_argv_uses_build_not_run_flags() -> None:
    argv = _release_build_argv(
        "flutter",
        job_id="job123",
        mode="fixed",
        output_dir=Path("out"),
    )
    joined = " ".join(argv)
    assert "--web-hostname" not in joined
    assert "--no-web-resources-cdn" in joined
    assert "--base-href" in joined
    assert "/preview/job123/" in joined


def test_release_preview_enabled_flag() -> None:
    assert release_preview_enabled(PreviewConfig()) is False
    assert release_preview_enabled(PreviewConfig(release_build=True)) is True


def test_resolve_release_asset_path_blocks_traversal(tmp_path: Path) -> None:
    root = release_output_root(tmp_path, "fixed")
    root.mkdir(parents=True)
    (root / "index.html").write_text("<html></html>", encoding="utf-8")

    resolved = resolve_release_asset_path(tmp_path, "fixed", "")
    assert resolved == root / "index.html"

    assert resolve_release_asset_path(tmp_path, "fixed", "../secrets.txt") is None


def test_read_release_preview_file_serves_index(tmp_path: Path) -> None:
    root = release_output_root(tmp_path, "fixed")
    root.mkdir(parents=True)
    (root / "index.html").write_text("<html>ok</html>", encoding="utf-8")

    assert release_build_ready(tmp_path, "fixed") is True
    status, headers, body = read_release_preview_file(tmp_path, "fixed", "") or (0, {}, b"")
    assert status == 200
    assert "text/html" in headers["content-type"]
    assert b"ok" in body


def test_read_release_preview_file_missing_build_returns_none(tmp_path: Path) -> None:
    assert read_release_preview_file(tmp_path, "fixed", "") is None
