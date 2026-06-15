"""Retry/backoff mixin for LLM clients."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from loguru import logger

from figma_flutter_agent.errors import LlmError, format_error_for_log
from figma_flutter_agent.llm.reasoning import LLM_OUTPUT_TOKEN_CAP

_T = TypeVar("_T")


class RetryMixin:
    """Retry/backoff helpers shared across LLM provider clients.

    Expects the host class to provide ``_model``, ``_max_retries`` and
    ``_effective_max_output_tokens`` / ``_max_output_tokens_override``.
    """

    @staticmethod
    def _is_retryable(exc: LlmError) -> bool:
        if RetryMixin._is_truncation_error(exc):
            return False
        return exc.status_code is None or exc.status_code in {429, 500, 502, 503, 504}

    @staticmethod
    def _is_truncation_error(exc: LlmError) -> bool:
        message = str(exc).lower()
        return "truncated" in message or "max_tokens reached" in message

    def _bump_output_token_limit_after_truncation(self) -> bool:
        current = self._effective_max_output_tokens()
        if current >= LLM_OUTPUT_TOKEN_CAP:
            return False
        bumped = min(current * 2, LLM_OUTPUT_TOKEN_CAP)
        if bumped <= current:
            return False
        self._max_output_tokens_override = bumped
        logger.warning(
            "LLM response truncated at max_tokens={}; retrying with max_tokens={}",
            current,
            bumped,
        )
        return True

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return float((2**attempt) + random.uniform(0.1, 1.0))

    def _log_retry(self, exc: LlmError, *, delay: float, attempt: int) -> None:
        logger.warning(
            "LLM request failed for model {}: {} — retrying in {:.2f}s (attempt {}/{})",
            self._model,
            format_error_for_log(exc),
            delay,
            attempt + 1,
            self._max_retries,
        )

    def _run_with_retry(self, operation: Callable[[], _T]) -> _T:
        for attempt in range(self._max_retries):
            try:
                return operation()
            except LlmError as exc:
                if (
                    self._is_truncation_error(exc)
                    and self._bump_output_token_limit_after_truncation()
                ):
                    if attempt == self._max_retries - 1:
                        raise
                    delay = self._retry_delay(attempt)
                    self._log_retry(exc, delay=delay, attempt=attempt)
                    time.sleep(delay)
                    continue
                if not self._is_retryable(exc) or attempt == self._max_retries - 1:
                    raise
                delay = self._retry_delay(attempt)
                self._log_retry(exc, delay=delay, attempt=attempt)
                time.sleep(delay)
        raise LlmError("LLM generation failed after retries")

    async def _run_with_retry_async(
        self,
        operation: Callable[[], Awaitable[_T]],
    ) -> _T:
        for attempt in range(self._max_retries):
            try:
                return await operation()
            except LlmError as exc:
                if (
                    self._is_truncation_error(exc)
                    and self._bump_output_token_limit_after_truncation()
                ):
                    if attempt == self._max_retries - 1:
                        raise
                    delay = self._retry_delay(attempt)
                    self._log_retry(exc, delay=delay, attempt=attempt)
                    await asyncio.sleep(delay)
                    continue
                if not self._is_retryable(exc) or attempt == self._max_retries - 1:
                    raise
                delay = self._retry_delay(attempt)
                self._log_retry(exc, delay=delay, attempt=attempt)
                await asyncio.sleep(delay)
        raise LlmError("LLM generation failed after retries")
