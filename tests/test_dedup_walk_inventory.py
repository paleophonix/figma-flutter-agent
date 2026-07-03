"""Tests for dedup walk inventory (04-P0-1)."""

from __future__ import annotations

from figma_flutter_agent.parser.dedup.walk_inventory import (
    INVENTORY_JSON_REL,
    list_walk_sites,
    write_walk_inventory,
)


def test_walk_inventory_is_deterministic() -> None:
    first = list_walk_sites()
    second = list_walk_sites()
    assert first == second
    assert any(site.status == "migrated" for site in first)


def test_write_walk_inventory_json() -> None:
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    path = repo_root / INVENTORY_JSON_REL
    write_walk_inventory(path=path)
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "dedup_prune_extracted" in text
