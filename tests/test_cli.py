"""CLI smoke tests using Typer's CliRunner."""

from __future__ import annotations

import importlib

import pytest
from typer.testing import CliRunner

from figma_flutter_agent.cli import app

_generate_mod = importlib.import_module("figma_flutter_agent.cli.generate")

runner = CliRunner()


def test_demo_signoff_command_passes_offline() -> None:
    result = runner.invoke(app, ["demo-signoff", "--strict"])
    assert result.exit_code == 0, result.stdout
    assert "Demo sign-off OK" in result.stdout
    assert "figma_node_sample.json" in result.stdout


def test_validate_spec23_command_passes_default_fixture() -> None:
    result = runner.invoke(
        app,
        ["validate-spec23", "--fixture", "tests/fixtures/figma_node_sample.json", "--strict"],
    )
    assert result.exit_code == 0, result.stdout
    assert "Spec §23 OK" in result.stdout
    assert "figma_connectivity" in result.stdout


def test_generate_allow_dev_profile_shows_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    from figma_flutter_agent.config import Settings
    from figma_flutter_agent.pipeline.result import PipelineResult
    from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens, NodeType

    stub_result = PipelineResult(
        clean_tree=CleanDesignTreeNode(id="1:1", name="Screen", type=NodeType.COLUMN),
        tokens=DesignTokens(),
        written_files=["lib/theme/app_colors.dart"],
        warnings=[],
    )

    def _fake_asyncio_run(coro: object) -> PipelineResult:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return stub_result

    monkeypatch.setattr(_generate_mod.asyncio, "run", _fake_asyncio_run)
    monkeypatch.setattr(_generate_mod, "load_settings", lambda config=None: Settings())
    monkeypatch.setattr(
        "figma_flutter_agent.dev.project.resolve_project_dir", lambda project_dir: project_dir
    )
    monkeypatch.setenv("FIGMA_SMOKE_FILE_KEY", "some_file_key")

    result = runner.invoke(
        app,
        [
            "generate",
            "--figma-url",
            "https://www.figma.com/design/x/n?node-id=1-2",
            "--allow-dev-profile",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "Dev profile" in result.stdout


def test_live_check_without_token_exits_error() -> None:
    result = runner.invoke(
        app,
        ["live-check"],
        env={"FIGMA_ACCESS_TOKEN": "", "FIGMA_SMOKE_FILE_KEY": "", "FIGMA_SMOKE_NODE_ID": ""},
    )
    assert result.exit_code == 1
    assert "FIGMA_ACCESS_TOKEN" in result.stdout


def test_live_check_without_smoke_shows_env_hint() -> None:
    result = runner.invoke(
        app,
        ["live-check"],
        env={
            "FIGMA_ACCESS_TOKEN": "figd_test",
            "FIGMA_SMOKE_FILE_KEY": "",
            "FIGMA_SMOKE_NODE_ID": "",
        },
    )
    assert result.exit_code == 0
    assert "FIGMA_SMOKE_FILE_KEY" in result.stdout
    assert "--figma-url" in result.stdout


def test_generate_maps_oserror_to_unexpected_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    from figma_flutter_agent.config import Settings

    def _raise_oserror(coro: object) -> None:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        raise OSError("disk full")

    monkeypatch.setattr(_generate_mod.asyncio, "run", _raise_oserror)
    monkeypatch.setattr(_generate_mod, "load_settings", lambda config=None: Settings())
    monkeypatch.setattr(
        "figma_flutter_agent.dev.project.resolve_project_dir", lambda project_dir: project_dir
    )
    monkeypatch.setenv("FIGMA_SMOKE_FILE_KEY", "some_file_key")

    result = runner.invoke(
        app,
        [
            "generate",
            "--figma-url",
            "https://www.figma.com/design/x/n?node-id=1-2",
            "--allow-dev-profile",
        ],
    )
    assert result.exit_code == 2
    assert "Unexpected failure" in result.stdout


def test_live_check_figma_url_runs_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    from figma_flutter_agent.stages.fetch import FigmaFetchResult

    class _FakeConnector:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def _fake_fetch(
        connector: object,
        *,
        file_key: str,
        node_id: str,
        project_dir: object,
        verbose: bool = False,
    ) -> FigmaFetchResult:
        assert file_key == "UrlKey"
        assert node_id == "1:2"
        return FigmaFetchResult(
            file_key=file_key,
            node_id=node_id,
            root={"id": node_id, "name": "Smoke Frame"},
            variables_payload=None,
            published_styles={},
            components={},
            prototype_links=[],
        )

    monkeypatch.setattr("figma_flutter_agent.stages.fetch.fetch_figma_frame", _fake_fetch)
    monkeypatch.setattr(
        "figma_flutter_agent.figma.client.FigmaConnector",
        lambda _token, _base: _FakeConnector(),
    )

    result = runner.invoke(
        app,
        [
            "live-check",
            "--figma-url",
            "https://www.figma.com/design/UrlKey/n?node-id=1-2",
        ],
        env={
            "FIGMA_ACCESS_TOKEN": "figd_test",
            "FIGMA_SMOKE_FILE_KEY": "ignored",
            "FIGMA_SMOKE_NODE_ID": "9:9",
        },
    )
    assert result.exit_code == 0, result.stdout
    assert "Live fetch OK" in result.stdout
    assert "FIGMA_SMOKE_FILE_KEY=UrlKey" in result.stdout
