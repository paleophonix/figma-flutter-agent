"""Wrap figma-flutter-agent pipeline execution for Discord jobs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from discord_bot.runner.feature_slug import infer_feature_slug
from figma_flutter_agent.config import apply_production_profile, load_settings
from figma_flutter_agent.config.paths import agent_repo_root
from figma_flutter_agent.figma.url import parse_figma_url
from figma_flutter_agent.pipeline.result import PipelineResult
from figma_flutter_agent.pipeline.run import run_pipeline


@dataclass(frozen=True)
class PipelineRunOutcome:
    """Pipeline result with derived metadata."""

    result: PipelineResult
    feature_slug: str | None
    project_dir: Path


async def execute_generation_pipeline(
    *,
    figma_url: str,
    project_dir: Path,
    agent_config_path: Path | None = None,
) -> PipelineRunOutcome:
    """Run the agent pipeline for one Discord job.

    Args:
        figma_url: Figma frame URL with node-id.
        project_dir: Target Flutter project root.
        agent_config_path: Optional agent YAML override.

    Returns:
        Pipeline outcome including inferred feature slug.
    """
    parse_figma_url(figma_url)
    config_path = agent_config_path
    if config_path is None:
        local = agent_repo_root() / ".ai-figma-flutter.yml"
        if local.is_file():
            config_path = local
    settings = load_settings(config_path)
    settings = apply_production_profile(settings)
    logger.info(
        "Discord runner starting pipeline project={} figma={}",
        project_dir.as_posix(),
        figma_url,
    )
    result = await run_pipeline(
        settings,
        figma_url=figma_url,
        project_dir=project_dir,
    )
    files = result.written_files or result.planned_files
    feature_slug = infer_feature_slug(files)
    return PipelineRunOutcome(
        result=result,
        feature_slug=feature_slug,
        project_dir=project_dir.resolve(),
    )
