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
from figma_flutter_agent.fixtures.assets import iter_layout_asset_keys, sync_fixture_vector_assets
from figma_flutter_agent.generator.writer import DartWriter
from figma_flutter_agent.render_log import expected_render_png_path, record_render_png
from figma_flutter_agent.schemas import CleanDesignTreeNode
from figma_flutter_agent.tools.process_run import (
    DOCKER_COMPOSE_TIMEOUT_SEC,
    FLUTTER_PUB_GET_TIMEOUT_SEC,
    FLUTTER_TEST_TIMEOUT_SEC,
    run_subprocess,
)
from figma_flutter_agent.validation.golden_capture_enrich import (
    enrich_planned_from_project,
    sync_flutter_test_config,
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


@dataclass
class GoldenCaptureHostSession:
    """Reusable capture root (Flutter project dir or temp sandbox)."""

    capture_dir: Path
    feature_name: str
    golden_test_rel: str
    flutter: str
    settings: Settings | None
    in_project: bool = False
    fast_capture: bool = False
    _tmp_handle: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self._tmp_handle is not None:
            _safe_temp_cleanup(self._tmp_handle)

    def refresh_and_capture(
        self,
        planned: Mapping[str, str],
        *,
        project_dir: Path | None,
        layout_tree: CleanDesignTreeNode | None,
    ) -> GoldenCaptureResult:
        """Rewrite planned Dart and re-run golden test in the existing capture root."""
        if self.in_project:
            capture_planned = _write_planned_for_golden_capture(
                self.capture_dir,
                planned,
                layout_tree=layout_tree,
            )
            return _run_golden_test_in_workspace(
                self.capture_dir,
                feature_name=self.feature_name,
                golden_test_rel=self.golden_test_rel,
                flutter=self.flutter,
                settings=self.settings,
                skip_build_clean=True,
                in_project=True,
                fast_capture=self.fast_capture,
            )
        capture_planned = _materialize_capture_workspace(
            self.capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        return _run_golden_test_in_workspace(
            self.capture_dir,
            feature_name=self.feature_name,
            golden_test_rel=self.golden_test_rel,
            flutter=self.flutter,
            settings=self.settings,
            skip_build_clean=True,
            asset_paths_hint=len(collect_planned_asset_paths(capture_planned, layout_tree)),
            fast_capture=self.fast_capture,
        )


@dataclass(frozen=True)
class GoldenCaptureResult:
    """Outcome of an offline golden capture attempt."""

    png: bytes | None = None
    reason: str | None = None
    figma_key_rects: dict[str, Any] | None = None
    host_session: GoldenCaptureHostSession | None = None

    @property
    def ok(self) -> bool:
        """True when golden PNG bytes were captured."""
        return self.png is not None


CAPTURE_OUT_ENV = "FIGMA_FLUTTER_CAPTURE_OUT"
CAPTURE_KEYS_OUT_ENV = "FIGMA_FLUTTER_CAPTURE_KEYS_OUT"


def golden_test_relative_path(feature_name: str) -> str:
    """Return the relative golden test path for a feature screen."""
    return f"test/golden/{feature_name}_screen_test.dart"


def capture_test_relative_path(feature_name: str) -> str:
    """Return the lightweight visual-refine capture test path."""
    return f"test/capture/{feature_name}_screen_capture_test.dart"


def _visual_refine_fast_capture(settings: Settings | None) -> bool:
    if settings is None:
        return True
    return not settings.agent.generation.llm_visual_refine_capture_golden


def _capture_collects_figma_keys(settings: Settings | None) -> bool:
    if settings is None:
        return False
    generation = settings.agent.generation
    return (
        generation.runtime_geometry_gate
        or generation.runtime_geometry_capture_if_missing
    )


def _resolve_host_capture_test(
    planned: Mapping[str, str],
    feature_name: str,
    settings: Settings | None,
) -> tuple[str, bool]:
    """Return ``(test_rel, fast_capture)`` for host visual-refine capture."""
    if _visual_refine_fast_capture(settings):
        capture_rel = capture_test_relative_path(feature_name)
        if capture_rel in planned:
            return capture_rel, True
    golden_rel = golden_test_relative_path(feature_name)
    return golden_rel, False


def _capture_png_out_path(capture_dir: Path, feature_name: str) -> Path:
    return capture_dir / ".figma_flutter_capture" / f"{feature_name}_screen.png"


def _capture_keys_out_path(capture_dir: Path, feature_name: str) -> Path:
    return capture_dir / ".figma_flutter_capture" / f"{feature_name}_figma_keys.json"


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
        paths.update(iter_layout_asset_keys(layout_tree))
    return paths


def _read_figma_key_rects(capture_dir: Path, feature_name: str) -> dict[str, Any] | None:
    keys_path = capture_dir / golden_figma_keys_relative_path(feature_name)
    if not keys_path.is_file():
        return None
    raw = keys_path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Golden capture: invalid {} ({})",
            keys_path.name,
            exc,
        )
        return None
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
    """Copy bundled fonts from the target app into the capture workspace."""
    from figma_flutter_agent.fonts.local import ensure_project_fonts_dir

    ensure_project_fonts_dir(source_project)
    source = source_project / "assets" / "fonts"
    if not source.is_dir():
        return
    font_files = [path for path in source.iterdir() if path.is_file()]
    if not font_files:
        return
    destination = project_dir / "assets" / "fonts"
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    logger.info(
        "Golden capture: copied {} font file(s) from {}",
        len(font_files),
        source_project,
    )


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
        kept = _filter_font_families_on_disk(project_dir, merged_families)
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
    source_assets = source_flutter.get("assets")
    if isinstance(source_assets, list):
        target_assets = target_flutter.setdefault("assets", [])
        if not isinstance(target_assets, list):
            target_assets = []
            target_flutter["assets"] = target_assets
        existing_assets = {str(item) for item in target_assets}
        for item in source_assets:
            normalized = str(item).replace("\\", "/")
            if normalized not in existing_assets:
                target_assets.append(item)
                existing_assets.add(normalized)
    yaml.dump(target_data, target_pubspec.open("w", encoding="utf-8"))


def _ensure_pubspec_asset_dirs(project_dir: Path, asset_paths: set[str]) -> None:
    """Register ``assets/<subdir>/`` in capture ``pubspec.yaml`` for synced files."""
    dirs: set[str] = set()
    for asset_key in asset_paths:
        normalized = asset_key.replace("\\", "/")
        parts = Path(normalized).parts
        if len(parts) >= 2 and parts[0] == "assets":
            dirs.add(f"assets/{parts[1]}/")
    if not dirs:
        return
    pubspec_path = project_dir / "pubspec.yaml"
    if not pubspec_path.is_file():
        return
    yaml = YAML()
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    flutter_section = data.setdefault("flutter", {})
    if not isinstance(flutter_section, dict):
        return
    assets = flutter_section.setdefault("assets", [])
    if not isinstance(assets, list):
        assets = []
        flutter_section["assets"] = assets
    existing = {str(item).replace("\\", "/") for item in assets}
    for asset_dir in sorted(dirs):
        if asset_dir not in existing:
            assets.append(asset_dir)
            existing.add(asset_dir)
    yaml.dump(data, pubspec_path.open("w", encoding="utf-8"))


def _ensure_pubspec_asset_directories_on_disk(project_dir: Path) -> None:
    """Create asset folder entries declared in ``pubspec.yaml`` (Flutter requires them to exist)."""
    pubspec_path = project_dir / "pubspec.yaml"
    if not pubspec_path.is_file():
        return
    yaml = YAML()
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return
    flutter_section = data.get("flutter")
    if not isinstance(flutter_section, dict):
        return
    assets = flutter_section.get("assets")
    if not isinstance(assets, list):
        return
    for item in assets:
        normalized = str(item).replace("\\", "/")
        if not normalized.endswith("/"):
            continue
        (project_dir / normalized.rstrip("/")).mkdir(parents=True, exist_ok=True)


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
            logger.debug("Golden capture: asset missing on disk: {}", normalized)
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
    """Copy fonts, pubspec asset trees, and referenced files from the target app."""
    _sync_fonts_folder(project_dir, source_project)
    _merge_pubspec_fonts_and_assets(project_dir, source_project)
    sync_flutter_test_config(project_dir, source_project)
    _ensure_pubspec_asset_directories_on_disk(project_dir)
    if planned is None:
        return
    asset_paths = collect_planned_asset_paths(planned, layout_tree)
    _sync_referenced_assets(project_dir, source_project, asset_paths)
    _ensure_pubspec_asset_dirs(project_dir, asset_paths)
    _ensure_pubspec_asset_directories_on_disk(project_dir)
    if asset_paths:
        logger.info(
            "Golden capture: synced {} referenced asset file(s) (not full assets/ tree)",
            len(asset_paths),
        )


def _safe_temp_cleanup(tmp_handle: tempfile.TemporaryDirectory[str] | None) -> None:
    if tmp_handle is None:
        return
    try:
        tmp_handle.cleanup()
    except (OSError, RecursionError) as exc:
        logger.debug("Golden capture temp cleanup fallback ({}): {}", exc, tmp_handle.name)
        shutil.rmtree(tmp_handle.name, ignore_errors=True)


def _prepare_flutter_test_build_dir(project_dir: Path) -> None:
    """Drop stale Flutter build output so ``flutter test`` rebuilds the asset bundle."""
    build_dir = project_dir / "build"
    if not build_dir.exists():
        return
    try:
        shutil.rmtree(build_dir)
    except OSError as exc:
        logger.warning("Could not remove {} before golden test: {}", build_dir, exc)


def _run_flutter_pub_get(project_dir: Path, flutter: str) -> GoldenCaptureResult | None:
    """Resolve packages before ``flutter test``. Returns failure or None."""
    from figma_flutter_agent.errors import GenerationError
    from figma_flutter_agent.generator.codegen import run_pub_get

    _ = flutter
    try:
        run_pub_get(project_dir)
    except GenerationError as exc:
        message = str(exc)
        if "timed out" in message:
            return GoldenCaptureResult(
                reason=_clip_reason(
                    f"flutter pub get timed out after {FLUTTER_PUB_GET_TIMEOUT_SEC:.0f}s"
                ),
            )
        return GoldenCaptureResult(reason=_clip_reason("flutter pub get failed before golden test"))
    return None


def _resolve_flutter_test_timeout(settings: Settings | None) -> float:
    if settings is not None:
        return settings.agent.generation.golden_capture_timeout_sec
    return FLUTTER_TEST_TIMEOUT_SEC


def _try_salvage_golden_png(
    capture_dir: Path,
    feature_name: str,
    *,
    failure_reason: str,
) -> GoldenCaptureResult | None:
    """Use an on-disk golden PNG when ``flutter test`` died after writing it."""
    golden_out = capture_dir / golden_png_relative_path(feature_name)
    if not golden_out.is_file():
        return None
    png = golden_out.read_bytes()
    if len(png) < 64:
        return None
    logger.warning(
        "Golden capture recovered PNG from {} after failure ({})",
        golden_out,
        failure_reason,
    )
    record_render_png(
        "flutter_render",
        png,
        extra={
            "featureName": feature_name,
            "runtime": "host",
            "salvaged": True,
            "failureReason": failure_reason,
        },
    )
    figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
    return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def _run_screen_capture_flutter_test(
    flutter: str,
    capture_dir: Path,
    capture_test_rel: str,
    *,
    png_out: Path,
    keys_out: Path | None,
    timeout_sec: float,
    stream_output: bool = False,
) -> subprocess.CompletedProcess[str] | GoldenCaptureResult:
    """Run a capture-only widget test (PNG to env path, no golden compare)."""
    png_out.parent.mkdir(parents=True, exist_ok=True)
    env: dict[str, str] = {CAPTURE_OUT_ENV: str(png_out.resolve())}
    if keys_out is not None:
        keys_out.parent.mkdir(parents=True, exist_ok=True)
        env[CAPTURE_KEYS_OUT_ENV] = str(keys_out.resolve())
    if stream_output:
        logger.info(
            "Flutter screen capture starting (first compile in a warm project is often "
            "3–8 min on Windows; limit {:.0f}s). Compiler output streams below.",
            timeout_sec,
        )
    else:
        logger.info(
            "Flutter screen capture starting (warm project often a few seconds; limit {:.0f}s)",
            timeout_sec,
        )
    try:
        return run_subprocess(
            [
                flutter,
                "test",
                capture_test_rel,
                "--no-pub",
                "--reporter",
                "silent",
                "--fail-fast",
            ],
            cwd=capture_dir,
            label="flutter test capture",
            timeout_sec=timeout_sec,
            stream_output=stream_output,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter screen capture timed out after {timeout_sec:.0f}s "
                "(often Dart compile for `flutter test` on a large layout — "
                "raise generation.golden_capture_timeout_sec; "
                "or check unbounded Stack/Flex / missing assets if compile finished quickly)"
            ),
        )


