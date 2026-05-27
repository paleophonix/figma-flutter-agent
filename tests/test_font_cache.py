"""Font disk cache tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fonts import cache


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_FLUTTER_FONT_CACHE_DIR", str(tmp_path))
    cache.clear_font_cache()


def test_write_and_read_cached_font() -> None:
    url = "https://example.com/inter-400.ttf"
    payload = b"font-bytes"
    cache.write_cached_font(url, payload)
    assert cache.read_cached_font(url) == payload


def test_cache_path_is_sha256_of_url() -> None:
    url = "https://example.com/font.ttf"
    path = cache.cache_path_for_url(url)
    assert path.name.endswith(".bin")
    assert path.parent == cache.font_cache_dir()
