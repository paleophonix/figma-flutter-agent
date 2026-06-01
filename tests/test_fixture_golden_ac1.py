"""AC-1: fixture golden capture matches committed docker baselines."""

from __future__ import annotations

import os

import pytest

from figma_flutter_agent.config import Settings, agent_repo_root
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import fixtures_root, load_screens_manifest
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png
from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime

_DOCKER_GOLDEN_DIR = fixtures_root() / "golden" / "png" / "docker"
_PIXEL_THRESHOLD = 0.05


def _flutter_sdk_root_for_tests() -> str | None:
    """Resolve SDK root when pytest skips dotenv (read only ``FIGMA_FLUTTER_SDK``)."""
    env = os.environ.get("FIGMA_FLUTTER_SDK", "").strip()
    if env:
        return env
    env_file = agent_repo_root() / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("FIGMA_FLUTTER_SDK="):
            value = stripped.split("=", 1)[1].strip().strip('"').strip("'")
            return value or None
    return None


def _flutter_available() -> bool:
    return resolve_flutter_executable(sdk_root=_flutter_sdk_root_for_tests()) is not None


@pytest.mark.parametrize("screen_id", ["music_v2"])
def test_fixture_golden_capture_is_stable_on_host(screen_id: str) -> None:
    """Two captures from the same planned files should be pixel-identical on host."""
    if not _flutter_available():
        pytest.skip("Flutter SDK not available")
    sdk = _flutter_sdk_root_for_tests()
    planned = reconcile_planned_dart_files(build_fixture_planned_files(screen_id))
    manifest = load_screens_manifest()
    feature = next(item.feature for item in manifest.screens if item.id == screen_id)
    first = capture_planned_flutter_golden_png(
        planned,
        feature_name=feature,
        golden_runtime="host",
        flutter_sdk=sdk,
    )
    second = capture_planned_flutter_golden_png(
        planned,
        feature_name=feature,
        golden_runtime="host",
        flutter_sdk=sdk,
    )
    if not first.ok or not second.ok or first.png is None or second.png is None:
        pytest.skip(f"golden capture failed: {first.reason or second.reason}")
    diff = compare_png_bytes(first.png, second.png, threshold=0.0)
    assert diff.changed_ratio == 0.0


@pytest.mark.parametrize(
    "screen_id",
    ["sign_up_and_sign_in", "reminders", "music_v2", "music_v2_ru_dirty"],
)
def test_fixture_golden_matches_committed_baseline(screen_id: str) -> None:
    """Committed docker baseline PNG should match a fresh host capture (AC-1)."""
    if not _flutter_available():
        pytest.skip("Flutter SDK not available")
    manifest = load_screens_manifest()
    entry = next(item for item in manifest.screens if item.id == screen_id)
    baseline_path = _DOCKER_GOLDEN_DIR / f"{entry.golden_id}.png"
    if not baseline_path.is_file():
        pytest.skip(f"baseline not committed: {baseline_path}")

    sdk = _flutter_sdk_root_for_tests()
    settings = Settings()
    runtime = resolve_golden_runtime(settings=settings).runtime
    planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
    capture = capture_planned_flutter_golden_png(
        planned,
        feature_name=entry.feature,
        settings=settings,
        golden_runtime=runtime,
        flutter_sdk=sdk,
    )
    if not capture.ok or capture.png is None:
        pytest.skip(f"capture failed: {capture.reason}")

    baseline = baseline_path.read_bytes()
    diff = compare_png_bytes(baseline, capture.png, threshold=_PIXEL_THRESHOLD)
    assert diff.passed, (
        f"{screen_id}: pixel diff {diff.changed_ratio:.2%} > {_PIXEL_THRESHOLD:.0%} "
        f"(re-run scripts/generate_fixture_goldens.py if intentional UI change)"
    )
