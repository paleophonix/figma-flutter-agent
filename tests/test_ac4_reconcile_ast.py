"""AC-4: planned reconcile uses AST sidecar, not legacy postprocess entry."""

from __future__ import annotations

import figma_flutter_agent.generator.planned_dart as planned_dart_module
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files


def test_reconcile_module_does_not_import_postprocess_generated_dart() -> None:
    assert "postprocess_generated_dart" not in planned_dart_module.__dict__


def test_reconcile_uses_ast_and_codegen_fixes(monkeypatch) -> None:
    process_calls: list[bool] = []

    def _process(source: str, **kwargs: object) -> str:
        process_calls.append(True)
        return source

    monkeypatch.setattr(planned_dart_module, "process_generated_dart_source", _process)

    planned = {
        "lib/features/demo/demo_screen.dart": "class DemoScreen extends StatelessWidget {}",
    }
    reconcile_planned_dart_files(planned, use_ast_sidecar=True)
    assert process_calls
