"""Synthetic replay failure artifact protocol (Program 08 P0-2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPLAY_SCHEMA_VERSION = "1"
_TEMP_ROOT = Path(__file__).resolve().parents[2] / ".temp" / "synthetic-replay"


def write_failure_artifact(
    *,
    test_name: str,
    payload: dict[str, Any],
) -> Path:
    _TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = _TEMP_ROOT / f"{test_name}.json"
    body = {"schemaVersion": REPLAY_SCHEMA_VERSION, **payload}
    path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_failure_artifact(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schemaVersion") == REPLAY_SCHEMA_VERSION
    return data
