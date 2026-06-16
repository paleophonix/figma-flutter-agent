"""GitHub REST client for tree scan and publish."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


class GitHubClient:
    """Minimal async GitHub API client."""

    def __init__(self, *, token: str, repo: str) -> None:
        self._token = token.strip()
        self._repo = repo.strip()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api(self, path: str) -> str:
        return f"https://api.github.com/repos/{self._repo}{path}"

    async def list_dart_files(self, *, lib_root: str) -> list[str]:
        """List screen candidate paths under ``lib_root``."""
        prefix = lib_root.strip("/").replace("\\", "/")
        if prefix and not prefix.endswith("/"):
            prefix = f"{prefix}/"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self._api("/git/trees/HEAD?recursive=1"),
                headers=self._headers,
            )
            response.raise_for_status()
            tree = response.json().get("tree") or []
        candidates: list[str] = []
        for item in tree:
            path = str(item.get("path") or "")
            if not path.startswith(prefix):
                continue
            if not path.endswith(".dart"):
                continue
            if "_screen.dart" in path or "/screens/" in path:
                candidates.append(path)
        return sorted(candidates)

    async def commit_files(
        self,
        *,
        branch: str,
        commit_message: str,
        files: dict[str, Path],
        start_branch: str | None = None,
    ) -> dict[str, Any]:
        """Create a commit on ``branch`` with the provided files."""
        base_branch = start_branch or branch
        async with httpx.AsyncClient(timeout=120.0) as client:
            ref_response = await client.get(
                self._api(f"/git/ref/heads/{quote(base_branch, safe='')}"),
                headers=self._headers,
            )
            ref_response.raise_for_status()
            base_sha = ref_response.json()["object"]["sha"]
            if base_branch != branch:
                await client.post(
                    self._api("/git/refs"),
                    headers=self._headers,
                    json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                )
            tree_items: list[dict[str, str]] = []
            for rel_path, path in files.items():
                content = base64.b64encode(path.read_bytes()).decode("ascii")
                blob_response = await client.post(
                    self._api("/git/blobs"),
                    headers=self._headers,
                    json={"content": content, "encoding": "base64"},
                )
                blob_response.raise_for_status()
                tree_items.append(
                    {
                        "path": rel_path.replace("\\", "/"),
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_response.json()["sha"],
                    }
                )
            tree_response = await client.post(
                self._api("/git/trees"),
                headers=self._headers,
                json={"tree": tree_items, "base_tree": base_sha},
            )
            tree_response.raise_for_status()
            commit_response = await client.post(
                self._api("/git/commits"),
                headers=self._headers,
                json={
                    "message": commit_message,
                    "tree": tree_response.json()["sha"],
                    "parents": [base_sha],
                },
            )
            commit_response.raise_for_status()
            commit_sha = commit_response.json()["sha"]
            await client.patch(
                self._api(f"/git/refs/heads/{quote(branch, safe='')}"),
                headers=self._headers,
                json={"sha": commit_sha},
            )
        return {"sha": commit_sha, "web_url": f"https://github.com/{self._repo}/tree/{branch}"}

    async def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        """Open a pull request."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._api("/pulls"),
                headers=self._headers,
                json={
                    "title": title,
                    "head": source_branch,
                    "base": target_branch,
                    "body": description,
                },
            )
            response.raise_for_status()
            return response.json()

    async def find_open_pull_request(
        self,
        *,
        branch: str,
        target_branch: str,
    ) -> dict[str, Any] | None:
        """Return an open pull request for ``branch`` if one exists."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self._api("/pulls"),
                headers=self._headers,
                params={"state": "open", "head": f"{self._repo.split('/')[0]}:{branch}"},
            )
            response.raise_for_status()
            pulls = response.json()
        for pull in pulls:
            if str((pull.get("base") or {}).get("ref") or "") == target_branch:
                return pull
        return None

    async def commit_files_update(
        self,
        *,
        branch: str,
        commit_message: str,
        files: dict[str, Path],
    ) -> dict[str, Any]:
        """Update files on an existing branch."""
        return await self.commit_files(
            branch=branch,
            commit_message=commit_message,
            files=files,
            start_branch=branch,
        )
