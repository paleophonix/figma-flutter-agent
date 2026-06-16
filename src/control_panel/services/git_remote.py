"""Git remote client protocol."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class GitRemoteClient(Protocol):
    """Minimal remote git API surface for publish."""

    async def list_dart_files(self, *, lib_root: str) -> list[str]:
        """List candidate Dart screen paths under ``lib_root``."""
        ...

    async def commit_files(
        self,
        *,
        branch: str,
        commit_message: str,
        files: dict[str, Path],
        start_branch: str | None = None,
    ) -> dict[str, Any]:
        """Create or update a branch with file contents."""
        ...

    async def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> dict[str, Any]:
        """Open a merge/pull request."""
        ...

    async def find_open_pull_request(
        self,
        *,
        branch: str,
        target_branch: str,
    ) -> dict[str, Any] | None:
        """Return an open PR/MR for the branch when present."""
        ...
