import json
from unittest.mock import MagicMock

from figma_flutter_agent.llm.client import _ANTHROPIC_TOOL_NAME, AnthropicLlmClient
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.llm.schema import generation_json_schema
from figma_flutter_agent.schemas import FlutterGenerationResponse


def test_anthropic_client_uses_tool_use_for_structured_output() -> None:
    mock_client = MagicMock()
    tool_input = {
        "screenCode": "class DemoScreen extends StatelessWidget { const DemoScreen({super.key}); @override Widget build(BuildContext c) => const SizedBox(); }",
        "extractedWidgets": [],
    }
    mock_block = MagicMock()
    mock_block.type = "tool_use"
    mock_block.name = _ANTHROPIC_TOOL_NAME
    mock_block.input = tool_input
    mock_response = MagicMock()
    mock_response.content = [mock_block]
    mock_client.messages.create.return_value = mock_response

    client = AnthropicLlmClient(
        api_key="test-key",
        model="claude-sonnet-4-6",
        temperature=0.1,
        top_p=0.95,
    )
    client._client = mock_client

    raw = client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())
    parsed = FlutterGenerationResponse.model_validate(json.loads(raw))

    assert parsed.screen_code.startswith("class DemoScreen")
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": _ANTHROPIC_TOOL_NAME}
    assert call_kwargs["tools"][0]["name"] == _ANTHROPIC_TOOL_NAME
    assert call_kwargs["tools"][0]["input_schema"] == generation_json_schema(strict=True)
    assert call_kwargs["temperature"] == 0.1
    assert call_kwargs["top_p"] == 0.95
