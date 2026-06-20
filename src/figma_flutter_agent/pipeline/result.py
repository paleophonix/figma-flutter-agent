"""Pipeline result model."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens


@dataclass
class PipelineResult:
    """Output of a pipeline run."""

    clean_tree: CleanDesignTreeNode
    tokens: DesignTokens
    planned_files: list[str] = field(default_factory=list)
    written_files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    run_id: str = ""
    clean_tree_hash: str = ""
    colors_hash: str = ""
    typography_hash: str = ""
    spacing_hash: str = ""
    dart_errors_log: str | None = None
    terminal_log: str | None = None
    render_log_dir: str | None = None
    debug_capture_dir: str | None = None
    flutter_capture_ok: bool | None = None
