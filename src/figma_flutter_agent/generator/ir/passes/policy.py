"""Layout pass policy resolution from agent configuration."""

from __future__ import annotations

from figma_flutter_agent.config.models import AgentYamlConfig


def resolve_layout_pass_policy(
    agent: AgentYamlConfig,
) -> tuple[int, bool, bool]:
    """Return scroll threshold, scroll-host injection, and responsive reflow flags.

    Args:
        agent: Loaded agent YAML configuration.

    Returns:
        Tuple of ``(fallback_threshold_px, inject_root_scroll_host, responsive_reflow_enabled)``.
    """
    passes = agent.layout_passes
    threshold = passes.scroll_extent_fallback_threshold_px
    if threshold is None:
        threshold = agent.responsive.macro_height_threshold_px
    return threshold, passes.inject_root_scroll_host, agent.responsive.enabled
