"""Render visual layout files with full emit kwargs."""

from __future__ import annotations

from typing import Any

from figma_flutter_agent.config.fidelity_policy import (
    RenderProfile,
    pixel_fidelity_policy_for_agent,
    resolve_render_profile,
)
from figma_flutter_agent.config.settings import Settings
from figma_flutter_agent.generator.layout.file import render_layout_file
from figma_flutter_agent.parser.truth_snapshot import attach_emit_tree, capture_truth_snapshot
from figma_flutter_agent.schemas import CleanDesignTreeNode


def should_use_visual_renderer(settings: Settings) -> bool:
    """Return True when render profile selects the visual-pixel path."""
    return resolve_render_profile(settings.agent) == RenderProfile.VISUAL_PIXEL


def render_visual_layout_files(
    root: CleanDesignTreeNode,
    *,
    settings: Settings,
    truth_snapshot: CleanDesignTreeNode | None = None,
    **layout_kwargs: Any,
) -> dict[str, str]:
    """Emit layout files via absolute-stack visual path with pixel policy."""
    policy = pixel_fidelity_policy_for_agent(settings.agent)
    truth = truth_snapshot or capture_truth_snapshot(root)
    files = render_layout_file(
        root,
        responsive_enabled=False,
        de_archetype_pass=True,
        skip_layout_reconcile=policy.preserve_raw_geometry,
        archetype_reconcile=False,
        **layout_kwargs,
    )
    _ = attach_emit_tree(truth, root)
    return files
