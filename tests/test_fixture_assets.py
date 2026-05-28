"""Fixture vector asset stubs for golden capture."""

from __future__ import annotations

from figma_flutter_agent.fixtures.assets import iter_vector_asset_keys, sync_fixture_vector_assets
from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree


def test_iter_vector_asset_keys_from_sign_up_fixture() -> None:
    tree = load_layout_tree("sign_up_and_sign_in")
    keys = iter_vector_asset_keys(tree)
    assert "assets/icons/google.svg" in keys


def test_sync_fixture_vector_assets_writes_placeholder(tmp_path) -> None:
    tree = load_layout_tree("music_v2")
    written = sync_fixture_vector_assets(tmp_path, tree)
    assert "assets/icons/provider_logo.svg" in written
    assert (tmp_path / "assets/icons/provider_logo.svg").is_file()
