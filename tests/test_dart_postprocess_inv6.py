"""INV-6: layout coordinate repairs must not use regex in dart_postprocess."""

from __future__ import annotations

from pathlib import Path


def test_dart_postprocess_has_no_positioned_layout_regex() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("src/figma_flutter_agent/generator/dart/postprocess").glob("*.py")
    )
    assert "Positioned" not in source
    assert "Stack(" not in source
