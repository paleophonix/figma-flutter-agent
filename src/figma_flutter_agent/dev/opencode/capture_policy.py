"""Repair pipeline capture proof policy."""

from __future__ import annotations

from figma_flutter_agent.config.settings import Settings


def repair_proof_capture_enabled(settings: Settings) -> bool:
    """Return whether the repair pipeline may run Flutter capture verify.

    ``RepairProofCaptureLaw``: when ``debug_pipeline.check_flutter_capture_verify``
    is enabled, post-repair capture proof is mandatory even if ``agent.dev.debug_capture``
    is false (that flag only gates generate-time capture, not repair closure).

    Args:
        settings: Loaded agent settings.

    Returns:
        True when repair may invoke ``run_capture_verify``.
    """
    if settings.agent.dev.debug_capture:
        return True
    return bool(settings.agent.debug_pipeline.check_flutter_capture_verify)
