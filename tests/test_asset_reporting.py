"""Tests for asset export failure reporting."""

from __future__ import annotations

from figma_flutter_agent.assets.reporting import summarize_failed_asset_exports


def test_summarize_failed_asset_exports_lists_node_ids() -> None:
    message = summarize_failed_asset_exports(frozenset({"42:1", "42:2"}))
    assert message is not None
    assert "42:1" in message
    assert "42:2" in message
    assert "2 node(s)" in message


def test_summarize_failed_asset_exports_rate_limited_prefix() -> None:
    message = summarize_failed_asset_exports(frozenset({"1:1"}), rate_limited=True)
    assert message is not None
    assert "rate limits" in message


def test_summarize_failed_asset_exports_empty() -> None:
    assert summarize_failed_asset_exports(frozenset()) is None
