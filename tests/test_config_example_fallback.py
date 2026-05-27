"""Agent config is loaded from the agent repo, not the Flutter project."""

from pathlib import Path

import pytest

from figma_flutter_agent.config import (
    Settings,
    agent_repo_root,
    resolve_agent_config_path,
)


def test_resolve_agent_config_path_uses_agent_repo() -> None:
    path = resolve_agent_config_path()
    assert path.is_file()
    assert path.parent == agent_repo_root()


def test_load_yaml_config_ignores_flutter_project_yaml_when_chdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".ai-figma-flutter.yml").write_text(
        "generation:\n  cluster_min_count: 99\n",
        encoding="utf-8",
    )

    settings = Settings()
    settings.load_yaml_config()

    assert settings.agent.generation.cluster_min_count != 99


def test_load_yaml_config_explicit_path_still_works(tmp_path: Path) -> None:
    config_path = tmp_path / ".ai-figma-flutter.yml"
    config_path.write_text(
        "generation:\n  cluster_min_count: 77\n",
        encoding="utf-8",
    )

    settings = Settings()
    settings.load_yaml_config(config_path)

    assert settings.agent.generation.cluster_min_count == 77
