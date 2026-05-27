"""Tests for production profile and deterministic screen scaffold."""

from figma_flutter_agent.config import Settings, apply_production_profile
from figma_flutter_agent.generator.layout_renderer import render_deterministic_screen_files


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
    assert settings.agent.generation.llm_fallback_to_deterministic is False
    assert settings.agent.generation.regen_llm_on_token_change is True
    assert settings.llm_require_strict_json_schema is True
    assert settings.agent.responsive.enabled is True
    assert settings.agent.layout.avoid_fixed_sizes is True
    assert settings.agent.sync.enabled is True


def test_deterministic_screen_includes_scaffold_and_app_bar() -> None:
    planned = render_deterministic_screen_files(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        uses_svg=False,
        use_auto_route=False,
        responsive_enabled=True,
        max_web_width=1200,
        use_scaffold=True,
    )
    screen_path = next(path for path in planned if path.endswith("_screen.dart"))
    content = planned[screen_path]

    assert "Scaffold(" in content
    assert "AppBar(" in content
    assert "GeneratedScreenShell" in content
