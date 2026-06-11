"""Tests for raw vs processed dump hygiene (E0.6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.pipeline.dump import load_fetch_result_from_dump


def test_load_fetch_result_from_dump_rejects_processed(tmp_path: Path) -> None:
    dump_path = tmp_path / "processed_layout.json"
    dump_path.write_text(
        json.dumps(
            {
                "parserVersion": "2026.06.1",
                "cleanTree": {"id": "1:1", "name": "Frame", "type": "STACK", "children": []},
                "tokens": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(FlutterProjectError, match="processed design-tree snapshot"):
        load_fetch_result_from_dump(dump_path, file_key="abc", node_id="1:1")


def test_load_fetch_result_from_dump_accepts_raw_frame(tmp_path: Path) -> None:
    dump_path = tmp_path / "raw_layout.json"
    dump_path.write_text(
        json.dumps(
            {
                "id": "362:319",
                "name": "Frame",
                "type": "FRAME",
                "visible": True,
                "children": [],
            }
        ),
        encoding="utf-8",
    )
    result = load_fetch_result_from_dump(dump_path, file_key="abc", node_id="362:319")
    assert result.node_id == "362:319"
    assert result.root["type"] == "FRAME"
