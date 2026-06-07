"""Codegen postprocess must not corrupt delimiter-valid compiler-emitted widgets."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from figma_flutter_agent.generator.dart.postprocess import process_generated_dart_source
from figma_flutter_agent.generator.dart.llm_codegen import validate_dart_delimiters

_CLUSTER0_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "tests"
    / "fixtures"
    / "dart"
    / "compiler_emitted_cluster0_widget.dart"
)


def test_process_generated_dart_skips_codegen_ast_for_figma_key_widgets() -> None:
    source = """import 'package:flutter/material.dart';

class DemoWidget extends StatelessWidget {
  const DemoWidget({super.key});

  @override
  Widget build(BuildContext context) {
    final textScaler = MediaQuery.textScalerOf(context);
    return Semantics(
      label: 'x',
      child: Text(
        'x',
        key: ValueKey('figma-1_2'),
        textScaler: textScaler,
      ),
    );
  }
}
"""
    with patch(
        "figma_flutter_agent.generator.dart.postprocess.apply_codegen_ast_rules"
    ) as codegen_mock:
        processed = process_generated_dart_source(source)
    codegen_mock.assert_not_called()
    assert validate_dart_delimiters(processed) is None
    assert "ValueKey('figma-1_2')" in processed


def test_process_generated_dart_preserves_large_ir_extracted_widget() -> None:
    source = _CLUSTER0_FIXTURE.read_text(encoding="utf-8")
    assert validate_dart_delimiters(source) is None
    before_len = len(source)
    processed = process_generated_dart_source(source)
    assert validate_dart_delimiters(processed) is None
    assert len(processed) >= before_len - 200
