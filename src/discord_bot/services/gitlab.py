"""GitLab REST client for issues, merge requests, and file uploads."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from loguru import logger


class GitLabClient:
    """Minimal async GitLab API client."""

    def __init__(self, *, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token.strip()

    @property
    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self._token}

    def _project_path(self, project_id: str) -> str:
        return quote(project_id, safe="")

    async def get_project(self, project_id: str) -> dict[str, Any]:
        """Fetch project metadata."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}",
                headers=self._headers,
            )
            response.raise_for_status()
            return response.json()

    async def resolve_user_id(self, username: str) -> int | None:
        """Resolve GitLab user id by username."""
        if not username.strip():
            return None
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self._base_url}/api/v4/users",
                headers=self._headers,
                params={"username": username},
            )
            response.raise_for_status()
            users = response.json()
        if not users:
            return None
        return int(users[0]["id"])

    async def create_issue(
        self,
        *,
        project_id: str,
        title: str,
        description: str,
        labels: list[str],
        assignee_username: str = "",
    ) -> dict[str, Any]:
        """Create a GitLab issue."""
        payload: dict[str, Any] = {
            "title": title,
            "description": description,
            "labels": ",".join(labels),
        }
        assignee_id = await self.resolve_user_id(assignee_username)
        if assignee_id is not None:
            payload["assignee_ids"] = [assignee_id]
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}/issues",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    async def create_issue_note_with_upload(
        self,
        *,
        project_id: str,
        issue_iid: int,
        body: str,
        upload_path: Path | None = None,
    ) -> None:
        """Attach an uploaded file reference as an issue note."""
        note_body = body
        if upload_path is not None and upload_path.is_file():
            uploaded = await self.upload_file(
                project_id=project_id,
                filename=upload_path.name,
                filepath=upload_path,
            )
            markdown = uploaded.get("markdown") or uploaded.get("url") or ""
            note_body = f"{body}\n\n{markdown}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                (
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}"
                    f"/issues/{issue_iid}/notes"
                ),
                headers=self._headers,
                data={"body": note_body},
            )
            response.raise_for_status()

    async def upload_file(
        self,
        *,
        project_id: str,
        filename: str,
        filepath: Path,
    ) -> dict[str, Any]:
        """Upload a file to a GitLab project."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            with filepath.open("rb") as handle:
                response = await client.post(
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}/uploads",
                    headers=self._headers,
                    files={"file": (filename, handle)},
                )
            response.raise_for_status()
            return response.json()

    async def create_merge_request(
        self,
        *,
        project_id: str,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        assignee_username: str = "",
        reviewer_usernames: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a merge request."""
        data: dict[str, str] = {
            "source_branch": source_branch,
            "target_branch": target_branch,
            "title": title,
            "description": description,
            "remove_source_branch": "true",
        }
        assignee_id = await self.resolve_user_id(assignee_username)
        if assignee_id is not None:
            data["assignee_id"] = str(assignee_id)
        reviewer_ids: list[int] = []
        for username in reviewer_usernames or []:
            user_id = await self.resolve_user_id(username)
            if user_id is not None:
                reviewer_ids.append(user_id)
        if reviewer_ids:
            data["reviewer_ids"] = ",".join(str(item) for item in reviewer_ids)
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                (
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}"
                    "/merge_requests"
                ),
                headers=self._headers,
                data=data,
            )
            response.raise_for_status()
            return response.json()

    async def commit_files(
        self,
        *,
        project_id: str,
        branch: str,
        commit_message: str,
        files: dict[str, Path],
        start_branch: str | None = None,
    ) -> dict[str, Any]:
        """Create a commit with multiple file actions via GitLab API."""
        actions: list[dict[str, str]] = []
        for rel_path, path in files.items():
            content = base64.b64encode(path.read_bytes()).decode("ascii")
            actions.append(
                {
                    "action": "create",
                    "file_path": rel_path.replace("\\", "/"),
                    "content": content,
                    "encoding": "base64",
                }
            )
        payload: dict[str, Any] = {
            "branch": branch,
            "commit_message": commit_message,
            "actions": actions,
        }
        if start_branch:
            payload["start_branch"] = start_branch
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}/repository/commits",
                headers=self._headers,
                json=payload,
            )
            if response.status_code == 400 and "already exists" in response.text.lower():
                logger.warning("GitLab commit failed; retrying with update actions")
                update_actions: list[dict[str, str]] = []
                for rel_path, path in files.items():
                    content = base64.b64encode(path.read_bytes()).decode("ascii")
                    update_actions.append(
                        {
                            "action": "update",
                            "file_path": rel_path.replace("\\", "/"),
                            "content": content,
                            "encoding": "base64",
                        }
                    )
                payload["actions"] = update_actions
                response = await client.post(
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}/repository/commits",
                    headers=self._headers,
                    json=payload,
                )
            response.raise_for_status()
            return response.json()

    async def commit_artifact_tree(
        self,
        *,
        project_id: str,
        branch: str,
        prefix: str,
        files: dict[str, Path],
        commit_message: str,
    ) -> str:
        """Commit artifact files under ``prefix/`` and return commit web URL."""
        mapped = {f"{prefix}/{name}": path for name, path in files.items()}
        commit = await self.commit_files(
            project_id=project_id,
            branch=branch,
            commit_message=commit_message,
            files=mapped,
            start_branch=branch,
        )
        return str(commit.get("web_url") or "")

    async def list_dart_files(self, *, project_id: str, lib_root: str) -> list[str]:
        """List screen candidate paths via repository tree API."""
        prefix = lib_root.strip("/").replace("\\", "/")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                (
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}"
                    "/repository/tree"
                ),
                headers=self._headers,
                params={"recursive": True, "per_page": 100},
            )
            response.raise_for_status()
            items = response.json()
        candidates: list[str] = []
        for item in items:
            path = str(item.get("path") or "")
            if prefix and not path.startswith(prefix):
                continue
            if path.endswith(".dart") and ("_screen.dart" in path or "/screens/" in path):
                candidates.append(path)
        return sorted(candidates)

    async def find_open_merge_request(
        self,
        *,
        project_id: str,
        source_branch: str,
        target_branch: str,
    ) -> dict[str, Any] | None:
        """Return an open merge request for ``source_branch`` when present."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                (
                    f"{self._base_url}/api/v4/projects/{self._project_path(project_id)}"
                    "/merge_requests"
                ),
                headers=self._headers,
                params={"state": "opened", "source_branch": source_branch},
            )
            response.raise_for_status()
            items = response.json()
        for item in items:
            if str(item.get("target_branch") or "") == target_branch:
                return item
        return None
