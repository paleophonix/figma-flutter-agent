"""Hot-triage debug artifact bundle for wizard agent debug."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.debug.paths import debug_path_display, screen_root
from figma_flutter_agent.errors import FigmaFlutterError

# Keep in sync with control_panel.repair.snapshot.DEFAULT_SNAPSHOT_FILES.
DEBUG_CONTEXT_FILES: tuple[str, ...] = (
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

OPTIONAL_DEBUG_CONTEXT_FILES: tuple[str, ...] = ("raw.json",)

LOG_TAIL_BYTES = 32_000

REQUIRED_ANY_OF: tuple[str, ...] = ("processed.json", "last.log")


@dataclass(frozen=True)
class DebugContextBundle:
    """Resolved debug artifacts for one screen."""

    project_dir: Path
    feature: str
    screen_root: Path
    present_files: tuple[str, ...]
    missing_optional: tuple[str, ...]
    log_tail: str


def _read_log_tail(path: Path, *, max_bytes: int = LOG_TAIL_BYTES) -> str:
    if not path.is_file():
        return ""
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[-max_bytes:]
    return data.decode("utf-8", errors="replace")


def collect_screen_debug_context(project_dir: Path, feature: str) -> DebugContextBundle:
    """Collect hot-triage debug artifacts for ``feature`` under canonical ``screen_root``.

    Args:
        project_dir: Flutter project root.
        feature: Screen feature slug from manifest.

    Returns:
        Bundle with present files and log tail.

    Raises:
        FigmaFlutterError: When the screen debug root is missing or has no minimum artifacts.
    """
    root = screen_root(project_dir, feature)
    if not root.is_dir():
        display = debug_path_display(root, project_dir)
        raise FigmaFlutterError(
            f"Debug bundle missing for screen {feature!r} at {display}. "
            "Run generate or fetch first."
        )

    present: list[str] = []
    for name in DEBUG_CONTEXT_FILES:
        if (root / name).is_file():
            present.append(name)

    missing_optional = tuple(
        name for name in OPTIONAL_DEBUG_CONTEXT_FILES if not (root / name).is_file()
    )

    if not any(name in present for name in REQUIRED_ANY_OF):
        display = debug_path_display(root, project_dir)
        raise FigmaFlutterError(
            f"Debug bundle at {display} has no processed.json or last.log. "
            "Run generate first."
        )

    log_tail = _read_log_tail(root / "last.log")
    return DebugContextBundle(
        project_dir=project_dir,
        feature=feature,
        screen_root=root,
        present_files=tuple(present),
        missing_optional=missing_optional,
        log_tail=log_tail,
    )
