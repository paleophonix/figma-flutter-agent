"""Run generate pipeline across a batch manifest."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from figma_flutter_agent.batch.manifest import BatchManifest, ScreenEntry, default_dump_path
from figma_flutter_agent.config import Settings
from figma_flutter_agent.debug.paths import resolve_screen_raw_dump
from figma_flutter_agent.figma.url import build_figma_url
from figma_flutter_agent.pipeline.deps import PipelineDependencies
from figma_flutter_agent.pipeline.result import PipelineResult
from figma_flutter_agent.pipeline.run import run_pipeline


@dataclass
class ScreenBatchResult:
    """Outcome for one screen in a batch run."""

    feature: str
    node_id: str
    success: bool
    dump_path: Path | None = None
    pipeline: PipelineResult | None = None
    error: str | None = None


@dataclass
class BatchRunReport:
    """Aggregated batch generate report."""

    results: list[ScreenBatchResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True when every screen succeeded."""
        return all(item.success for item in self.results)

    @property
    def failures(self) -> list[ScreenBatchResult]:
        """Return failed screen results."""
        return [item for item in self.results if not item.success]


def _resolve_dump(screen: ScreenEntry, project_dir: Path) -> Path:
    explicit = screen.dump if screen.dump is not None and screen.dump.is_file() else None
    return resolve_screen_raw_dump(
        project_dir,
        screen.feature,
        screen.node_id,
        explicit=explicit,
    )


def _figma_url_for_screen(manifest: BatchManifest, screen: ScreenEntry) -> str:
    if screen.figma_url:
        return screen.figma_url
    if manifest.figma_file_url:
        dashed = screen.node_id.replace(":", "-")
        separator = "&" if "?" in manifest.figma_file_url else "?"
        return f"{manifest.figma_file_url}{separator}node-id={dashed}"
    return build_figma_url(manifest.file_key, screen.node_id)


async def run_batch_generate(
    manifest: BatchManifest,
    settings: Settings,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    allow_dev_profile: bool = False,
    regenerate_templates: bool = False,
    require_dump: bool = True,
    force_llm_regen: bool = False,
    deps: PipelineDependencies | None = None,
) -> BatchRunReport:
    """Generate Flutter outputs for every screen in ``manifest``.

    Args:
        manifest: Batch screen manifest.
        settings: Agent settings.
        dry_run: Plan without writing files.
        verbose: Verbose logging.
        allow_dev_profile: Passed through to pipeline credential checks indirectly.
        regenerate_templates: Force template rewrite during incremental sync.
        require_dump: When True, skip screens without a cached dump file.

    Returns:
        ``BatchRunReport`` with per-screen outcomes.
    """
    report = BatchRunReport()
    for screen in manifest.screens:
        dump_path = _resolve_dump(screen, manifest.project_dir)
        if require_dump and not dump_path.is_file():
            report.results.append(
                ScreenBatchResult(
                    feature=screen.feature,
                    node_id=screen.node_id,
                    success=False,
                    dump_path=dump_path,
                    error=f"Dump missing: {dump_path.as_posix()} (run batch dump first)",
                )
            )
            continue
        figma_url = _figma_url_for_screen(manifest, screen)
        log = logger.bind(feature=screen.feature, node_id=screen.node_id)
        try:
            pipeline_result = await run_pipeline(
                settings,
                figma_url=figma_url,
                project_dir=manifest.project_dir,
                feature_name=screen.feature,
                dry_run=dry_run,
                verbose=verbose,
                regenerate_templates=regenerate_templates,
                from_dump=dump_path if dump_path.is_file() else None,
                require_figma_token=not dump_path.is_file(),
                force_llm_regen=force_llm_regen,
                deps=deps,
            )
            log.info(
                "Batch screen {} OK ({} planned files)",
                screen.feature,
                len(pipeline_result.planned_files),
            )
            report.results.append(
                ScreenBatchResult(
                    feature=screen.feature,
                    node_id=screen.node_id,
                    success=True,
                    dump_path=dump_path,
                    pipeline=pipeline_result,
                )
            )
        except Exception as exc:
            log.exception("Batch screen {} failed", screen.feature)
            report.results.append(
                ScreenBatchResult(
                    feature=screen.feature,
                    node_id=screen.node_id,
                    success=False,
                    dump_path=dump_path,
                    error=str(exc),
                )
            )
    return report
