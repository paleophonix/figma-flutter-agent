"""Plan target path validation against the repair worktree."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.scope_enforcement import (
    _plan_test_path,
    collect_plan_target_files,
)
from figma_flutter_agent.errors import FigmaFlutterError

_COMPILER_PREFIX = "src/figma_flutter_agent/"
_CODE_CHANGE_KIND = "CODE_CHANGE"
_NON_COMPILER_ACTION_KINDS = frozenset({"REPORT_ONLY", "INFRA_RETRY", "HUMAN_REQUIRED"})
_FORBIDDEN_TARGET_MARKERS = (
    "/lib/",
    ".dart",
    "/emitter/row_emitter",
)


def _normalize_repo_path(path: str) -> str:
    return path.replace("\\", "/").strip().lstrip("./")


def resolve_compiler_target(worktree: Path, path: str) -> str | None:
    """Map a plan target to an on-disk compiler file when possible.

    Legacy module paths such as ``generator/ir/validate.py`` resolve to package
    ``__init__.py`` files when the flat module file was split into a directory.

    Args:
        worktree: Repair git worktree root.
        path: Plan ``targetFiles`` entry.

    Returns:
        Repo-relative POSIX path when a matching file exists, else ``None``.
    """
    normalized = _normalize_repo_path(path)
    candidate = worktree / normalized
    if candidate.is_file():
        return normalized
    if normalized.endswith(".py"):
        package_init = worktree / f"{normalized[:-3]}/__init__.py"
        if package_init.is_file():
            return package_init.relative_to(worktree).as_posix()
    return None


def _is_valid_compiler_target(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    if not normalized.startswith(_COMPILER_PREFIX):
        return normalized.startswith("tests/")
    lowered = normalized.lower()
    return not any(marker in lowered for marker in _FORBIDDEN_TARGET_MARKERS)


def _target_exists(worktree: Path, path: str) -> bool:
    return resolve_compiler_target(worktree, path) is not None


def normalize_plan_target_files(plan_payload: dict[str, Any], *, worktree: Path) -> None:
    """Rewrite CODE_CHANGE targetFiles to canonical on-disk paths in place."""
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or "CODE_CHANGE").upper() != "CODE_CHANGE":
            continue
        resolved: list[str] = []
        for raw in item.get("targetFiles") or []:
            if not isinstance(raw, str) or not raw.strip():
                continue
            canonical = resolve_compiler_target(worktree, raw)
            resolved.append(canonical if canonical is not None else _normalize_repo_path(raw))
        item["targetFiles"] = sorted(set(resolved))


def normalize_plan_test_paths(plan_payload: dict[str, Any]) -> None:
    """Rewrite CODE_CHANGE tests[] entries to canonical ``tests/**`` paths in place."""
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or _CODE_CHANGE_KIND).upper() != _CODE_CHANGE_KIND:
            continue
        raw_tests = item.get("tests")
        if not isinstance(raw_tests, list):
            continue
        normalized_entries: list[Any] = []
        for entry in raw_tests:
            canonical = _plan_test_path(entry)
            if canonical is None:
                normalized_entries.append(entry)
                continue
            if isinstance(entry, str):
                normalized_entries.append(canonical)
            elif isinstance(entry, dict):
                updated = dict(entry)
                updated["path"] = canonical
                normalized_entries.append(updated)
            else:
                normalized_entries.append(entry)
        item["tests"] = normalized_entries


def collect_invalid_plan_test_paths(plan_payload: dict[str, Any], *, worktree: Path) -> list[str]:
    """Return CODE_CHANGE test paths that are not under repo ``tests/``."""
    invalid: list[str] = []
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return invalid
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or _CODE_CHANGE_KIND).upper() != _CODE_CHANGE_KIND:
            continue
        for entry in item.get("tests") or []:
            normalized = _plan_test_path(entry)
            if normalized is None:
                if isinstance(entry, str) and entry.strip():
                    invalid.append(_normalize_repo_path(entry.strip()))
                elif isinstance(entry, dict):
                    raw = entry.get("path") or entry.get("name")
                    if isinstance(raw, str) and raw.strip():
                        invalid.append(_normalize_repo_path(raw.strip()))
    return sorted(set(invalid))


def collect_invalid_plan_targets(plan_payload: dict[str, Any], *, worktree: Path) -> list[str]:
    """Return plan targetFiles that are missing or structurally invalid."""
    invalid: list[str] = []
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return invalid
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or _CODE_CHANGE_KIND).upper() != _CODE_CHANGE_KIND:
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


_CATALOG_PATTERN_BUDGETS: tuple[tuple[str, int], ...] = (
    ("generator/layout/**/*.py", 32),
    ("generator/ir/**/*.py", 32),
    ("stages/**/*.py", 16),
    ("dev/opencode/**/*.py", 16),
)


