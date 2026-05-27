"""Capture Flutter golden PNGs from planned Dart files."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from ruamel.yaml import YAML

from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.generator.writer import DartWriter

_FLUTTER_SKELETON = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "flutter_skeleton"
_MAX_REASON_LEN = 160
_DART_DIAGNOSTIC_RE = re.compile(r"\.dart:\d+:\d+:\s*Error:")


@dataclass(frozen=True)
class GoldenCaptureResult:
    """Outcome of an offline golden capture attempt."""

    png: bytes | None = None
    reason: str | None = None

    @property
    def ok(self) -> bool:
        """True when golden PNG bytes were captured."""
        return self.png is not None


def golden_test_relative_path(feature_name: str) -> str:
    """Return the relative golden test path for a feature screen."""
    return f"test/golden/{feature_name}_screen_test.dart"


def golden_png_relative_path(feature_name: str) -> str:
    """Return the relative golden PNG path for a feature screen."""
    return f"test/goldens/{feature_name}_screen.png"


def _clip_reason(text: str) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= _MAX_REASON_LEN:
        return stripped
    return f"{stripped[: _MAX_REASON_LEN - 3]}..."


def _first_process_line(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    if not text:
        return "flutter test failed"
    diagnostics: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _DART_DIAGNOSTIC_RE.search(stripped):
            diagnostics.append(stripped)
    for stripped in diagnostics:
        normalized = stripped.replace("\\", "/")
        if "/lib/" in normalized or normalized.startswith("lib/"):
            return _clip_reason(stripped)
    if diagnostics:
        return _clip_reason(diagnostics[0])
    return _clip_reason(text.splitlines()[0])


def _copy_skeleton_project(target_dir: Path) -> None:
    """Copy the Flutter skeleton without stale tool artifacts."""
    shutil.copytree(
        _FLUTTER_SKELETON,
        target_dir,
        ignore=shutil.ignore_patterns(".dart_tool", "build"),
    )


def _sync_project_assets(project_dir: Path, source_project: Path) -> None:
    """Copy assets and bundled fonts from the target Flutter app for golden tests."""
    for folder in ("assets", "fonts"):
        source = source_project / folder
        if not source.is_dir():
            continue
        destination = project_dir / folder
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

    source_pubspec = source_project / "pubspec.yaml"
    target_pubspec = project_dir / "pubspec.yaml"
    if not source_pubspec.is_file() or not target_pubspec.is_file():
        return
    yaml = YAML()
    source_data = yaml.load(source_pubspec.read_text(encoding="utf-8"))
    target_data = yaml.load(target_pubspec.read_text(encoding="utf-8"))
    if not isinstance(source_data, dict) or not isinstance(target_data, dict):
        return
    source_flutter = source_data.get("flutter")
    if not isinstance(source_flutter, dict):
        return
    target_flutter = target_data.setdefault("flutter", {})
    if not isinstance(target_flutter, dict):
        return
    if source_flutter.get("fonts"):
        target_flutter["fonts"] = source_flutter["fonts"]
    if source_flutter.get("assets"):
        target_flutter["assets"] = source_flutter["assets"]
    yaml.dump(target_data, target_pubspec.open("w", encoding="utf-8"))


def _run_flutter_pub_get(project_dir: Path, flutter: str) -> GoldenCaptureResult | None:
    """Resolve packages before ``flutter test``. Returns failure or None."""
    result = subprocess.run(
        [flutter, "pub", "get"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.debug(
            "flutter pub get failed before golden capture:\n{}\n{}",
            result.stderr,
            result.stdout,
        )
        return GoldenCaptureResult(reason=_clip_reason("flutter pub get failed before golden test"))
    return None


def capture_planned_flutter_golden_png(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
) -> GoldenCaptureResult:
    """Write planned files to a skeleton app and run ``flutter test --update-goldens``.

    Args:
        planned: Relative project paths mapped to generated file contents.
        feature_name: Generated feature slug.
        flutter_sdk: Optional Flutter SDK root (``FIGMA_FLUTTER_SDK``) when not on PATH.
        project_dir: Optional Flutter app root to copy ``assets/``, ``fonts/``, and pubspec
            asset/font entries from (the real ``--project-dir`` during pipeline runs).

    Returns:
        Captured PNG bytes, or a short ``reason`` when capture cannot run.
    """
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return GoldenCaptureResult(reason="no Flutter SDK (PATH or FIGMA_FLUTTER_SDK)")

    golden_test_rel = golden_test_relative_path(feature_name)
    if golden_test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {golden_test_rel} in plan")

    if not _FLUTTER_SKELETON.is_dir():
        logger.debug("Flutter skeleton missing at {}", _FLUTTER_SKELETON)
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    with tempfile.TemporaryDirectory(prefix="figma-flutter-golden-") as tmp:
        capture_dir = Path(tmp) / "golden_capture"
        _copy_skeleton_project(capture_dir)
        if project_dir is not None and project_dir.is_dir():
            _sync_project_assets(capture_dir, project_dir)
        writer = DartWriter(capture_dir, enable_backup=False)
        writer.write_files(planned)
        pub_get_failure = _run_flutter_pub_get(capture_dir, flutter)
        if pub_get_failure is not None:
            return pub_get_failure
        golden_out = capture_dir / golden_png_relative_path(feature_name)
        result = subprocess.run(
            [flutter, "test", golden_test_rel, "--update-goldens"],
            cwd=capture_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "Golden capture failed for {}:\n{}\n{}",
                feature_name,
                result.stderr,
                result.stdout,
            )
            return GoldenCaptureResult(reason=_first_process_line(result))
        if not golden_out.is_file():
            logger.debug("Golden PNG was not written: {}", golden_out)
            return GoldenCaptureResult(reason="golden PNG not written")
        return GoldenCaptureResult(png=golden_out.read_bytes())
