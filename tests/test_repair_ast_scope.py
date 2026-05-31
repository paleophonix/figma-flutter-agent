"""AST reconcile path expansion for repair replan."""

from __future__ import annotations

from figma_flutter_agent.llm.repair_scope import expand_ast_reconcile_paths


def test_expand_ast_reconcile_paths_adds_layout() -> None:
    planned = {
        "lib/features/sign_up/sign_up_screen.dart": "screen",
        "lib/generated/sign_up_layout.dart": "layout",
    }
    expanded = expand_ast_reconcile_paths(
        frozenset({"lib/features/sign_up/sign_up_screen.dart"}),
        planned,
        resolved_feature="sign_up",
    )
    assert "lib/generated/sign_up_layout.dart" in expanded
    assert "lib/features/sign_up/sign_up_screen.dart" in expanded
