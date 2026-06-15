"""OpenAiLlmClient — Flutter codegen via OpenAI Chat Completions API."""

from __future__ import annotations

import time

import httpx
from loguru import logger
from openai import APIError as OpenAIAPIError
from openai import APITimeoutError, OpenAI

from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.llm.capabilities import LlmProvider
from figma_flutter_agent.llm.clients.client import (
    _LLM_DEFAULT_MAX_RETRIES,
    _LLM_HTTP_CONNECT_TIMEOUT_SEC,
    _LLM_HTTP_TIMEOUT_SEC,
    BaseLlmClient,
)
from figma_flutter_agent.llm.clients.content import _build_openai_user_content
from figma_flutter_agent.llm.clients.protocol import _first_chat_choice, _provider_api_label
from figma_flutter_agent.llm.prompts import REFERENCE_USER_PREAMBLE
from figma_flutter_agent.llm.reasoning import DEFAULT_LLM_MAX_OUTPUT_TOKENS, LlmReasoningSettings
from figma_flutter_agent.llm.schema import StructuredOutputSpec, generation_output_spec


class OpenAiLlmClient(BaseLlmClient):
    """Generate Flutter widget code through the OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
        provider: LlmProvider = "openai",
        strict_json_schema: bool = True,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning: LlmReasoningSettings | None = None,
        max_retries: int = _LLM_DEFAULT_MAX_RETRIES,
        max_output_tokens: int = DEFAULT_LLM_MAX_OUTPUT_TOKENS,
    ) -> None:
        super().__init__(
            model,
            provider=provider,
            strict_json_schema=strict_json_schema,
            temperature=temperature,
            top_p=top_p,
            reasoning=reasoning,
            max_retries=max_retries,
            max_output_tokens=max_output_tokens,
        )
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=httpx.Timeout(
                _LLM_HTTP_TIMEOUT_SEC,
                connect=_LLM_HTTP_CONNECT_TIMEOUT_SEC,
            ),
        )
        from figma_flutter_agent.llm.reasoning import openai_output_token_param

        self._openai_output_token_param = openai_output_token_param(model)
        self._openai_suppressed_sampling: set[str] = set()

    def _openai_sampling_kwargs(self) -> dict[str, float]:
        from figma_flutter_agent.llm.reasoning import openai_allows_top_p

        kwargs = super()._sampling_kwargs()
        if not openai_allows_top_p(self._model):
            kwargs.pop("top_p", None)
        for key in self._openai_suppressed_sampling:
            kwargs.pop(key, None)
        return kwargs

    def _openai_output_token_limit_kwargs(self) -> dict[str, int]:
        limit = self._effective_max_output_tokens()
        return {self._openai_output_token_param: limit}

    def _openai_create_kwargs(
        self,
        *,
        system_prompt: str,
        user_content: str | list[dict[str, object]],
        include_reasoning: bool,
        output_spec: StructuredOutputSpec,
    ) -> dict[str, object]:
        schema_strict = self._strict_json_schema
        kwargs: dict[str, object] = {
            "model": self._model,
            **self._openai_output_token_limit_kwargs(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": output_spec.name,
                    "strict": schema_strict,
                    "schema": output_spec.schema,
                },
            },
            **self._openai_sampling_kwargs(),
        }
        if include_reasoning:
            reasoning_payload = self._reasoning_settings.openrouter_payload()
            if reasoning_payload is not None:
                kwargs["extra_body"] = {"reasoning": reasoning_payload}
        return kwargs

    def _openai_chat_completion(
        self,
        *,
        system_prompt: str,
        user_content: str | list[dict[str, object]],
        output_spec: StructuredOutputSpec,
    ) -> object:
        """Call Chat Completions with optional reasoning and compatibility fallback."""
        include_reasoning = self._include_reasoning()
        try:
            return self._client.chat.completions.create(
                **self._openai_create_kwargs(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    include_reasoning=include_reasoning,
                    output_spec=output_spec,
                )
            )
        except OpenAIAPIError as exc:
            llm_error = self._openai_llm_error(exc)
        except (APITimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
            llm_error = LlmError(
                f"{_provider_api_label(self._provider)} request timed out "
                f"(model={self._model}): {exc}",
                status_code=None,
            )

        from figma_flutter_agent.llm.reasoning import (
            is_unsupported_max_tokens_error,
            is_unsupported_openai_param_error,
        )

        def _retry_openai_create() -> object:
            return self._client.chat.completions.create(
                **self._openai_create_kwargs(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    include_reasoning=include_reasoning,
                    output_spec=output_spec,
                )
            )

        if (
            is_unsupported_max_tokens_error(
                status_code=llm_error.status_code,
                message=str(llm_error),
            )
            and self._openai_output_token_param == "max_tokens"
        ):
            self._openai_output_token_param = "max_completion_tokens"
            logger.info(
                "OpenAI model {} requires max_completion_tokens; retrying",
                self._model,
            )
            try:
                return _retry_openai_create()
            except OpenAIAPIError as exc:
                llm_error = self._openai_llm_error(exc)
            except (APITimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
                llm_error = LlmError(
                    f"{_provider_api_label(self._provider)} request timed out "
                    f"(model={self._model}): {exc}",
                    status_code=None,
                )

        for param in ("top_p", "temperature"):
            if param in self._openai_suppressed_sampling:
                continue
            if not is_unsupported_openai_param_error(
                status_code=llm_error.status_code,
                message=str(llm_error),
                param=param,
            ):
                continue
            self._openai_suppressed_sampling.add(param)
            logger.info(
                "OpenAI model {} rejected {}; retrying without it",
                self._model,
                param,
            )
            try:
                return _retry_openai_create()
            except OpenAIAPIError as exc:
                llm_error = self._openai_llm_error(exc)
            except (APITimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
                llm_error = LlmError(
                    f"{_provider_api_label(self._provider)} request timed out "
                    f"(model={self._model}): {exc}",
                    status_code=None,
                )
            break

        if not self._should_retry_without_reasoning(llm_error):
            raise llm_error
        self._suppress_reasoning_after_rejection(llm_error)
        try:
            return self._client.chat.completions.create(
                **self._openai_create_kwargs(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    include_reasoning=False,
                    output_spec=output_spec,
                )
            )
        except OpenAIAPIError as exc:
            raise self._openai_llm_error(exc) from exc
        except (APITimeoutError, httpx.TimeoutException, httpx.TransportError) as exc:
            raise LlmError(
                f"{_provider_api_label(self._provider)} request timed out "
                f"(model={self._model}): {exc}",
                status_code=None,
            ) from exc

    def _request_generation(
        self,
        prompt: str,
        *,
        system_prompt: str,
        figma_reference_png: bytes | None = None,
        flutter_render_png: bytes | None = None,
        visual_diff_png: bytes | None = None,
        user_preamble: str = REFERENCE_USER_PREAMBLE,
        output_spec: StructuredOutputSpec | None = None,
        analytics_span_name: str | None = None,
    ) -> str:
        spec = output_spec or generation_output_spec(strict=self._strict_json_schema)
        user_content = _build_openai_user_content(
            prompt,
            figma_reference_png,
            flutter_render_png,
            visual_diff_png,
            user_preamble=user_preamble,
        )
        started = time.perf_counter()
        try:
            response = self._openai_chat_completion(
                system_prompt=system_prompt,
                user_content=user_content,
                output_spec=spec,
            )

            choice = _first_chat_choice(
                response,
                provider=self._provider,
                model=self._model,
            )
            if choice.finish_reason == "length":
                raise LlmError("LLM response truncated (max_tokens reached)")
            message = choice.message
            if not message.content:
                raise LlmError("LLM returned no text content")
            usage = getattr(response, "usage", None)
            self._emit_llm_analytics(
                latency_sec=time.perf_counter() - started,
                system_prompt=system_prompt,
                user_prompt=prompt,
                output_text=message.content,
                is_error=False,
                input_tokens=getattr(usage, "prompt_tokens", None),
                output_tokens=getattr(usage, "completion_tokens", None),
                analytics_span_name=analytics_span_name,
            )
            return message.content
        except Exception as exc:
            self._emit_llm_analytics(
                latency_sec=time.perf_counter() - started,
                system_prompt=system_prompt,
                user_prompt=prompt,
                output_text=None,
                is_error=True,
                error_message=str(exc),
                analytics_span_name=analytics_span_name,
            )
            raise
