"""High-level design-token assembly."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.parser.tokens.tree import extract_from_tree, merge_token_maps
from figma_flutter_agent.parser.tokens.variables import (
    extract_from_variables,
    merge_variable_payloads,
)
from figma_flutter_agent.schemas import DesignTokens


def build_design_tokens(
    root: dict[str, Any],
    variables_payload: dict[str, Any] | None,
    *,
    published_variables_payload: dict[str, Any] | None = None,
) -> DesignTokens:
    """Build design tokens using variables first, then tree fallback."""
    merged_variables = merge_variable_payloads(variables_payload, published_variables_payload)
    from_variables = extract_from_variables(merged_variables)
    tree_tokens = extract_from_tree(root)
    if from_variables and from_variables.colors:
        return merge_token_maps(from_variables, tree_tokens)
    return tree_tokens
