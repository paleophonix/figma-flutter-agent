"""Custom-code policies during publish."""

from __future__ import annotations

from pathlib import Path

from control_panel.config.models import CustomCodePolicy
from figma_flutter_agent.errors import FigmaFlutterError
from figma_flutter_agent.generator.writing.custom_code import (
    find_orphan_line_numbers,
    merge_custom_code,
)


def apply_custom_code_policy(
    *,
    policy: CustomCodePolicy,
    relative_path: str,
    generated_content: str,
    existing_path: Path | None,
) -> str:
    """Apply the configured custom-code policy before commit."""
    if existing_path is None or not existing_path.is_file():
        return generated_content
    existing_content = existing_path.read_text(encoding="utf-8")
    if policy == CustomCodePolicy.REPLACE_SCREEN:
        return generated_content
    if policy == CustomCodePolicy.BLOCK_ON_DIRTY:
        orphans = find_orphan_line_numbers(existing_content)
        if orphans:
            raise FigmaFlutterError(
                f"Manual edits outside preservation zones in {relative_path}; publish blocked."
            )
    return merge_custom_code(generated_content, existing_content)
