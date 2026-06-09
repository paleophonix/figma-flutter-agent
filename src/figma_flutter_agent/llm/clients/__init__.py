"""LLM clients package — re-exports public API."""

from figma_flutter_agent.llm.clients.protocol import LlmClient
from figma_flutter_agent.llm.clients.client import BaseLlmClient
from figma_flutter_agent.llm.clients.content import (
    _build_anthropic_user_content,
    _build_openai_user_content,
    _encode_png_base64,
    _is_visual_refine_attachment,
)
from figma_flutter_agent.llm.clients.anthropic import AnthropicLlmClient, _ANTHROPIC_TOOL_NAME
from figma_flutter_agent.llm.clients.openai import OpenAiLlmClient
from figma_flutter_agent.llm.clients.openrouter import OpenRouterLlmClient
from figma_flutter_agent.llm.clients.google import GoogleLlmClient
from figma_flutter_agent.llm.clients.factory import create_llm_client, default_model_for_provider

__all__ = [
    "LlmClient",
    "BaseLlmClient",
    "AnthropicLlmClient",
    "OpenAiLlmClient",
    "OpenRouterLlmClient",
    "GoogleLlmClient",
    "create_llm_client",
    "default_model_for_provider",
]
