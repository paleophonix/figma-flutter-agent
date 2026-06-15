"""Config domain policy views."""

from __future__ import annotations

from figma_flutter_agent.config.generation_domains import fidelity_generation_policy
from figma_flutter_agent.config.models import GenerationConfig


def test_fidelity_generation_policy_view() -> None:
    cfg = GenerationConfig(pixel_fidelity=True, preserve_placement=True)
    policy = fidelity_generation_policy(cfg)
    assert policy.pixel_fidelity is True
    assert policy.preserve_placement is True
