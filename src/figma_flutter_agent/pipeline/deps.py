"""Composition root for injectable pipeline dependencies."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from figma_flutter_agent.stages.write import WriteStageRequest, WriteStageResult

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import LlmError
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.llm.clients.core import LlmClient, create_llm_client
from figma_flutter_agent.llm.reasoning import LlmReasoningSettings

FigmaConnectorFactory = Callable[[str, str], Any]
LlmClientFactory = Callable[[Settings], LlmClient]
DartWriterFactory = Callable[..., DartWriter]
WriteStageFn = Callable[["WriteStageRequest"], "WriteStageResult"]


def _default_figma_connector(token: str, base_url: str) -> FigmaConnector:
    return FigmaConnector(token, base_url)


def _build_llm_client(
    settings: Settings,
    *,
    model: str,
    temperature: float | None = None,
    reasoning: LlmReasoningSettings | None = None,
) -> LlmClient:
    api_key = settings.llm_api_key()
    if not api_key:
        env_name = settings.llm_api_key_env_name()
        raise LlmError(
            f"LLM API key is missing. Set {env_name} or enable generation.use_deterministic_screen."
        )
    resolved_reasoning = (
        settings.resolved_llm_reasoning() if reasoning is None else reasoning
    )
    return create_llm_client(
        provider=settings.resolved_llm_provider(),
        api_key=api_key,
        model=model,
        require_strict_json_schema=settings.llm_require_strict_json_schema,
        temperature=temperature,
        top_p=settings.llm_top_p,
        reasoning=resolved_reasoning,
        max_retries=settings.llm_max_retries,
        max_output_tokens=settings.llm_max_output_tokens,
    )


def _default_llm_client(settings: Settings) -> LlmClient:
    return _build_llm_client(
        settings,
        model=settings.resolved_llm_generate_model(),
        temperature=settings.resolved_llm_generate_temperature(),
    )


def _default_llm_repair_client(settings: Settings) -> LlmClient:
    return _build_llm_client(
        settings,
        model=settings.resolved_llm_repair_model(),
        temperature=settings.resolved_llm_repair_temperature(),
    )


def _default_llm_refine_client(settings: Settings) -> LlmClient:
    return _build_llm_client(
        settings,
        model=settings.resolved_llm_refine_model(),
        temperature=settings.resolved_llm_generate_temperature(),
    )


def _default_dart_writer(
    project_dir: Path,
    *,
    enable_backup: bool,
    strict_preservation: bool,
) -> DartWriter:
    return DartWriter(
        project_dir,
        enable_backup=enable_backup,
        strict_preservation=strict_preservation,
    )


@dataclass(frozen=True)
class PipelineDependencies:
    """Injectable factories used by ``run_pipeline`` and stages."""

    figma_connector: FigmaConnectorFactory
    create_llm_client: LlmClientFactory
    create_llm_repair_client: LlmClientFactory
    create_llm_refine_client: LlmClientFactory
    commit_planned_files: WriteStageFn
    dart_writer_factory: DartWriterFactory


def default_pipeline_dependencies() -> PipelineDependencies:
    """Return production defaults (real Figma connector, LLM client, Dart writer)."""
    from figma_flutter_agent.stages.write import commit_planned_files

    return PipelineDependencies(
        figma_connector=_default_figma_connector,
        create_llm_client=_default_llm_client,
        create_llm_repair_client=_default_llm_repair_client,
        create_llm_refine_client=_default_llm_refine_client,
        commit_planned_files=commit_planned_files,
        dart_writer_factory=_default_dart_writer,
    )
