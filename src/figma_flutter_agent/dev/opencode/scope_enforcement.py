"""Post-hoc edit scope enforcement for OpenCode repair and fix steps."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.dev.opencode.worktree import _git_command
from figma_flutter_agent.errors import FigmaFlutterError

_FORBIDDEN_PREFIXES = (
    "sandbox/",
    "demo_app/lib/",
    "apps/",
    ".debug/",
)

_CODE_CHANGE_KIND = "CODE_CHANGE"


@dataclass(frozen=True)
class ScopeResult:
    """Outcome of a scope validation."""

    passed: bool
    violations: tuple[str, ...]
    reason_code: str
    touched_paths: tuple[str, ...]


def _normalize_repo_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_forbidden_path(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    return any(normalized.startswith(prefix) for prefix in _FORBIDDEN_PREFIXES)


def collect_plan_target_files(plan_payload: dict) -> frozenset[str]:
    """Union plan ``targetFiles`` and ``tests`` for CODE_CHANGE steps."""
    paths: set[str] = set()
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return frozenset()
    for item in steps:
        if not isinstance(item, dict):
            continue
        action_kind = str(item.get("actionKind") or _CODE_CHANGE_KIND).upper()
        if action_kind != _CODE_CHANGE_KIND:
            continue
        for key in ("targetFiles", "tests"):
            raw = item.get(key) or []
            if isinstance(raw, list):
                for entry in raw:
                    if isinstance(entry, str) and entry.strip():
                        paths.add(_normalize_repo_path(entry.strip()))
    return frozenset(paths)


def collect_plan_gate_paths(plan_payload: dict) -> list[str]:
    """Return ruff/pytest paths derived from the repair plan."""
    targets = sorted(collect_plan_target_files(plan_payload))
    if not targets:
        return ["tests/test_debug_pipeline_models.py"]
    ruff_paths = [p for p in targets if p.startswith("src/figma_flutter_agent/")]
    pytest_paths = [p for p in targets if p.startswith("tests/")]
    if not ruff_paths:
        ruff_paths = ["src/figma_flutter_agent/dev/opencode"]
    if not pytest_paths:
        pytest_paths = ["tests/test_debug_pipeline_models.py"]
    return sorted(set(ruff_paths + pytest_paths))


def allowed_paths_for_step(
    step: str,
    *,
    worktree: Path,
    plan_payload: dict,
) -> frozenset[str]:
    """Return allowed relative repo paths for a write step."""
    if step == "fix":
        prefix = ".repair/candidate/planned_files/"
        allowed: set[str] = {prefix}
        planned_root = worktree / ".repair" / "candidate" / "planned_files"
        if planned_root.is_dir():
            for path in planned_root.rglob("*"):
                if path.is_file():
                    rel = path.relative_to(worktree).as_posix()
                    allowed.add(rel)
        return frozenset(allowed)

    if step == "repair":
        plan_paths = collect_plan_target_files(plan_payload)
        allowed = {p for p in plan_paths if not _is_forbidden_path(p)}
        for path in plan_paths:
            if path.startswith("src/figma_flutter_agent/"):
                allowed.add(path)
        if not allowed:
            allowed.add("src/figma_flutter_agent/")
        return frozenset(allowed)

    msg = f"unsupported write step for scope enforcement: {step}"
    raise ValueError(msg)


def diff_touched_paths(worktree: Path, *, baseline_ref: str = "HEAD") -> list[str]:
    """Return repo-relative paths changed since ``baseline_ref``."""
    resolved = worktree.resolve()
    result = subprocess.run(
        _git_command(resolved, "diff", "--name-only", baseline_ref),
        cwd=resolved,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise FigmaFlutterError(f"git diff failed in repair worktree: {stderr}")
    paths: list[str] = []
    for line in (result.stdout or "").splitlines():
        normalized = _normalize_repo_path(line.strip())
        if normalized:
            paths.append(normalized)
    return paths


def _path_allowed(touched: str, allowed: frozenset[str]) -> bool:
    normalized = _normalize_repo_path(touched)
    if _is_forbidden_path(normalized):
        return False
    for candidate in allowed:
        if normalized == candidate:
            return True
        if candidate.endswith("/") and normalized.startswith(candidate):
            return True
        if normalized.startswith(f"{candidate}/"):
            return True
    return False


def validate_scope(
    step: str,
    *,
    touched_paths: list[str],
    allowed_paths: frozenset[str],
) -> ScopeResult:
    """Validate touched paths against the allowed set for one write step."""
    violations: list[str] = []
    for touched in touched_paths:
        if not _path_allowed(touched, allowed_paths):
            violations.append(touched)
    return ScopeResult(
        passed=not violations,
        violations=tuple(violations),
        reason_code="SCOPE_OK" if not violations else "SCOPE_DRIFT",
        touched_paths=tuple(_normalize_repo_path(p) for p in touched_paths),
    )
