"""Scan-once stale markers (Program 10 P2, advisory)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def content_hash_for_path(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def stale_marker(
    *,
    artifact: str,
    previous_hash: str | None,
    current_hash: str,
) -> dict[str, Any] | None:
    if not previous_hash or previous_hash == current_hash:
        return None
    return {
        "artifact": artifact,
        "previousHash": previous_hash,
        "currentHash": current_hash,
        "stale": True,
    }


def write_stale_markers(path: Path, markers: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"markers": markers}, indent=2) + "\n", encoding="utf-8")