def _catalog_paths_for_pattern(
    root: Path,
    worktree: Path,
    pattern: str,
    budget: int,
) -> list[str]:
    """Collect paths with round-robin across immediate parent folders."""
    grouped: dict[str, list[Path]] = {}
    for path in sorted(root.glob(pattern)):
        if path.is_file():
            parent = path.parent.relative_to(root).as_posix()
            grouped.setdefault(parent, []).append(path)
    parents = sorted(grouped)
    paths: list[str] = []
    round_index = 0
    while len(paths) < budget and parents:
        progressed = False
        for parent in parents:
            bucket = grouped[parent]
            if round_index >= len(bucket):
                continue
            rel = bucket[round_index].relative_to(worktree).as_posix()
            if rel not in paths:
                paths.append(rel)
                progressed = True
            if len(paths) >= budget:
                break
        if not progressed:
            break
        round_index += 1
    return paths


def compiler_path_catalog(worktree: Path, *, limit: int = 96) -> list[str]:
    """Return existing Python compiler paths for plan/repair navigation."""
    root = worktree / "src" / "figma_flutter_agent"
    if not root.is_dir():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for pattern, budget in _CATALOG_PATTERN_BUDGETS:
        for rel in _catalog_paths_for_pattern(root, worktree, pattern, budget):
            if rel in seen:
                continue
            seen.add(rel)
            paths.append(rel)
            if len(paths) >= limit:
                return paths[:limit]
    return paths[:limit]


def is_executive_blocked_plan(plan_payload: dict[str, Any]) -> bool:
    """Return True when plan is a terminal blocked executive response."""
    if not plan_payload.get("blocked"):
        return False
    blocked_items = plan_payload.get("blockedItems")
    if isinstance(blocked_items, list) and blocked_items:
        return True
    return bool(str(plan_payload.get("notes") or "").strip())


def _validate_blocked_plan_items(plan_payload: dict[str, Any]) -> None:
    blocked_items = plan_payload.get("blockedItems")
    if not isinstance(blocked_items, list) or not blocked_items:
        return
    for index, item in enumerate(blocked_items):
        if not isinstance(item, dict):
            raise FigmaFlutterError(f"plan blockedItems[{index}] must be object")
        if not item.get("lawId"):
            raise FigmaFlutterError("plan blocked item missing lawId")
        if not str(item.get("reason") or "").strip():
            raise FigmaFlutterError("plan blocked item missing reason")


def validate_plan(plan_payload: dict[str, Any], *, worktree: Path) -> None:
    """Validate plan shape and on-disk compiler targets.

    Args:
        plan_payload: Parsed plan step JSON.
        worktree: Repair git worktree root.

    Raises:
        FigmaFlutterError: When required fields are missing or targets are invalid.
    """
    normalize_plan_target_files(plan_payload, worktree=worktree)
    normalize_plan_test_paths(plan_payload)
    if is_executive_blocked_plan(plan_payload):
        _validate_blocked_plan_items(plan_payload)
        return
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise FigmaFlutterError("plan blocked: no steps")
    for item in steps:
        if not isinstance(item, dict):
            raise FigmaFlutterError("plan step must be object")
        if not item.get("lawId"):
            raise FigmaFlutterError("plan step missing lawId")
        action_kind = str(item.get("actionKind") or _CODE_CHANGE_KIND).upper()
        if action_kind == _CODE_CHANGE_KIND and not item.get("tests"):
            raise FigmaFlutterError("plan step missing tests[]")
        if action_kind in _NON_COMPILER_ACTION_KINDS and item.get("targetFiles"):
            raise FigmaFlutterError(
                f"plan step {action_kind} must not name compiler targetFiles"
            )

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

    invalid_tests = collect_invalid_plan_test_paths(plan_payload, worktree=worktree)
    if invalid_tests:
        raise FigmaFlutterError(
            "plan blocked: CODE_CHANGE tests[] must name tests/**/*.py paths. "
            f"Invalid: {', '.join(invalid_tests)}"
        )

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
