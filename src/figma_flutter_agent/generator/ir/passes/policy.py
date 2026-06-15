"""Layout pass policy resolution from agent configuration."""

from __future__ import annotations

from figma_flutter_agent.config.models import AgentYamlConfig

_PLACEMENT_MUTATING_PASS_NAMES = frozenset({"sectionize", "unstack", "unpin"})


def preserve_placement_layout_passes(agent: AgentYamlConfig) -> bool:
    """Return True when layout passes must not mutate stack placement or structure."""
    generation = agent.generation
    return bool(generation.preserve_placement or generation.pixel_fidelity)


def resolve_layout_pass_policy(
    agent: AgentYamlConfig,
) -> tuple[int, bool, bool, bool]:
    """Return scroll threshold, scroll-host injection, responsive reflow, placement freeze.

    Args:
        agent: Loaded agent YAML configuration.

    Returns:
        Tuple of
        ``(fallback_threshold_px, inject_root_scroll_host, responsive_reflow_enabled,
        preserve_placement_passes)``.
    """
    passes = agent.layout_passes
    threshold = passes.scroll_extent_fallback_threshold_px
    if threshold is None:
        threshold = agent.responsive.macro_height_threshold_px
    freeze_placement = preserve_placement_layout_passes(agent)
    return (
        threshold,
        passes.inject_root_scroll_host,
        agent.responsive.enabled,
        freeze_placement,
    )


def filter_layout_passes_for_placement(
    passes: tuple[Pass, ...],
    *,
    preserve_placement: bool,
) -> tuple[Pass, ...]:
    """Drop placement-mutating passes when pixel fidelity requires frozen geometry."""
    if not preserve_placement:
        return passes
    return tuple(
        registered
        for registered in passes
        if getattr(registered, "name", "") not in _PLACEMENT_MUTATING_PASS_NAMES
    )
