"""Processed debug snapshot copy for repair worktrees."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.debug.paths import screen_root

DEFAULT_SNAPSHOT_FILES: tuple[str, ...] = (
    "processed.json",
    "pre_emit.json",
    "llm_validated.json",
    "dart-errors.json",
    "last.log",
    "semantics.json",
    "contract_emit_diff.md",
    "run.meta.json",
    "figma.png",
)

OPTIONAL_RAW_FILE = "raw.json"

LOG_TAIL_BYTES = 32_000


@dataclass(frozen=True)
class RepairSnapshotResult:
    """Outcome of copying processed artifacts into a worktree."""

    source_screen_root: Path
    dest_debug_root: Path
    copied_files: tuple[str, ...]
    include_raw: bool


def repair_debug_dest(worktree: Path, project_slug: str, feature_slug: str) -> Path:
    """Return ``<worktree>/.repair/debug/<project>/<feature>/``."""
    return worktree / ".repair" / "debug" / project_slug / feature_slug


def _tail_file(src: Path, dest: Path, *, max_bytes: int) -> None:
    """Copy the last ``max_bytes`` of a text file."""
    data = src.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    dest.write_bytes(data)


def copy_processed_snapshot(
    *,
    flutter_project_dir: Path,
    feature_slug: str,
    worktree: Path,
    project_slug: str,
    include_raw_fallback: bool = False,
) -> RepairSnapshotResult:
    """Copy processed-first debug artifacts into the repair worktree.

    Args:
        flutter_project_dir: Flutter project that produced the screen debug bundle.
        feature_slug: Screen feature slug.
        worktree: Agent-repo git worktree root.
        project_slug: Debug project label (usually Flutter project folder name).
        include_raw_fallback: When true, also copy ``raw.json`` if present.

    Returns:
        Paths and list of copied relative filenames.

    Raises:
        FileNotFoundError: When the source screen debug root is missing.
    """
    source = screen_root(flutter_project_dir, feature_slug)
    if not source.is_dir():
        raise FileNotFoundError(f"Screen debug root missing: {source}")
    dest = repair_debug_dest(worktree, project_slug, feature_slug)
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in DEFAULT_SNAPSHOT_FILES:
        src = source / name
        if not src.is_file():
            continue
        target = dest / name
        if name == "last.log":
            _tail_file(src, target, max_bytes=LOG_TAIL_BYTES)
        else:
            shutil.copy2(src, target)
        copied.append(name)
    if include_raw_fallback:
        raw_src = source / OPTIONAL_RAW_FILE
        if raw_src.is_file():
            shutil.copy2(raw_src, dest / OPTIONAL_RAW_FILE)
            copied.append(OPTIONAL_RAW_FILE)
    return RepairSnapshotResult(
        source_screen_root=source,
        dest_debug_root=dest,
        copied_files=tuple(copied),
        include_raw=include_raw_fallback and OPTIONAL_RAW_FILE in copied,
    )


def read_debug_text(debug_root: Path, name: str, *, limit: int = 4000) -> str:
    """Read a truncated text artifact from the repair debug bundle."""
    path = debug_root / name
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]
