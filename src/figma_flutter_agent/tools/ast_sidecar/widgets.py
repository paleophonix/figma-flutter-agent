"""Widget-level AST sidecar operations."""

from __future__ import annotations

from typing import Any, Literal

from figma_flutter_agent.tools.ast_sidecar.commands import compiler_invocation, require_ast_compiler
from figma_flutter_agent.tools.ast_sidecar.transport import invoke_sidecar_json


def sidecar_widget_command(
    command: Literal["extract_widget", "replace_widget"],
    source: str,
    figma_id: str,
    *,
    replacement: str | None = None,
) -> dict[str, Any] | None:
    invocation = compiler_invocation()
    if invocation is None:
        return None
    payload: dict[str, Any] = {
        "version": 1,
        "command": command,
        "source": source,
        "figmaId": figma_id,
    }
    if replacement is not None:
        payload["replacement"] = replacement
    return invoke_sidecar_json(invocation, payload, require_ok=False)


def extract_widget_by_figma_id(source: str, figma_id: str) -> str | None:
    response = sidecar_widget_command("extract_widget", source, figma_id)
    if response is None or not response.get("ok"):
        return None
    snippet = response.get("snippet")
    return str(snippet) if snippet is not None else None


def replace_widget_by_figma_id(source: str, figma_id: str, replacement: str) -> str | None:
    response = sidecar_widget_command("replace_widget", source, figma_id, replacement=replacement)
    if response is None or not response.get("ok"):
        return None
    updated = response.get("source")
    return str(updated) if updated is not None else None


def list_bindings_in_dart_source(source: str) -> list[dict[str, Any]]:
    """Return Figma binding records from Dart source via the AST sidecar."""
    payload = {
        "version": 1,
        "command": "list_bindings",
        "source": source,
    }
    response = invoke_sidecar_json(require_ast_compiler(), payload, require_ok=False)
    if response is None or not response.get("ok"):
        return []
    bindings = response.get("bindings")
    if not isinstance(bindings, list):
        return []
    return [entry for entry in bindings if isinstance(entry, dict)]
