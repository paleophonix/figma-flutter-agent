"""Compare fresh golden captures against committed fixture baselines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import (
    ScreenFixtureEntry,
    fixtures_root,
    load_screens_manifest,
)
from figma_flutter_agent.generator.planned.reconcile import reconcile_planned_dart_files
from figma_flutter_agent.validation.compare import compare_png_bytes
from figma_flutter_agent.validation.golden_runtime import resolve_golden_runtime


@dataclass(frozen=True)
class FixtureGoldenCompareResult:
    """Outcome of comparing one fixture screen to its baseline PNG."""

    screen_id: str
    ok: bool
    skipped: bool = False
    reason: str | None = None
    changed_ratio: float | None = None


def _baseline_path(entry: ScreenFixtureEntry, *, baseline_dir: Path) -> Path:
    return baseline_dir / f"{entry.golden_id}.png"


def compare_fixture_golden(
    entry: ScreenFixtureEntry,
    *,
    settings: Settings | None = None,
    baseline_dir: Path | None = None,
    pixel_threshold: float = 0.05,
    golden_runtime: str | None = None,
    flutter_sdk: str | None = None,
) -> FixtureGoldenCompareResult:
    """Capture a screen and compare to the committed docker baseline PNG."""
    resolved_settings = settings or Settings()
    baseline_root = baseline_dir or (fixtures_root() / "golden" / "png" / "docker")
    baseline_path = _baseline_path(entry, baseline_dir=baseline_root)
    if not baseline_path.is_file():
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason=f"baseline missing: {baseline_path}",
        )

    runtime = golden_runtime
    if runtime is None:
        runtime = resolve_golden_runtime(settings=resolved_settings).runtime
    sdk = flutter_sdk if flutter_sdk is not None else resolved_settings.flutter_sdk or None

    from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png

    planned = reconcile_planned_dart_files(build_fixture_planned_files(entry))
    capture = capture_planned_flutter_golden_png(
        planned,
        feature_name=entry.feature,
        settings=resolved_settings,
        golden_runtime=runtime,
        flutter_sdk=sdk,
    )
    if not capture.ok or capture.png is None:
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=False,
            skipped=True,
            reason=capture.reason or "capture failed",
        )

    baseline = baseline_path.read_bytes()
    diff = compare_png_bytes(baseline, capture.png, threshold=pixel_threshold)
    if diff.passed:
        return FixtureGoldenCompareResult(
            screen_id=entry.id,
            ok=True,
            changed_ratio=diff.changed_ratio,
        )
    return FixtureGoldenCompareResult(
        screen_id=entry.id,
        ok=False,
        reason=f"pixel diff {diff.changed_ratio:.2%} > {pixel_threshold:.2%}",
        changed_ratio=diff.changed_ratio,
    )


def compare_all_fixture_goldens(
    *,
    screen_ids: list[str] | None = None,
    settings: Settings | None = None,
    baseline_dir: Path | None = None,
    pixel_threshold: float = 0.05,
    golden_runtime: str | None = None,
) -> list[FixtureGoldenCompareResult]:
    """Compare every manifest screen to its committed baseline."""
    manifest = load_screens_manifest()
    entries = manifest.screens
    if screen_ids is not None:
        wanted = frozenset(screen_ids)
        entries = [entry for entry in entries if entry.id in wanted]
    resolved_settings = settings or Settings()
    sdk = resolved_settings.flutter_sdk or None
    return [
        compare_fixture_golden(
            entry,
            settings=resolved_settings,
            baseline_dir=baseline_dir,
            pixel_threshold=pixel_threshold,
            golden_runtime=golden_runtime,
            flutter_sdk=sdk,
        )
        for entry in entries
    ]
