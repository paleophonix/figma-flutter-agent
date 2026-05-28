"""AC-4: planned reconcile uses AST sidecar, not legacy postprocess entry."""

from __future__ import annotations

import figma_flutter_agent.generator.planned_dart as planned_dart_module
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files


def test_reconcile_module_does_not_import_postprocess_generated_dart() -> None:
    assert "postprocess_generated_dart" not in planned_dart_module.__dict__


def test_reconcile_uses_ast_and_codegen_fixes(monkeypatch) -> None:
    ast_calls: list[bool] = []
    codegen_calls: list[bool] = []

    def _ast(source: str, **kwargs: object) -> object:
        ast_calls.append(True)
        from figma_flutter_agent.tools.ast_sidecar import AstSidecarResult

        return AstSidecarResult(source=source, backend="in_process", edits=[])

    def _codegen(source: str, **kwargs: object) -> str:
        codegen_calls.append(True)
        return source

    monkeypatch.setattr(planned_dart_module, "apply_ast_rules", _ast)
    monkeypatch.setattr(planned_dart_module, "apply_codegen_dart_fixes", _codegen)

    planned = {
        "lib/features/demo/demo_screen.dart": "class DemoScreen extends StatelessWidget {}",
    }
    reconcile_planned_dart_files(planned, use_ast_sidecar=True)
    assert ast_calls
    assert codegen_calls
