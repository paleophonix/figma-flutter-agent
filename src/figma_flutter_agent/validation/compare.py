"""Visual QA comparison orchestration."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from figma_flutter_agent.validation.pixeldiff import PixelDiffResult, compare_png_files
from figma_flutter_agent.validation.reference import REFERENCE_DIR_NAME
from figma_flutter_agent.validation.specimens import FontValidationSpecimen, load_font_specimens


@dataclass(frozen=True)
class VisualQaComparison:
    """One named PNG comparison result."""

    name: str
    result: PixelDiffResult
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class VisualQaReport:
    """Aggregated visual QA comparison report."""

    comparisons: list[VisualQaComparison] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True when every non-skipped comparison passed."""
        return all(item.skipped or item.result.passed for item in self.comparisons)

    @property
    def failures(self) -> list[VisualQaComparison]:
        """Return comparisons that failed the pixel threshold."""
        return [item for item in self.comparisons if not item.skipped and not item.result.passed]


def _read_reference_scale(metadata_path: Path) -> float:
    if not metadata_path.is_file():
        return 1.0
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    scale = payload.get("scale", 1.0)
    return float(scale) if isinstance(scale, (int, float)) else 1.0


def compare_png_bytes(
    reference_png: bytes,
    actual_png: bytes,
    *,
    threshold: float = 0.05,
) -> PixelDiffResult:
    """Compare two in-memory PNG payloads.

    Args:
        reference_png: Baseline PNG bytes (for example Figma export).
        actual_png: Candidate PNG bytes (for example Flutter golden).
        threshold: Maximum changed-pixel ratio.

    Returns:
        ``PixelDiffResult`` with pass/fail via ``passed``.
    """
    with tempfile.TemporaryDirectory(prefix="figma-flutter-pixeldiff-") as tmp:
        reference_path = Path(tmp) / "reference.png"
        actual_path = Path(tmp) / "actual.png"
        reference_path.write_bytes(reference_png)
        actual_path.write_bytes(actual_png)
        return compare_png_files(
            reference_path.as_posix(),
            actual_path.as_posix(),
            threshold=threshold,
            resize_reference=True,
        )


def compare_screen_golden(
    project_dir: Path,
    feature_name: str,
    *,
    threshold: float = 0.05,
) -> VisualQaComparison | None:
    """Compare Figma reference PNG against the Flutter screen golden.

    Args:
        project_dir: Flutter project root.
        feature_name: Generated feature slug.
        threshold: Maximum changed-pixel ratio.

    Returns:
        Comparison result, or ``None`` when required files are missing.
    """
    reference_png = project_dir / REFERENCE_DIR_NAME / f"{feature_name}_figma.png"
    golden_png = project_dir / "test" / "goldens" / f"{feature_name}_screen.png"
    if not reference_png.is_file():
        logger.warning("Figma reference PNG missing: {}", reference_png)
        return None
    if not golden_png.is_file():
        logger.warning(
            "Flutter golden PNG missing: {} (run flutter test --update-goldens)", golden_png
        )
        return None

    metadata_path = project_dir / REFERENCE_DIR_NAME / f"{feature_name}_figma.json"
    scale = _read_reference_scale(metadata_path)
    result = compare_png_files(
        reference_png.as_posix(),
        golden_png.as_posix(),
        threshold=threshold,
        resize_reference=True,
    )
    logger.info(
        "Screen pixel diff {}: {:.2%} changed (scale={})",
        "PASS" if result.passed else "FAIL",
        result.changed_ratio,
        scale,
    )
    return VisualQaComparison(name=f"{feature_name}_screen", result=result)


def compare_typography_specimen(
    project_dir: Path,
    specimen: FontValidationSpecimen,
    *,
    default_threshold: float = 0.05,
) -> VisualQaComparison:
    """Compare optional Figma/Flutter specimen PNG pair when both exist."""
    reference_png = project_dir / REFERENCE_DIR_NAME / "specimens" / f"{specimen.id}.png"
    golden_png = project_dir / "test" / "goldens" / f"{specimen.id}.png"
    threshold = specimen.max_changed_pixel_ratio or default_threshold

    if not golden_png.is_file():
        return VisualQaComparison(
            name=specimen.id,
            result=_placeholder_result(golden_png, threshold),
            skipped=True,
            skip_reason=f"Flutter golden missing: {golden_png.as_posix()}",
        )
    if not reference_png.is_file():
        return VisualQaComparison(
            name=specimen.id,
            result=_placeholder_result(golden_png, threshold),
            skipped=True,
            skip_reason=f"Figma specimen reference missing: {reference_png.as_posix()}",
        )

    result = compare_png_files(
        reference_png.as_posix(),
        golden_png.as_posix(),
        threshold=threshold,
        resize_reference=True,
    )
    return VisualQaComparison(name=specimen.id, result=result)


def _placeholder_result(path: Path, threshold: float) -> PixelDiffResult:
    return PixelDiffResult(
        reference_path="",
        actual_path=path.as_posix(),
        width=0,
        height=0,
        changed_pixels=0,
        total_pixels=0,
        changed_ratio=0.0,
        threshold=threshold,
    )


def run_visual_qa(
    project_dir: Path,
    feature_name: str,
    *,
    threshold: float = 0.05,
    include_specimens: bool = True,
) -> VisualQaReport:
    """Run all configured visual QA comparisons for a project feature.

    Args:
        project_dir: Flutter project root.
        feature_name: Generated feature slug.
        threshold: Screen-level changed-pixel threshold.
        include_specimens: When True, include Table E typography specimen checks.

    Returns:
        Aggregated ``VisualQaReport``.
    """
    report = VisualQaReport()
    screen = compare_screen_golden(project_dir, feature_name, threshold=threshold)
    if screen is not None:
        report.comparisons.append(screen)

    if include_specimens:
        registry = load_font_specimens()
        for specimen in registry.specimens:
            report.comparisons.append(
                compare_typography_specimen(project_dir, specimen, default_threshold=threshold)
            )
    return report
