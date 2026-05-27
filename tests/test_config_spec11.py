"""Config schema tests aligned with spec §11."""

from pathlib import Path

from figma_flutter_agent.config import AgentYamlConfig, Settings


def test_legacy_theme_string_is_coerced() -> None:
    config = AgentYamlConfig.model_validate({"theme": "material_3"})

    assert config.theme.variant == "material_3"
    assert config.theme.generate is True


def test_nested_theme_and_flutter_architecture() -> None:
    config = AgentYamlConfig.model_validate(
        {
            "theme": {"variant": "cupertino", "generate": False},
            "flutter": {"architecture": "layer_first"},
            "state_management": {"type": "riverpod"},
            "assets": {"optimize": False},
        }
    )

    assert config.theme.generate is False
    assert config.theme.variant == "cupertino"
    assert config.flutter.architecture == "layer_first"
    assert config.state_management.type == "riverpod"
    assert config.assets.optimize is False


def test_settings_loads_spec11_yaml(tmp_path: Path) -> None:
    config_path = tmp_path / ".ai-figma-flutter.yml"
    config_path.write_text(
        """
theme:
  variant: material_3
  generate: true
flutter:
  architecture: feature_first
state_management:
  type: bloc
assets:
  optimize: true
""".strip(),
        encoding="utf-8",
    )
    settings = Settings(config_path=config_path)
    settings.load_yaml_config(config_path)

    assert settings.agent.state_management.type == "bloc"
    assert settings.agent.assets.optimize is True
