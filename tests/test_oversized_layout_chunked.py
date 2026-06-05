"""Chunked layout codegen for oversized Dart sources (WP-4)."""

from __future__ import annotations

from figma_flutter_agent.generator.planned_dart import split_oversized_layout_dart
from figma_flutter_agent.tools.ast_sidecar import AST_SIDECAR_MAX_SOURCE_BYTES


def _synthetic_layout() -> str:
    pad = "x" * 500
    widgets = "\n".join(
        f"Widget _w{i}() => Container(key: const ValueKey('figma-node_{i}'), child: Text('{pad}'));"
        for i in range(200)
    )
    return f"import 'package:flutter/material.dart';\nclass DemoLayout {{\n{widgets}\n}}\n"


def test_oversized_layout_chunked_codegen() -> None:
    source = _synthetic_layout()
    assert len(source.encode("utf-8")) > AST_SIDECAR_MAX_SOURCE_BYTES
    chunks = split_oversized_layout_dart("lib/generated/demo_layout.dart", source)
    assert len(chunks) > 1
    assert any(path.endswith("_shell.dart") for path in chunks)
    assert any("_body_" in path for path in chunks)
    for chunk in chunks.values():
        assert len(chunk.encode("utf-8")) <= AST_SIDECAR_MAX_SOURCE_BYTES or "_body_" in chunk
