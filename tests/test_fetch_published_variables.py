"""Tests for published variables merge and connector helpers."""

from __future__ import annotations

from figma_flutter_agent.parser.tokens.build import build_design_tokens
from figma_flutter_agent.parser.tokens.variables import (
    merge_variable_payloads,
    resolve_image_fill_ref,
)


def test_merge_variable_payloads_combines_meta() -> None:
    local = {"meta": {"variables": {"a": {"name": "localColor"}}}}
    published = {"meta": {"variables": {"b": {"name": "pubColor"}}}}
    merged = merge_variable_payloads(local, published)
    assert merged is not None
    variables = merged["meta"]["variables"]
    assert "a" in variables
    assert "b" in variables


def test_resolve_image_fill_ref() -> None:
    urls = {"abc123": "https://example.com/fill.png"}
    assert resolve_image_fill_ref("abc123", urls) == urls["abc123"]
    assert resolve_image_fill_ref("missing", urls) is None


def test_build_design_tokens_includes_edge_insets_from_tree() -> None:
    root = {
        "type": "FRAME",
        "paddingTop": 8,
        "paddingBottom": 8,
        "paddingLeft": 16,
        "paddingRight": 16,
        "children": [],
        "fills": [],
    }
    tokens = build_design_tokens(root, None)
    assert tokens.edge_insets
