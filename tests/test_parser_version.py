"""CORE-21 processed dump parser version stamping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.parser.version import (
    PARSER_VERSION,
    check_stale_processed_dump,
)


def test_check_stale_processed_dump_strict_raises(tmp_path: Path) -> None:
    feature = "demo_screen"
    dump_dir = tmp_path / ".debug" / "processed"
    dump_dir.mkdir(parents=True)
    path = dump_dir / f"{feature}_layout.json"
    path.write_text(
        json.dumps({"parserVersion": "0.0.0", "cleanTree": {}, "tokens": {}}),
        encoding="utf-8",
    )
    with pytest.raises(GenerationError, match="Stale processed dump"):
        check_stale_processed_dump(tmp_path, feature, strict=True)


def test_check_stale_processed_dump_ok_when_current(tmp_path: Path) -> None:
    feature = "demo_screen"
    dump_dir = tmp_path / ".debug" / "processed"
    dump_dir.mkdir(parents=True)
    path = dump_dir / f"{feature}_layout.json"
    path.write_text(
        json.dumps({"parserVersion": PARSER_VERSION, "cleanTree": {}, "tokens": {}}),
        encoding="utf-8",
    )
    check_stale_processed_dump(tmp_path, feature, strict=True)