def _run_golden_flutter_test(
    flutter: str,
    capture_dir: Path,
    golden_test_rel: str,
    *,
    timeout_sec: float,
) -> subprocess.CompletedProcess[str] | GoldenCaptureResult:
    """Run a single golden widget test with bounded timeout."""
    logger.info(
        "Flutter golden test starting (first compile in this temp workspace is often 3–8 min; "
        "hard limit {:.0f}s). Compiler output streams below.",
        timeout_sec,
    )
    try:
        return run_subprocess(
            [
                flutter,
                "test",
                golden_test_rel,
                "--update-goldens",
                "--no-pub",
                "--reporter",
                "expanded",
                "--timeout",
                "2m",
                "--fail-fast",
            ],
            cwd=capture_dir,
            label="flutter test --update-goldens",
            timeout_sec=timeout_sec,
            stream_output=True,
        )
    except subprocess.TimeoutExpired as exc:
        _log_process_output(
            subprocess.CompletedProcess([], 1, exc.stdout, exc.stderr),
            level="warning",
        )
        return GoldenCaptureResult(
            reason=_clip_reason(
                f"flutter test timed out after {timeout_sec:.0f}s "
                "(layout may not settle — check unbounded Stack/Flex or missing assets)"
            ),
        )


def _prepare_capture_workspace() -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    """Return an empty isolated capture root (skeleton only)."""
    tmp = tempfile.TemporaryDirectory(prefix="figma-flutter-golden-")
    capture_dir = Path(tmp.name) / "golden_capture"
    _copy_skeleton_project(capture_dir)
    return capture_dir, tmp


