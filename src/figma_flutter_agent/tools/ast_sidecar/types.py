"""Shared AST sidecar types and limits."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from figma_flutter_agent.errors import FigmaFlutterError

AstRule = Literal[
    "codegen_pass",
    "strip_bare_unicode_escapes",
    "normalize_string_literals",
    "sanitize_imports",
    "unscale_design_expressions",
    "unwrap_scale_layout_builder",
    "strip_viewport_scale_transform",
    "fix_llm_api_mistakes",
    "fix_alignment_literals",
    "strip_design_canvas_gesture_matryoshka",
    "wrap_flex_row_column_children",
    "llm_syntax_repairs",
    "planned_delimiter_balance",
]

AST_SIDECAR_MAX_SOURCE_BYTES = 65_536

SIDECAR_COMMANDS_ALLOWING_OVERSIZED_SOURCE: frozenset[str] = frozenset(
    {"extract_widget", "replace_widget"}
)

AST_REQUIRED_MSG = (
    "Dart AST sidecar is required. Set FIGMA_FLUTTER_SDK (or PATH to dart), "
    "run tools/build_sidecars.ps1, or set FIGMA_AST_COMPILER_PATH to a built ast_compiler binary."
)


class AstSidecarError(FigmaFlutterError):
    """Raised when the AST sidecar cannot apply rules."""


@dataclass(frozen=True)
class AstSidecarResult:
    """Outcome of an AST sidecar invocation."""

    source: str
    backend: Literal["subprocess", "skipped"]
    edits: list[dict[str, Any]]


def ast_source_exceeds_sidecar_limit(source: str) -> bool:
    """Return True when ``source`` is too large for a reliable full-file sidecar pass."""
    return len(source.encode("utf-8")) > AST_SIDECAR_MAX_SOURCE_BYTES
