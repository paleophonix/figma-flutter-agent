"""Font disk cache tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from figma_flutter_agent.fonts import cache
from figma_flutter_agent.fonts.paths import MIN_FONT_BUNDLE_BYTES
from tests.font_bytes import minimal_ttf_payload


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_FLUTTER_FONT_CACHE_DIR", str(tmp_path))
    cache.clear_font_cache()


def test_write_and_read_cached_font() -> None:
    url = "https://example.com/inter-400.ttf"
    payload = minimal_ttf_payload()
    cache.write_cached_font(url, payload)
    assert cache.read_cached_font(url) == payload


def test_read_cached_font_discards_invalid_payload(tmp_path: Path) -> None:
    url = "https://example.com/inter-700.ttf"
    path = cache.cache_path_for_url(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x01\x00\x00" + (b"\x00" * (MIN_FONT_BUNDLE_BYTES - 4)))
    assert cache.read_cached_font(url) is None
    assert not path.is_file()


def test_write_cached_font_rejects_invalid_payload() -> None:
    url = "https://example.com/bad.ttf"
    assert cache.write_cached_font(url, b"not-a-font") is None
    assert cache.read_cached_font(url) is None


def test_cache_path_is_sha256_of_url() -> None:
    url = "https://example.com/font.ttf"
    path = cache.cache_path_for_url(url)
    assert path.name.endswith(".bin")
    assert path.parent == cache.font_cache_dir()