def _write_planned_for_golden_capture(
    capture_dir: Path,
    planned: Mapping[str, str],
    *,
    layout_tree: CleanDesignTreeNode | None,
) -> dict[str, str]:
    """Flush in-memory planned Dart into an on-disk Flutter tree (no asset tree copy)."""
    capture_planned = enrich_planned_from_project(dict(planned), capture_dir)
    writer = DartWriter(capture_dir, enable_backup=True)
    writer.write_files(capture_planned)
    if layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree, overwrite=False)
    return capture_planned


def _materialize_capture_workspace(
    capture_dir: Path,
    planned: dict[str, str],
    *,
    enable_backup: bool,
    layout_tree: CleanDesignTreeNode | None,
    project_dir: Path | None,
) -> dict[str, str]:
    """Enrich planned Dart, write files, and sync fonts/assets into an isolated sandbox."""
    capture_planned = dict(planned)
    if project_dir is not None and project_dir.is_dir():
        capture_planned = enrich_planned_from_project(capture_planned, project_dir)
    writer = DartWriter(capture_dir, enable_backup=enable_backup)
    writer.write_files(capture_planned)
    if layout_tree is not None:
        sync_fixture_vector_assets(capture_dir, layout_tree)
    if project_dir is not None and project_dir.is_dir():
        _sync_project_assets(
            capture_dir,
            project_dir,
            planned=capture_planned,
            layout_tree=layout_tree,
        )
    return capture_planned


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
        _materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        _prepare_flutter_test_build_dir(capture_dir)
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
        record_render_png(
            "flutter_render",
            png,
            extra={"featureName": feature_name, "runtime": "docker"},
        )
        return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def _run_golden_test_in_workspace(
    capture_dir: Path,
    *,
    feature_name: str,
    golden_test_rel: str,
    flutter: str,
    settings: Settings | None,
    skip_build_clean: bool,
    asset_paths_hint: int = 0,
    in_project: bool = False,
    fast_capture: bool = False,
) -> GoldenCaptureResult:
    if not skip_build_clean:
        _prepare_flutter_test_build_dir(capture_dir)
        pub_get_failure = _run_flutter_pub_get(capture_dir, flutter)
        if pub_get_failure is not None:
            return pub_get_failure
    png_out = (
        _capture_png_out_path(capture_dir, feature_name)
        if fast_capture
        else capture_dir / golden_png_relative_path(feature_name)
    )
    keys_out = (
        _capture_keys_out_path(capture_dir, feature_name)
        if fast_capture and _capture_collects_figma_keys(settings)
        else None
    )
    render_dest = expected_render_png_path("flutter_render")
    if in_project:
        logger.info(
            "Rendering Flutter screen for {} in project {} ({}) {}{} → {}",
            feature_name,
            capture_dir,
            golden_test_rel,
            "capture " if fast_capture else "golden ",
            png_out,
            render_dest.resolve() if render_dest is not None else "logs/renders",
        )
    elif render_dest is not None:
        logger.info(
            "Rendering Flutter screen for {} ({}); {}{} → combat log {}{}",
            feature_name,
            golden_test_rel,
            "capture " if fast_capture else "golden ",
            png_out,
            render_dest.resolve(),
            f" ({asset_paths_hint} assets synced)" if asset_paths_hint else "",
        )
    else:
        logger.info(
            "Rendering Flutter screen for {} ({}); output {}",
            feature_name,
            golden_test_rel,
            png_out,
        )
    test_timeout = _resolve_flutter_test_timeout(settings)
    if fast_capture:
        test_outcome = _run_screen_capture_flutter_test(
            flutter,
            capture_dir,
            golden_test_rel,
            png_out=png_out,
            keys_out=keys_out,
            timeout_sec=test_timeout,
            stream_output=in_project or fast_capture,
        )
    else:
        test_outcome = _run_golden_flutter_test(
            flutter,
            capture_dir,
            golden_test_rel,
            timeout_sec=test_timeout,
        )
    if isinstance(test_outcome, GoldenCaptureResult):
        if fast_capture:
            return test_outcome
        salvaged = _try_salvage_golden_png(
            capture_dir,
            feature_name,
            failure_reason=test_outcome.reason or "flutter test failed",
        )
        if salvaged is not None:
            return salvaged
        return test_outcome
    result = test_outcome
    if result.returncode != 0:
        _log_process_output(result, level="warning")
        reason = _first_process_line(result)
        if fast_capture:
            return GoldenCaptureResult(reason=reason)
        salvaged = _try_salvage_golden_png(
            capture_dir,
            feature_name,
            failure_reason=reason,
        )
        if salvaged is not None:
            return salvaged
        return GoldenCaptureResult(reason=reason)
    if not png_out.is_file():
        logger.warning("Capture PNG was not written: {}", png_out)
        return GoldenCaptureResult(reason="screen capture PNG not written")
    png = png_out.read_bytes()
    if fast_capture and keys_out is not None and keys_out.is_file():
        raw = keys_out.read_text(encoding="utf-8").strip()
        try:
            figma_key_rects = json.loads(raw) if raw else None
        except json.JSONDecodeError as exc:
            logger.warning("Capture: invalid {} ({})", keys_out.name, exc)
            figma_key_rects = None
    else:
        figma_key_rects = _read_figma_key_rects(capture_dir, feature_name)
    saved = record_render_png(
        "flutter_render",
        png,
        extra={"featureName": feature_name, "runtime": "host", "goldenPath": str(png_out)},
    )
    if saved is None:
        logger.warning(
            "Golden PNG captured at {} but not copied to logs/renders/ "
            "(enable generation.llm_visual_refine)",
            png_out,
        )
    return GoldenCaptureResult(png=png, figma_key_rects=figma_key_rects)


