"""Tests for GitLab issue description Figma URL parsing."""

from __future__ import annotations

import pytest

from control_panel.gitlab_workflow.parser import (
    extract_figma_frame_urls,
    extract_first_figma_frame_url,
)
from figma_flutter_agent.errors import FigmaUrlError


def test_extract_first_figma_frame_url_from_description() -> None:
    text = "Please generate this screen\n\nhttps://www.figma.com/design/abc123/App?node-id=12-34\n"
    url = extract_first_figma_frame_url(text)
    assert "abc123" in url
    assert "node-id=12-34" in url


def test_extract_figma_frame_urls_rejects_multiple() -> None:
    text = (
        "https://www.figma.com/design/a/A?node-id=1-2\n"
        "https://www.figma.com/design/b/B?node-id=3-4\n"
    )
    with pytest.raises(FigmaUrlError, match="exactly one"):
        extract_first_figma_frame_url(text)


def test_extract_figma_frame_urls_requires_node_id() -> None:
    text = "https://www.figma.com/design/abc123/App"
    assert extract_figma_frame_urls(text) == []
    with pytest.raises(FigmaUrlError):
        extract_first_figma_frame_url(text)
