"""Tests for production profile."""

from figma_flutter_agent.config import Settings, apply_production_profile


def test_apply_production_profile_enables_strict_gates() -> None:
    settings = apply_production_profile(Settings())
    quality = settings.agent.quality
    validation = settings.agent.validation

    assert quality.enforce_spec9_gates is True
    assert quality.strict_accessibility_labels is True
    assert quality.strict_contrast is True
    assert settings.agent.accessibility.auto_fix is False
    assert quality.fail_duplicate_clusters is True
    assert validation.require_dart_sdk is True
    assert validation.spec23_dart_analyze is True
    assert validation.analyze_scope == "all_planned"
    assert validation.strict_preservation is True
    assert settings.agent.generation.regen_llm_on_token_change is True
    assert settings.llm_require_strict_json_schema is True
    assert settings.agent.responsive.enabled is True
    assert settings.agent.layout.avoid_fixed_sizes is True
    assert settings.agent.sync.enabled is True

