"""Tests for publish git checkout helpers."""

from __future__ import annotations

from control_panel.publish.checkout import authenticated_git_remote_url


def test_authenticated_git_remote_url_injects_gitlab_oauth2_token() -> None:
    url = authenticated_git_remote_url(
        remote_url="https://gitlab.com/group/project.git",
        token="glpat-secret",
    )
    assert url.startswith("https://oauth2:")
    assert "glpat-secret" in url
    assert url.endswith("gitlab.com/group/project.git")


def test_authenticated_git_remote_url_leaves_empty_token_unchanged() -> None:
    remote = "https://gitlab.com/group/project.git"
    assert authenticated_git_remote_url(remote_url=remote, token="") == remote