def _capture_planned_flutter_golden_png_in_project(
    planned: dict[str, str],
    *,
    feature_name: str,
    project_dir: Path,
    layout_tree: CleanDesignTreeNode | None,
    flutter: str,
    settings: Settings | None,
    golden_test_rel: str,
    host_session: GoldenCaptureHostSession | None,
    fast_capture: bool = False,
) -> GoldenCaptureResult:
    """Run golden capture in the user's Flutter project (no temp tree, no asset copy)."""
    if host_session is not None and host_session.in_project:
        result = host_session.refresh_and_capture(
            planned,
            project_dir=project_dir,
            layout_tree=layout_tree,
        )
        if result.ok:
            return GoldenCaptureResult(
                png=result.png,
                figma_key_rects=result.figma_key_rects,
                host_session=host_session,
            )
        host_session.close()
        return result

    capture_planned = _write_planned_for_golden_capture(
        project_dir,
        planned,
        layout_tree=layout_tree,
    )
    pub_get_failure = _run_flutter_pub_get(project_dir, flutter)
    if pub_get_failure is not None:
        return pub_get_failure
    result = _run_golden_test_in_workspace(
        project_dir,
        feature_name=feature_name,
        golden_test_rel=golden_test_rel,
        flutter=flutter,
        settings=settings,
        skip_build_clean=True,
        in_project=True,
        fast_capture=fast_capture,
    )
    if not result.ok:
        return result
    session = GoldenCaptureHostSession(
        capture_dir=project_dir,
        feature_name=feature_name,
        golden_test_rel=golden_test_rel,
        flutter=flutter,
        settings=settings,
        in_project=True,
        fast_capture=fast_capture,
        _tmp_handle=None,
    )
    return GoldenCaptureResult(
        png=result.png,
        figma_key_rects=result.figma_key_rects,
        host_session=session,
    )


