"""Capture Flutter golden PNGs from planned Dart files."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from ruamel.yaml import YAML

from figma_flutter_agent.config import Settings
from figma_flutter_agent.dev.flutter_sdk import resolve_flutter_executable
from figma_flutter_agent.dev.golden_capture_build import (
    ensure_golden_capture_image,
    golden_docker_auto_build_enabled,
)
from figma_flutter_agent.fixtures.assets import iter_vector_asset_keys, sync_fixture_vector_assets
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.render_log import record_render_png
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.process_run import (
    DOCKER_COMPOSE_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    FLUTTER_TEST_TIMEOUT_SEC,
    run_subprocess,
)
from figma_flutter_agent.validation.golden_runtime import (
    GoldenCaptureMode,
    golden_compose_file,
    resolve_golden_runtime,
)

_FLUTTER_SKELETON = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "flutter_skeleton"
_MAX_REASON_LEN = 160
_DART_DIAGNOSTIC_RE = re.compile(r"\.dart:\d+:\d+:\s*Error:")
_PLANNED_ASSET_PATH_RE = re.compile(r"""['"](assets/[^'"]+)['"]""")
_SKIP_LINE_PREFIXES = (
    "Resolving dependencies",
    "Downloading packages",
    "Got dependencies",
    "Syncing files",
    'Running "flutter pub get"',
    "Running flutter pub get",
)
_HIGH_SIGNAL_LINE_PATTERNS = (
    re.compile(r"A Stack requires bounded constraints"),
    re.compile(r"RenderFlex overflowed"),
    re.compile(r"Bad state:"),
    re.compile(r"Test failed"),
    re.compile(r"EXCEPTION CAUGHT BY"),
    re.compile(r"Multiple exceptions"),
    _DART_DIAGNOSTIC_RE,
)


@dataclass(frozen=True)
class GoldenCaptureResult:
    """Outcome of an offline golden capture attempt."""

    png: bytes | None = None
    reason: str | None = None
    figma_key_rects: dict[str, Any] | None = None

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


def golden_figma_keys_relative_path(feature_name: str) -> str:
    """Return the relative JSON path for runtime ``figma-*`` widget bounds."""
    return f"test/goldens/{feature_name}_figma_keys.json"


def collect_planned_asset_paths(
    planned: Mapping[str, str],
    layout_tree: CleanDesignTreeNode | None = None,
) -> set[str]:
    """Collect asset paths referenced by planned Dart and the layout tree."""
    paths: set[str] = set()
    for content in planned.values():
        for match in _PLANNED_ASSET_PATH_RE.finditer(content):
            paths.add(match.group(1).replace("\\", "/"))
    if layout_tree is not None:
        paths.update(iter_vector_asset_keys(layout_tree))
    return paths


def _read_figma_key_rects(capture_dir: Path, feature_name: str) -> dict[str, Any] | None:
    keys_path = capture_dir / golden_figma_keys_relative_path(feature_name)
    if not keys_path.is_file():
        return None
    payload = json.loads(keys_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    return payload


def _clip_reason(text: str) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= _MAX_REASON_LEN:
        return stripped
    return f"{stripped[: _MAX_REASON_LEN - 3]}..."


def _log_process_output(result: subprocess.CompletedProcess[str], *, level: str = "debug") -> None:
    combined = "\n".join(
        part for part in (result.stdout or "", result.stderr or "") if part.strip()
    ).strip()
    if not combined:
        return
    tail = combined[-4000:]
    if level == "warning":
        logger.warning("Golden capture subprocess output (tail):\n{}", tail)
    else:
        logger.debug("Golden capture subprocess output (tail):\n{}", tail)


def _first_process_line(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    if not text:
        return "flutter test failed"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for stripped in reversed(lines):
        if any(pattern.search(stripped) for pattern in _HIGH_SIGNAL_LINE_PATTERNS):
            normalized = stripped.replace("\\", "/")
            if _DART_DIAGNOSTIC_RE.search(stripped) and (
                "/lib/" in normalized or normalized.startswith("lib/")
            ):
                return _clip_reason(stripped)
            if not _DART_DIAGNOSTIC_RE.search(stripped):
                return _clip_reason(stripped)
    diagnostics: list[str] = []
    for stripped in lines:
        if _DART_DIAGNOSTIC_RE.search(stripped):
            diagnostics.append(stripped)
    for stripped in diagnostics:
        normalized = stripped.replace("\\", "/")
        if "/lib/" in normalized or normalized.startswith("lib/"):
            return _clip_reason(stripped)
    if diagnostics:
        return _clip_reason(diagnostics[0])
    for stripped in reversed(lines):
        if any(stripped.startswith(prefix) for prefix in _SKIP_LINE_PREFIXES):
            continue
        return _clip_reason(stripped)
    return _clip_reason(lines[0] if lines else "flutter test failed")


def _copy_skeleton_project(target_dir: Path) -> None:
    """Copy the Flutter skeleton without stale tool artifacts."""
    shutil.copytree(
        _FLUTTER_SKELETON,
        target_dir,
        ignore=shutil.ignore_patterns(".dart_tool", "build"),
    )


def _sync_fonts_folder(project_dir: Path, source_project: Path) -> None:
    """Copy bundled fonts required by generated ``pubspec.yaml`` font entries."""
    source = source_project / "assets" / "fonts"
    if not source.is_dir():
        legacy = source_project / "fonts"
        if legacy.is_dir():
            source = legacy
        else:
            return
    destination = project_dir / "assets" / "fonts"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def _merge_pubspec_fonts_and_assets(project_dir: Path, source_project: Path) -> None:
    """Merge ``flutter: fonts/assets`` from the target app into the capture ``pubspec.yaml``."""
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
        from figma_flutter_agent.generator.pubspec import _filter_font_families_on_disk
        from figma_flutter_agent.schemas import FontPubspecAsset, FontPubspecFamily

        merged_families: list[FontPubspecFamily] = []
        for entry in source_flutter["fonts"]:
            if not isinstance(entry, dict):
                continue
            family_name = entry.get("family")
            font_rows = entry.get("fonts")
            if not isinstance(family_name, str) or not isinstance(font_rows, list):
                continue
            fonts = []
            for row in font_rows:
                if not isinstance(row, dict):
                    continue
                asset = row.get("asset")
                weight = row.get("weight")
                if not isinstance(asset, str) or not isinstance(weight, int):
                    continue
                style = row.get("style")
                fonts.append(
                    FontPubspecAsset(
                        asset=asset,
                        weight=weight,
                        style=style if isinstance(style, str) else None,
                    )
                )
            if fonts:
                merged_families.append(FontPubspecFamily(family=family_name, fonts=fonts))
        kept = _filter_font_families_on_disk(source_project, merged_families)
        if kept:
            target_flutter["fonts"] = [
                {
                    "family": family.family,
                    "fonts": [
                        {
                            "asset": font.asset,
                            "weight": font.weight,
                            **({"style": font.style} if font.style else {}),
                        }
                        for font in family.fonts
                    ],
                }
                for family in kept
            ]
        else:
            target_flutter.pop("fonts", None)
    yaml.dump(target_data, target_pubspec.open("w", encoding="utf-8"))


def _sync_referenced_assets(
    project_dir: Path,
    source_project: Path,
    asset_paths: set[str],
) -> None:
    """Copy only assets referenced by the planned screen (not the whole ``assets/`` tree)."""
    for asset_key in sorted(asset_paths):
        normalized = asset_key.replace("\\", "/")
        if not normalized.startswith("assets/"):
            continue
        source = source_project / Path(normalized)
        if not source.is_file():
            continue
        destination = project_dir / Path(normalized)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _sync_project_assets(
    project_dir: Path,
    source_project: Path,
    *,
    planned: Mapping[str, str] | None = None,
    layout_tree: CleanDesignTreeNode | None = None,
) -> None:
    """Copy fonts and only the asset files needed for golden capture."""
    _sync_fonts_folder(project_dir, source_project)
    _merge_pubspec_fonts_and_assets(project_dir, source_project)
    if planned is None:
        return
    asset_paths = collect_planned_asset_paths(planned, layout_tree)
    _sync_referenced_assets(project_dir, source_project, asset_paths)


def _prepare_flutter_test_build_dir(project_dir: Path) -> None:
    """Reset ``build/unit_test_assets`` so ``flutter test`` can bundle assets on Windows hosts."""
    assets_dir = project_dir / "build" / "unit_test_assets"
    if assets_dir.exists():
        try:
            shutil.rmtree(assets_dir)
        except OSError as exc:
            logger.warning("Could not remove {} before golden test: {}", assets_dir, exc)
    try:
        assets_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Could not prepare {}: {}", assets_dir, exc)


def _run_flutter_pub_get(project_dir: Path, flutter: str) -> GoldenCaptureResult | None:
    """Resolve packages before ``flutter test``. Returns failure or None."""
    try:
        result = run_subprocess(
            [flutter, "pub", "get"],
            cwd=project_dir,
            label="flutter pub get (golden)",
            timeout_sec=FLUTTER_PUB_GET_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter pub get timed out after {FLUTTER_PUB_GET_TIMEOUT_SEC:.0f}s"
            ),
        )
    if result.returncode != 0:
        _log_process_output(result, level="warning")
        return GoldenCaptureResult(reason=_clip_reason("flutter pub get failed before golden test"))
    return None


def _run_golden_flutter_test(
    flutter: str,
    capture_dir: Path,
    golden_test_rel: str,
) -> subprocess.CompletedProcess[str] | GoldenCaptureResult:
    """Run a single golden widget test with bounded timeout."""
    try:
        return run_subprocess(
            [
                flutter,
                "test",
                golden_test_rel,
                "--update-goldens",
                "--no-pub",
                "--reporter",
                "compact",
                "--timeout",
                "2m",
            ],
            cwd=capture_dir,
            label="flutter test --update-goldens",
            timeout_sec=FLUTTER_TEST_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter test timed out after {FLUTTER_TEST_TIMEOUT_SEC:.0f}s"
            ),
        )


def _prepare_capture_workspace(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path | None,
    layout_tree: CleanDesignTreeNode | None,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None, bool]:
    """Return an isolated capture root so host ``flutter test`` does not touch a live app tree."""
    tmp = tempfile.TemporaryDirectory(prefix="figma-flutter-golden-")
    capture_dir = Path(tmp.name) / "golden_capture"
    _copy_skeleton_project(capture_dir)
    if project_dir is not None and project_dir.is_dir():
        _sync_project_assets(
            capture_dir,
            project_dir,
            planned=planned,
            layout_tree=layout_tree,
        )
    elif layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree)
    return capture_dir, tmp, False


def _write_planned_capture_files(
    capture_dir: Path,
    planned: dict[str, str],
    *,
    enable_backup: bool,
    layout_tree: CleanDesignTreeNode | None,
    project_dir: Path | None,
) -> None:
    """Write planned Dart into the capture workspace and ensure assets exist."""
    writer = DartWriter(capture_dir, enable_backup=enable_backup)
    writer.write_files(planned)
    if layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree)
    if project_dir is not None and project_dir.is_dir() and capture_dir.resolve() != project_dir.resolve():
        _sync_project_assets(
            capture_dir,
            project_dir,
            planned=planned,
            layout_tree=layout_tree,
        )


def capture_planned_flutter_golden_png_docker(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path | None = None,
    update_goldens: bool = True,
    layout_tree: CleanDesignTreeNode | None = None,
) -> GoldenCaptureResult:
    """Capture golden PNG inside the ``docker/render-capture`` compose service."""
    compose = golden_compose_file()
    if not compose.is_file():
        return GoldenCaptureResult(reason="docker compose file missing")

    docker = shutil.which("docker")
    if docker is None:
        return GoldenCaptureResult(reason="docker CLI not found")

    golden_test_rel = golden_test_relative_path(feature_name)
    if golden_test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {golden_test_rel} in plan")

    if not _FLUTTER_SKELETON.is_dir():
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    with tempfile.TemporaryDirectory(prefix="figma-flutter-golden-docker-") as tmp:
        capture_dir = Path(tmp) / "project"
        _copy_skeleton_project(capture_dir)
        if project_dir is not None and project_dir.is_dir():
            _sync_project_assets(
                capture_dir,
                project_dir,
                planned=planned,
                layout_tree=layout_tree,
            )
        writer = DartWriter(capture_dir, enable_backup=False)
        writer.write_files(planned)
        if layout_tree is not None:
            sync_fixture_vector_assets(capture_dir, layout_tree)
        golden_out = capture_dir / golden_png_relative_path(feature_name)
        env = os.environ.copy()
        env["FEATURE_NAME"] = feature_name
        env["UPDATE_GOLDENS"] = "1" if update_goldens else "0"
        try:
            result = run_subprocess(
                [
                    docker,
                    "compose",
                    "-f",
                    str(compose),
                    "run",
                    "--rm",
                    "-v",
                    f"{capture_dir}:/capture",
                    "golden-capture",
                ],
                cwd=compose.parent,
                label="docker compose golden-capture",
                timeout_sec=DOCKER_COMPOSE_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return GoldenCaptureResult(
                reason=_clip_reason(
                    f"docker golden capture timed out after {DOCKER_COMPOSE_TIMEOUT_SEC:.0f}s"
                ),
            )
        if result.returncode != 0:
            _log_process_output(result, level="warning")
            return GoldenCaptureResult(reason=_first_process_line(result))
        if not golden_out.is_file():
            return GoldenCaptureResult(reason="golden PNG not written")
        png = golden_out.read_bytes()
        figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
        if project_dir is not None and project_dir.is_dir():
            record_render_png(
                "flutter_golden_docker",
                png,
                extra={"featureName": feature_name, "runtime": "docker"},
            )
        return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def capture_planned_flutter_golden_png_host(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
    layout_tree: CleanDesignTreeNode | None = None,
) -> GoldenCaptureResult:
    """Run ``flutter test --update-goldens`` for planned files on the host."""
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return GoldenCaptureResult(reason="no Flutter SDK (PATH or FIGMA_FLUTTER_SDK)")

    golden_test_rel = golden_test_relative_path(feature_name)
    if golden_test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {golden_test_rel} in plan")

    if not _FLUTTER_SKELETON.is_dir():
        logger.debug("Flutter skeleton missing at {}", _FLUTTER_SKELETON)
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    capture_dir, tmp_handle, enable_backup = _prepare_capture_workspace(
        planned,
        feature_name=feature_name,
        project_dir=project_dir,
        layout_tree=layout_tree,
    )
    try:
        _write_planned_capture_files(
            capture_dir,
            planned,
            enable_backup=enable_backup,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        _prepare_flutter_test_build_dir(capture_dir)
        pub_get_failure = _run_flutter_pub_get(capture_dir, flutter)
        if pub_get_failure is not None:
            return pub_get_failure
        golden_out = capture_dir / golden_png_relative_path(feature_name)
        test_outcome = _run_golden_flutter_test(flutter, capture_dir, golden_test_rel)
        if isinstance(test_outcome, GoldenCaptureResult):
            return test_outcome
        result = test_outcome
        if result.returncode != 0:
            _log_process_output(result, level="warning")
            return GoldenCaptureResult(reason=_first_process_line(result))
        if not golden_out.is_file():
            logger.warning("Golden PNG was not written: {}", golden_out)
            return GoldenCaptureResult(reason="golden PNG not written")
        png = golden_out.read_bytes()
        figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
        if project_dir is not None and project_dir.is_dir():
            record_render_png(
                "flutter_golden_host",
                png,
                extra={"featureName": feature_name, "runtime": "host"},
            )
        return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)
    finally:
        if tmp_handle is not None:
            tmp_handle.cleanup()


def _ensure_docker_golden_image(settings: Settings | None) -> GoldenCaptureResult | None:
    """Build or verify the golden-capture image before ``docker compose run``."""
    if not ensure_golden_capture_image(
        settings,
        build_if_missing=golden_docker_auto_build_enabled(),
        interactive=False,
        print_hint=False,
    ):
        return GoldenCaptureResult(
            reason="golden-capture Docker image missing (auto-build failed or disabled)",
        )
    return None


def capture_planned_flutter_golden_png(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
    golden_runtime: GoldenCaptureMode | None = None,
    settings: Settings | None = None,
    no_docker: bool = False,
    layout_tree: CleanDesignTreeNode | None = None,
) -> GoldenCaptureResult:
    """Capture a golden PNG using the resolved host or Docker runtime."""
    sdk_root = flutter_sdk
    if sdk_root is None and settings is not None:
        sdk_root = settings.flutter_sdk or None
    if flutter_sdk is not None:
        selection = resolve_golden_runtime("host", settings=settings, no_docker=True)
    else:
        selection = resolve_golden_runtime(
            golden_runtime,
            settings=settings,
            no_docker=no_docker,
        )
    if selection.fallback_from_docker and selection.configured in ("docker", "auto"):
        logger.warning(
            "Golden capture falling back to host runtime (configured={})",
            selection.configured,
        )
    if selection.runtime == "docker":
        image_failure = _ensure_docker_golden_image(settings)
        if image_failure is not None:
            return image_failure
        return capture_planned_flutter_golden_png_docker(
            planned,
            feature_name=feature_name,
            project_dir=project_dir,
            layout_tree=layout_tree,
        )
    return capture_planned_flutter_golden_png_host(
        planned,
        feature_name=feature_name,
        flutter_sdk=sdk_root,
        project_dir=project_dir,
        layout_tree=layout_tree,
    )
