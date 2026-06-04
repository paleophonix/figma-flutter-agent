"""Tests for plugin JSON token import."""

from __future__ import annotations

import json
from pathlib import Path

from figma_flutter_agent.parser.tokens import import_design_tokens_json


def test_import_w3c_color_tokens(tmp_path: Path) -> None:
    payload = {
        "global": {
            "primary": {"$type": "color", "$value": "#112233"},
        },
    }
    path = tmp_path / "tokens.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    tokens = import_design_tokens_json(path)
    assert tokens.colors
    assert any("112233" in value for value in tokens.colors.values())
