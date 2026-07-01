"""Post-hoc edit scope enforcement for OpenCode repair and fix steps."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from figma_flutter_agent.dev.opencode.worktree import _git_command
from figma_flutter_agent.errors import FigmaFlutterError

_FORBIDDEN_PREFIXES = (
    "sandbox/",
    "demo_app/lib/",
    "apps/",
    ".debug/",
)

_CODE_CHANGE_KIND = "CODE_CHANGE"
_HALLUCINATED_TEST_PREFIX = "src/figma_flutter_agent/tests/"
_TOUCH_BASELINE_JSON = "touch_baseline.json"


def _repair_agent_snapshot(worktree: Path) -> dict[str, str]:
    """Hash ``.repair/state`` and ``.repair/candidate`` for scope drift visibility."""
    snapshot: dict[str, str] = {}
    for rel_root in (".repair/state", ".repair/candidate"):
        root = worktree / rel_root
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(worktree).as_posix()
            if rel.endswith("touch_baseline.json"):
                continue
            snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _touch_state_snapshot(worktree: Path) -> dict[str, str]:
    """Return repo-relative paths to content hashes for currently touched files."""
    snapshot: dict[str, str] = {}
    for rel in diff_touched_paths(worktree):
        if rel.endswith("touch_baseline.json"):
            continue
        path = worktree / rel
        if path.is_file():
            snapshot[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshot.update(_repair_agent_snapshot(worktree))
    return snapshot


def capture_worktree_touch_baseline(worktree: Path, state_dir: Path) -> Path:
    """Persist current touched file content hashes before a write step.

    Args:
        worktree: Repair git worktree root.
        state_dir: ``.repair/state`` directory.

    Returns:
        Path to the written baseline JSON file.
    """
    baseline_path = state_dir / _TOUCH_BASELINE_JSON
    state_dir.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(
        json.dumps(_touch_state_snapshot(worktree), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return baseline_path


def diff_touched_since_baseline(worktree: Path, baseline_path: Path) -> list[str]:
    """Return repo-relative paths whose content changed since the baseline snapshot.

    Args:
        worktree: Repair git worktree root.
        baseline_path: Baseline JSON from ``capture_worktree_touch_baseline``.

    Returns:
        Sorted paths with new or changed content since baseline.
    """
    if not baseline_path.is_file():
        return diff_touched_paths(worktree)
    loaded = json.loads(baseline_path.read_text(encoding="utf-8"))
    after = _touch_state_snapshot(worktree)
    if isinstance(loaded, list):
        before_paths = {str(path) for path in loaded}
        return sorted(path for path, digest in after.items() if path not in before_paths)
    if not isinstance(loaded, dict):
        return sorted(after)
    before = {str(key): str(value) for key, value in loaded.items()}
    all_paths = set(before) | set(after)
    return sorted(path for path in all_paths if before.get(path) != after.get(path))


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


def _canonical_tests_repo_path(path: str) -> str | None:
    """Map plan test paths to repo-relative ``tests/**`` paths when possible."""
    normalized = _normalize_repo_path(path)
    if normalized.startswith("tests/"):
        return normalized
    if normalized.startswith(_HALLUCINATED_TEST_PREFIX):
        return "tests/" + normalized[len(_HALLUCINATED_TEST_PREFIX) :]
    return None


def _plan_test_path(entry: object) -> str | None:
    """Normalize a plan tests[] entry to a repo-relative tests/ path."""
    if isinstance(entry, str) and entry.strip():
        return _canonical_tests_repo_path(entry.strip())
    if isinstance(entry, dict):
        for key in ("path", "name", "testFile"):
            raw = entry.get(key)
            if isinstance(raw, str) and raw.strip():
                canonical = _canonical_tests_repo_path(raw.strip())
                if canonical is not None:
                    return canonical
    return None


def plan_declares_broad_test_scope(plan_payload: dict) -> bool:
    """Return True when the plan explicitly allows editing all of ``tests/``."""
    if str(plan_payload.get("regressionScope") or "").lower() == "module":
        return True
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return False
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or _CODE_CHANGE_KIND).upper() != _CODE_CHANGE_KIND:
            continue
        if item.get("broadTestScope") is True:
            return True
    return False


def plan_declares_code_change_tests(plan_payload: dict) -> bool:
    """Return True when repair scope may include regression tests beyond explicit paths."""
    if plan_declares_broad_test_scope(plan_payload):
        return True
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return False
    for item in steps:
        if not isinstance(item, dict):
            continue
        if str(item.get("actionKind") or _CODE_CHANGE_KIND).upper() != _CODE_CHANGE_KIND:
            continue
        raw_tests = item.get("tests") or []
        if isinstance(raw_tests, list) and raw_tests:
            return True
    return False


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
        raw_targets = item.get("targetFiles") or []
        if isinstance(raw_targets, list):
            for entry in raw_targets:
                if isinstance(entry, str) and entry.strip():
                    paths.add(_normalize_repo_path(entry.strip()))
        raw_tests = item.get("tests") or []
        if isinstance(raw_tests, list):
            for entry in raw_tests:
                test_path = _plan_test_path(entry)
                if test_path is not None:
                    paths.add(test_path)
    return frozenset(paths)


def plan_has_actionable_compiler_targets(plan_payload: dict[str, Any]) -> bool:
    """Return whether the plan names at least one compiler ``src/`` CODE_CHANGE target."""
    targets = collect_plan_target_files(plan_payload)
    return any(path.startswith("src/figma_flutter_agent/") for path in targets)


def collect_plan_target_files_for_orders(
    plan_payload: dict,
    plan_step_orders: list[int],
) -> frozenset[str]:
    """Union targetFiles/tests for assigned CODE_CHANGE plan steps only."""
    allowed_orders = {int(order) for order in plan_step_orders}
    paths: set[str] = set()
    steps = plan_payload.get("steps") or []
    if not isinstance(steps, list):
        return frozenset()
    for item in steps:
        if not isinstance(item, dict):
            continue
        order = item.get("order")
        if allowed_orders and order not in allowed_orders:
            continue
        action_kind = str(item.get("actionKind") or _CODE_CHANGE_KIND).upper()
        if action_kind != _CODE_CHANGE_KIND:
            continue
        for entry in item.get("targetFiles") or []:
            if isinstance(entry, str) and entry.strip():
                paths.add(_normalize_repo_path(entry.strip()))
        for entry in item.get("tests") or []:
            test_path = _plan_test_path(entry)
            if test_path is not None:
                paths.add(test_path)
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


def collect_repair_gate_paths(
    plan_payload: dict,
    *,
    worktree: Path,
    git_touched: list[str] | None = None,
) -> list[str]:
    """Return gate paths from the plan unioned with on-disk repair edits.

    Plan-declared ``tests/**`` entries that are missing on disk are omitted so
    gates run against files the repair agent actually created instead of
    hallucinated paths from the plan step.
    """
    paths: set[str] = set(collect_plan_gate_paths(plan_payload))
    for raw in git_touched or []:
        normalized = _normalize_repo_path(raw)
        if normalized.startswith("tests/") or normalized.startswith("src/figma_flutter_agent/"):
            paths.add(normalized)
    pruned: set[str] = set()
    plan_pytest = sorted(
        path for path in collect_plan_target_files(plan_payload) if path.startswith("tests/")
    )
    for path in paths:
        if path.startswith("tests/") and path not in plan_pytest:
            if not (worktree / path).is_file():
                continue
        pruned.add(path)
    for path in plan_pytest:
        if (worktree / path).is_file():
            pruned.add(path)
    if not pruned:
        return collect_plan_gate_paths(plan_payload)
    ruff_paths = [p for p in pruned if p.startswith("src/figma_flutter_agent/")]
    pytest_paths = [p for p in pruned if p.startswith("tests/") and (worktree / p).is_file()]
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
        for path in plan_paths:
            if path.startswith("tests/"):
                allowed.add(path)
        if plan_declares_broad_test_scope(plan_payload):
            allowed.add("tests/")
        if not allowed:
            allowed.add("src/figma_flutter_agent/")
        return frozenset(allowed)

    msg = f"unsupported write step for scope enforcement: {step}"
    raise ValueError(msg)


def _git_diff_paths(worktree: Path, *, baseline_ref: str = "HEAD") -> list[str]:
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


def _git_status_paths(worktree: Path) -> list[str]:
    """Return repo-relative paths from porcelain status (includes untracked)."""
    resolved = worktree.resolve()
    result = subprocess.run(
        _git_command(
            resolved,
            "status",
            "--porcelain",
            "--untracked-files=all",
        ),
        cwd=resolved,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise FigmaFlutterError(f"git status failed in repair worktree: {stderr}")
    paths: list[str] = []
    for line in (result.stdout or "").splitlines():
        if len(line) < 4:
            continue
        raw = line[3:].strip()
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1].strip()
        normalized = _normalize_repo_path(raw)
        if normalized:
            paths.append(normalized)
    return paths


def paths_from_opencode_session_diff(entries: list[dict[str, Any]]) -> list[str]:
    """Extract repo-relative paths from OpenCode session diff payloads."""
    paths: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        candidate: str | None = None
        for key in ("path", "file", "filename", "relativePath", "relative_path"):
            raw = entry.get(key)
            if isinstance(raw, str) and raw.strip():
                candidate = raw.strip()
                break
        if candidate is None:
            continue
        normalized = _normalize_repo_path(candidate)
        if normalized:
            paths.append(normalized)
    return paths


def merge_touched_paths(
    worktree: Path,
    *,
    session_diff_entries: list[dict[str, Any]] | None = None,
    baseline_ref: str = "HEAD",
) -> list[str]:
    """Union git diff/status paths with OpenCode session diff paths."""
    merged = set(diff_touched_paths(worktree, baseline_ref=baseline_ref))
    if session_diff_entries:
        merged.update(paths_from_opencode_session_diff(session_diff_entries))
    return sorted(merged)


def diff_touched_paths(worktree: Path, *, baseline_ref: str = "HEAD") -> list[str]:
    """Return repo-relative paths changed since ``baseline_ref`` (tracked + untracked)."""
    merged = set(_git_diff_paths(worktree, baseline_ref=baseline_ref))
    merged.update(_git_status_paths(worktree))
    return sorted(merged)


def snapshot_tree_hashes(root: Path) -> dict[str, str]:
    """Hash every file under ``root`` keyed by posix path relative to ``root``."""
    if not root.is_dir():
        return {}
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[rel] = digest
    return hashes


def diff_snapshot(
    before: dict[str, str],
    after: dict[str, str],
    *,
    prefix: str,
) -> list[str]:
    """Return worktree-relative paths added, modified, or deleted under ``prefix``."""
    normalized_prefix = _normalize_repo_path(prefix).rstrip("/")
    touched: set[str] = set()
    all_keys = set(before) | set(after)
    for rel in all_keys:
        worktree_rel = f"{normalized_prefix}/{rel}" if normalized_prefix else rel
        if before.get(rel) != after.get(rel):
            touched.add(worktree_rel)
    return sorted(touched)


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


def revert_scope_violation_paths(
    worktree: Path, violations: list[str] | tuple[str, ...]
) -> list[str]:
    """Restore out-of-scope paths to HEAD in a repair worktree.

    Args:
        worktree: Repair git worktree root.
        violations: Repo-relative paths reported by ``validate_scope``.

    Returns:
        Paths successfully reverted.
    """
    reverted: list[str] = []
    resolved = worktree.resolve()
    for raw in violations:
        normalized = _normalize_repo_path(raw)
        if not normalized:
            continue
        target = resolved / normalized
        if not target.is_file() and not target.exists():
            continue
        result = subprocess.run(
            _git_command(resolved, "checkout", "HEAD", "--", normalized),
            cwd=resolved,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            reverted.append(normalized)
    return reverted


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
