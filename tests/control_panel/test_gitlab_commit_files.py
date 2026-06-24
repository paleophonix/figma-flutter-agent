"""Tests for GitLab commit action selection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from control_panel.services.gitlab import GitLabClient


@pytest.mark.asyncio
async def test_commit_files_uses_update_for_files_on_start_branch(tmp_path: Path) -> None:
    """New issue branches inherit ``start_branch`` files and must use update."""
    dart_path = tmp_path / "lib" / "features" / "login" / "login_screen.dart"
    dart_path.parent.mkdir(parents=True)
    dart_path.write_text("void main() {}", encoding="utf-8")

    client = GitLabClient(base_url="https://gitlab.com", token="token")

    async def fake_branch_exists(
        _client: httpx.AsyncClient,
        *,
        project_id: str,
        branch: str,
    ) -> bool:
        _ = (project_id, branch)
        return False

    async def fake_file_exists(
        _client: httpx.AsyncClient,
        *,
        project_id: str,
        branch: str,
        file_path: str,
    ) -> bool:
        _ = project_id
        return branch == "main" and file_path == "lib/features/login/login_screen.dart"

    captured: dict[str, object] = {}

    async def fake_post(url: str, *, headers: dict[str, str], json: dict[str, object]) -> MagicMock:
        _ = (url, headers)
        captured["actions"] = json.get("actions")
        response = MagicMock()
        response.status_code = 201
        response.text = "{}"
        response.json.return_value = {"id": "abc"}
        response.raise_for_status = MagicMock()
        return response

    mock_http = MagicMock()
    mock_http.get = AsyncMock()
    mock_http.post = AsyncMock(side_effect=fake_post)
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(client, "_branch_exists", side_effect=fake_branch_exists),
        patch.object(client, "_file_exists_on_branch", side_effect=fake_file_exists),
        patch("control_panel.services.gitlab.httpx.AsyncClient", return_value=mock_http),
    ):
        await client.commit_files(
            project_id="83548281",
            branch="figma/issue-4",
            commit_message="feat: test",
            files={"lib/features/login/login_screen.dart": dart_path},
            start_branch="main",
        )

    actions = captured.get("actions")
    assert isinstance(actions, list)
    assert actions[0]["action"] == "update"