def capture_planned_flutter_golden_png_host(
    planned: dict[str, str],
    *,
    feature_name: str,
    flutter_sdk: str | Path | None = None,
    project_dir: Path | None = None,
    layout_tree: CleanDesignTreeNode | None = None,
    settings: Settings | None = None,
    host_session: GoldenCaptureHostSession | None = None,
    capture_in_project: bool = True,
) -> GoldenCaptureResult:
    """Capture a Flutter screen PNG on the host (fast capture or golden test)."""
    flutter = resolve_flutter_executable(sdk_root=flutter_sdk)
    if flutter is None:
        return GoldenCaptureResult(reason="no Flutter SDK (PATH or FIGMA_FLUTTER_SDK)")

    test_rel, fast_capture = _resolve_host_capture_test(planned, feature_name, settings)
    if test_rel not in planned:
        return GoldenCaptureResult(reason=f"no {test_rel} in plan")

    if not _FLUTTER_SKELETON.is_dir():
        logger.debug("Flutter skeleton missing at {}", _FLUTTER_SKELETON)
        return GoldenCaptureResult(reason="flutter skeleton fixture missing")

    if project_dir is not None and project_dir.is_dir() and capture_in_project:
        return _capture_planned_flutter_golden_png_in_project(
            planned,
            feature_name=feature_name,
            project_dir=project_dir,
            layout_tree=layout_tree,
            flutter=flutter,
            settings=settings,
            golden_test_rel=test_rel,
            host_session=host_session,
            fast_capture=fast_capture,
        )

    if host_session is not None:
        result = host_session.refresh_and_capture(
            planned,
            project_dir=project_dir,
            layout_tree=layout_tree,
        )
        if result.ok:
            return GoldenCaptureResult(
                png=result.png,
                figma_key_rects=result.figma_key_rects,
                host_session=host_session,
            )
        host_session.close()
        return result

    capture_dir, tmp_handle = _prepare_capture_workspace()
    try:
        capture_planned = _materialize_capture_workspace(
            capture_dir,
            planned,
            enable_backup=False,
            layout_tree=layout_tree,
            project_dir=project_dir,
        )
        result = _run_golden_test_in_workspace(
            capture_dir,
            feature_name=feature_name,
            golden_test_rel=test_rel,
            flutter=flutter,
            settings=settings,
            skip_build_clean=False,
            asset_paths_hint=len(collect_planned_asset_paths(capture_planned, layout_tree)),
            fast_capture=fast_capture,
        )
        if not result.ok:
            return result
        session = GoldenCaptureHostSession(
            capture_dir=capture_dir,
            feature_name=feature_name,
            golden_test_rel=test_rel,
            flutter=flutter,
            settings=settings,
            in_project=False,
            fast_capture=fast_capture,
            _tmp_handle=tmp_handle,
        )
        return GoldenCaptureResult(
            png=result.png,
            figma_key_rects=result.figma_key_rects,
            host_session=session,
        )
    except Exception:
        _safe_temp_cleanup(tmp_handle)
        raise


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
    host_session: GoldenCaptureHostSession | None = None,
    capture_in_project: bool = True,
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
        settings=settings,
        host_session=host_session,
        capture_in_project=capture_in_project,
    )
