"""Tests for .figma_debug path helpers."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.debug.paths import (
    full_file_dump_path,
    layout_debug_filename,
    legacy_raw_dump_path,
    processed_dump_path,
    raw_dump_path,
    resolve_screen_raw_dump,
)


def test_layout_debug_filename() -> None:
    assert layout_debug_filename("sign_in") == "sign_in_layout.json"


def test_raw_and_processed_paths() -> None:
    project = Path("/proj")
    assert raw_dump_path(project, "home") == Path(
        "/proj/.figma_debug/raw/home_layout.json"
    )
    assert processed_dump_path(project, "home") == Path(
        "/proj/.figma_debug/processed/home_layout.json"
    )
    assert full_file_dump_path(project, "abc123") == Path(
        "/proj/.figma_debug/raw/full_file_abc123.json"
    )


def test_resolve_screen_raw_dump_prefers_canonical(tmp_path: Path) -> None:
    canonical = raw_dump_path(tmp_path, "sign_in")
    legacy = legacy_raw_dump_path(tmp_path, "1:3570")
    canonical.parent.mkdir(parents=True)
    canonical.write_text("{}", encoding="utf-8")
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(tmp_path, "sign_in", "1:3570")
    assert resolved == canonical


def test_resolve_screen_raw_dump_falls_back_to_legacy(tmp_path: Path) -> None:
    legacy = legacy_raw_dump_path(tmp_path, "1:3570")
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}", encoding="utf-8")

    resolved = resolve_screen_raw_dump(tmp_path, "sign_in", "1:3570")
    assert resolved == legacy
