"""Emit eligibility checks shared by extraction bijection and layout emit."""

from __future__ import annotations

from figma_flutter_agent.schemas import CleanDesignTreeNode


def external_cluster_delegate_eligible(node: CleanDesignTreeNode) -> bool:
    """Return True when a node may emit as an external cluster delegate call-site."""
    from figma_flutter_agent.parser.interaction import (
        layout_fact_hosts_compact_checkbox_control,
        layout_fact_hosts_payment_selection_indicator,
        must_inline_extracted_widget_host,
    )

    if must_inline_extracted_widget_host(node):
        return False
    if layout_fact_hosts_compact_checkbox_control(node):
        return False
    if layout_fact_hosts_payment_selection_indicator(node):
        return False
    ref = (node.extracted_widget_ref or "").strip()
    if ref:
        return True
    return bool(node.cluster_id or node.shape_cluster_id)
