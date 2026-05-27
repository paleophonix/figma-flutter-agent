import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from figma_flutter_agent.llm.client import _ANTHROPIC_TOOL_NAME, AnthropicLlmClient, GoogleLlmClient
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.validation.reference import (
    load_cached_reference_png,
    reference_png_path,
    resolve_figma_reference_png,
)


def test_build_system_prompt_includes_visual_reference_rule_when_attached() -> None:
    prompt = build_system_prompt(figma_reference_attached=True)
    assert "VISUAL GOLD STANDARD" in prompt
    assert "golden standard" in prompt.lower()


def test_build_system_prompt_omits_visual_reference_rule_by_default() -> None:
    prompt = build_system_prompt(figma_reference_attached=False)
    assert "VISUAL GOLD STANDARD" not in prompt


def test_anthropic_client_attaches_reference_png_to_user_message() -> None:
    mock_client = MagicMock()
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = _ANTHROPIC_TOOL_NAME
    mock_block.input = {"screenCode": "class Demo {}", "extractedWidgets": []}
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    client = AnthropicLlmClient(api_key="test-key", model="claude-sonnet-4-6")
    client._client = mock_client

    client._request_generation(
        '{"featureName":"demo"}',
        system_prompt=build_system_prompt(figma_reference_attached=True),
        figma_reference_png=b"\x89PNG\r\n\x1a\n",
    )

    call_kwargs = mock_client.messages.create.call_args.kwargs
    user_content = call_kwargs["messages"][0]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "text"
    assert user_content[1]["type"] == "image"
    assert user_content[2]["type"] == "text"
    assert "Golden-standard Figma export" in user_content[0]["text"]


def test_google_client_attaches_reference_png_to_user_message() -> None:
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps({"screenCode": "class Demo {}", "extractedWidgets": []})
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    client = GoogleLlmClient(api_key="test-key", model="gemini-2.0-flash")
    client._client = mock_client

    client._request_generation(
        '{"featureName":"demo"}',
        system_prompt=build_system_prompt(figma_reference_attached=True),
        figma_reference_png=b"\x89PNG\r\n\x1a\n",
    )

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_content = call_kwargs["messages"][1]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "text"
    assert user_content[1]["type"] == "image_url"


@pytest.mark.asyncio
async def test_resolve_figma_reference_png_live_fetch_for_llm(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    connector = MagicMock()
    connector.fetch_image_urls = AsyncMock(
        return_value=MagicMock(urls={"1:2": "https://figma.example/png"})
    )
    connector.download_bytes = AsyncMock(return_value=b"png-bytes")

    resolution = await resolve_figma_reference_png(
        connector=connector,
        file_key="abc",
        node_id="1:2",
        project_dir=project_dir,
        feature_name="music_v2",
        figma_root={"absoluteBoundingBox": {"width": 360, "height": 800}},
        scale=2.0,
        attach_to_llm=True,
        save_to_disk=True,
        from_dump=False,
    )

    assert resolution.png_bytes == b"png-bytes"
    assert resolution.image_hash is not None
    assert resolution.export is not None
    assert reference_png_path(project_dir, "music_v2").is_file()
    assert load_cached_reference_png(project_dir, "music_v2") == b"png-bytes"


@pytest.mark.asyncio
async def test_resolve_figma_reference_png_loads_cached_dump_png(tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    path = reference_png_path(project_dir, "music_v2")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"cached-png")

    resolution = await resolve_figma_reference_png(
        connector=None,
        file_key="abc",
        node_id="1:2",
        project_dir=project_dir,
        feature_name="music_v2",
        figma_root={},
        scale=2.0,
        attach_to_llm=True,
        save_to_disk=False,
        from_dump=True,
    )

    assert resolution.png_bytes == b"cached-png"
