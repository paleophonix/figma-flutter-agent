import json
from unittest.mock import MagicMock

from figma_flutter_agent.llm.client import GoogleLlmClient
from figma_flutter_agent.llm.prompts import build_system_prompt
from figma_flutter_agent.llm.schema import generation_json_schema
from figma_flutter_agent.schemas import FlutterGenerationResponse


def test_google_client_uses_openai_compat_with_json_schema() -> None:
    mock_client = MagicMock()
    tool_input = {
        "screenCode": "class DemoScreen extends StatelessWidget { const DemoScreen({super.key}); @override Widget build(BuildContext c) => const SizedBox(); }",
        "extractedWidgets": [],
    }
    mock_message = MagicMock()
    mock_message.content = json.dumps(tool_input)
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response

    client = GoogleLlmClient(
        api_key="test-key",
        model="gemini-2.0-flash",
        temperature=0.0,
        top_p=1.0,
    )
    client._client = mock_client

    raw = client._request_generation('{"featureName":"demo"}', system_prompt=build_system_prompt())
    parsed = FlutterGenerationResponse.model_validate(json.loads(raw))

    assert parsed.screen_code.startswith("class DemoScreen")
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.0-flash"
    assert call_kwargs["response_format"]["type"] == "json_schema"
    assert call_kwargs["response_format"]["json_schema"]["strict"] is False
    assert call_kwargs["response_format"]["json_schema"]["schema"] == generation_json_schema(
        strict=False
    )
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["top_p"] == 1.0
