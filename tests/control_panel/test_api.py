"""Public API and auth tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from control_panel.api.deps import get_settings, hash_api_key, require_principal
from control_panel.config.models import ApiClientConfig, DiscordBotSettings, DiscordBotYamlConfig
from control_panel.db import JobOrigin


def _settings(*, enabled: bool = True, key_hash: str = "") -> DiscordBotSettings:
    yaml = DiscordBotYamlConfig()
    clients = ()
    if key_hash:
        clients = (ApiClientConfig(principal="ci-bot", key_hash=key_hash, project_key="default"),)
    return DiscordBotSettings(
        yaml=yaml,
        discord_bot_token=SecretStr(""),
        gitlab_private_token=SecretStr("y"),
        github_token=SecretStr("z"),
        telegram_bot_token=SecretStr(""),
        database_url="postgresql+asyncpg://u:p@localhost/db",
        database_mode=yaml.database.mode,
        redis_url="redis://127.0.0.1:6379/0",
        config_path=Path("cfg.yml"),
        api_enabled=enabled,
        api_clients=clients,
    )


def _auth_client(settings: DiscordBotSettings) -> TestClient:
    app = FastAPI()

    @app.get("/auth-check")
    def auth_check(principal: str = Depends(require_principal)) -> dict[str, str]:
        return {"principal": principal}

    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.mark.control_plane
def test_hash_api_key_stable() -> None:
    assert hash_api_key("secret") == hashlib.sha256(b"secret").hexdigest()


@pytest.mark.control_plane
def test_require_principal_rejects_missing_key() -> None:
    client = _auth_client(_settings(key_hash=hash_api_key("secret")))
    response = client.get("/auth-check")
    assert response.status_code == 401


@pytest.mark.control_plane
def test_require_principal_accepts_valid_key() -> None:
    digest = hash_api_key("secret")
    client = _auth_client(_settings(key_hash=digest))
    response = client.get("/auth-check", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json()["principal"] == "ci-bot"


@pytest.mark.control_plane
@pytest.mark.asyncio
async def test_create_api_job(job_store, tmp_path) -> None:
    job = await job_store.create_job(
        job_id="api_job",
        figma_url="https://www.figma.com/design/x/y?node-id=1-2",
        project_dir=tmp_path / "proj",
        origin=JobOrigin.API.value,
        principal="ci-bot",
    )
    assert job.origin == JobOrigin.API
    assert job.principal == "ci-bot"
    assert job.discord_user_id is None
