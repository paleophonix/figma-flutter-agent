"""Plan target path validation against the repair worktree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.scope_enforcement import collect_plan_target_files
from figma_flutter_agent.errors import FigmaFlutterError

_COMPILER_PREFIX = "src/figma_flutter_agent/"
_FORBIDDEN_TARGET_MARKERS = (
    "/lib/",
    ".dart",
    "/emitter/row_emitter",
)


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def _is_valid_compiler_target(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    if not normalized.startswith(_COMPILER_PREFIX):
        return normalized.startswith("tests/")
    lowered = normalized.lower()
    return not any(marker in lowered for marker in _FORBIDDEN_TARGET_MARKERS)


def _target_exists(worktree: Path, path: str) -> bool:
    normalized = _normalize_repo_path(path)
    candidate = worktree / normalized
    return candidate.is_file()


def collect_invalid_plan_targets(plan_payload: dict[str, Any], *, worktree: Path) -> list[str]:
    """Return plan targetFiles that are missing or structurally invalid."""
    invalid: list[str] = []
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return invalid
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or "CODE_CHANGE").upper() != "CODE_CHANGE":
            continue
        for raw in item.get("targetFiles") or []:
            if not isinstance(raw, str) or not raw.strip():
                continue
            path = _normalize_repo_path(raw)
            if not _is_valid_compiler_target(path):
                invalid.append(path)
                continue
            if path.startswith(_COMPILER_PREFIX) and not _target_exists(worktree, path):
                invalid.append(path)
    return sorted(set(invalid))


def compiler_path_catalog(worktree: Path, *, limit: int = 96) -> list[str]:
    """Return existing Python compiler paths for plan/repair navigation."""
    root = worktree / "src" / "figma_flutter_agent"
    if not root.is_dir():
        return []
    patterns = (
        "generator/layout/**/*.py",
        "generator/ir/**/*.py",
        "stages/**/*.py",
        "dev/opencode/**/*.py",
    )
    paths: list[str] = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(worktree).as_posix()
            paths.append(rel)
            if len(paths) >= limit:
                return paths
    return paths


def validate_plan(plan_payload: dict[str, Any], *, worktree: Path) -> None:
    """Validate plan shape and on-disk compiler targets.

    Args:
        plan_payload: Parsed plan step JSON.
        worktree: Repair git worktree root.

    Raises:
        FigmaFlutterError: When required fields are missing or targets are invalid.
    """
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise FigmaFlutterError("plan blocked: no steps")
    for item in steps:
        if not isinstance(item, dict):
            raise FigmaFlutterError("plan step must be object")
        if not item.get("lawId"):
            raise FigmaFlutterError("plan step missing lawId")
        if not item.get("tests"):
            raise FigmaFlutterError("plan step missing tests[]")

    invalid = collect_invalid_plan_targets(plan_payload, worktree=worktree)
    if invalid:
        catalog = compiler_path_catalog(worktree, limit=12)
        catalog_hint = ", ".join(catalog[:8]) if catalog else "none"
        raise FigmaFlutterError(
            "plan blocked: targetFiles must exist under the Python agent repo "
            f"(src/figma_flutter_agent/**/*.py, tests/**/*.py). "
            f"Invalid or missing: {', '.join(invalid)}. "
            f"Examples that exist: {catalog_hint}"
        )

    if plan_payload.get("blocked"):
        raise FigmaFlutterError("plan blocked: executive JSON marked blocked=true")

    compiler_targets = {
        p
        for p in collect_plan_target_files(plan_payload)
        if p.startswith(_COMPILER_PREFIX)
    }
    if not compiler_targets:
        raise FigmaFlutterError(
            "plan blocked: CODE_CHANGE steps must name at least one "
            "src/figma_flutter_agent/**/*.py targetFile"
        )
