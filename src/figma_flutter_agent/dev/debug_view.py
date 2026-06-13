"""Preview screens from ``.debug/dart`` or ``.debug/reference`` bundles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from loguru import logger

from figma_flutter_agent.config import Settings, load_settings
from figma_flutter_agent.debug.dart_bundle_parse import (
    detect_screen_class_from_planned_files,
    planned_files_from_dart_bundle,
)
from figma_flutter_agent.debug.paths import (
    dart_debug_snapshot_path,
    emitter_reference_bundle_path,
)
from figma_flutter_agent.dev.project import ensure_project_config
from figma_flutter_agent.dev.run import launch_flutter_app
from figma_flutter_agent.dev.wizard import build_run_plan
from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.generator.pubspec import read_pubspec_name
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.pipeline.helpers import routing_enabled as pipeline_routing_enabled


class DebugViewSource(StrEnum):
    """Cached Dart bundle location for interactive preview."""

    DART_FINAL = "dart"
    DART_PLAN = "dart_plan"
    REFERENCE = "reference"


@dataclass(frozen=True)
class DebugViewBundleChoice:
    """One selectable cached bundle for interactive preview."""

    menu_label: str
    source: DebugViewSource
    path: Path


def _bundle_path_for_source(
    project_dir: Path,
    feature_name: str,
    source: DebugViewSource,
) -> Path:
    if source is DebugViewSource.REFERENCE:
        return emitter_reference_bundle_path(project_dir, feature_name)
    snapshot = "plan" if source is DebugViewSource.DART_PLAN else "final"
    return dart_debug_snapshot_path(project_dir, feature_name, snapshot)


def discover_view_bundle_choices(
    project_dir: Path,
    feature_name: str,
) -> list[DebugViewBundleChoice]:
    """Return menu choices for bundles that exist on disk.

    Order is intentional: ``dart`` (final), ``reference``, then ``dart-plan``.
    """
    ordered_sources = (
        DebugViewSource.DART_FINAL,
        DebugViewSource.REFERENCE,
        DebugViewSource.DART_PLAN,
    )
    command_labels = {
        DebugViewSource.DART_FINAL: "dart",
        DebugViewSource.REFERENCE: "ref",
        DebugViewSource.DART_PLAN: "plan",
    }
    choices: list[DebugViewBundleChoice] = []
    for source in ordered_sources:
        path = _bundle_path_for_source(project_dir, feature_name, source)
        if not path.is_file():
            continue
        rel = path.relative_to(project_dir).as_posix()
        command = command_labels[source]
        choices.append(
            DebugViewBundleChoice(
                menu_label=f"{command} — {rel}",
                source=source,
                path=path,
            )
        )
    return choices


def resolve_view_bundle_choice_input(
    raw: str,
    choices: list[DebugViewBundleChoice],
) -> int | None:
    """Map numeric or textual menu input to a choice index."""
    text = raw.strip().lower()
    if not text:
        return None
    aliases = {
        "dart": DebugViewSource.DART_FINAL,
        "final": DebugViewSource.DART_FINAL,
        "screen": DebugViewSource.DART_FINAL,
        "ref": DebugViewSource.REFERENCE,
        "reference": DebugViewSource.REFERENCE,
        "golden": DebugViewSource.REFERENCE,
        "emitter": DebugViewSource.REFERENCE,
        "plan": DebugViewSource.DART_PLAN,
        "dart-plan": DebugViewSource.DART_PLAN,
        "dart_plan": DebugViewSource.DART_PLAN,
    }
    if text in aliases:
        wanted = aliases[text]
        for index, choice in enumerate(choices):
            if choice.source is wanted:
                return index
        return None
    if text.isdigit():
        num = int(text)
        if 1 <= num <= len(choices):
            return num - 1
    return None


def resolve_debug_view_bundle_path(
    project_dir: Path,
    feature_name: str,
    source: DebugViewSource,
) -> Path:
    """Return an existing debug bundle path for ``feature_name``.

    Args:
        project_dir: Flutter project root.
        feature_name: Screen feature slug.
        source: Bundle kind (planned dart final/plan or emitter reference).

    Returns:
        Path to the bundle ``.dart`` file.

    Raises:
        FlutterProjectError: When the bundle file is missing.
    """
    path = _bundle_path_for_source(project_dir, feature_name, source)
    if not path.is_file():
        raise FlutterProjectError(
            f"Debug bundle not found for {feature_name!r}: {path.as_posix()}. "
            "Run generate first or pick another source."
        )
    return path


def deploy_debug_bundle_to_project(
    project_dir: Path,
    bundle_path: Path,
    *,
    feature_name: str,
    settings: Settings | None = None,
) -> dict[str, str]:
    """Write bundle sections into ``lib/`` and refresh ``main.dart``.

    Args:
        project_dir: Flutter project root.
        bundle_path: Single-file debug or reference bundle.
        feature_name: Screen slug for bootstrap wiring.
        settings: Optional settings; loaded from agent config when omitted.

    Returns:
        All files written (including ``lib/main.dart``).
    """
    config_path = ensure_project_config(project_dir)
    active_settings = settings or load_settings(config_path)
    package_name = read_pubspec_name(project_dir)
    architecture = active_settings.agent.flutter.architecture
    bundle_text = bundle_path.read_text(encoding="utf-8")
    planned = planned_files_from_dart_bundle(bundle_text, package_name=package_name)
    screen_class = detect_screen_class_from_planned_files(
        planned,
        feature_name=feature_name,
        architecture=architecture,
    )

    renderer = DartRenderer()
    routing_on = pipeline_routing_enabled(active_settings)
    planned.update(
        renderer.render_app_bootstrap(
            feature_name=feature_name,
            screen_class=screen_class,
            app_title=feature_name.replace("_", " ").strip().title() or "Screen",
            routing_type=active_settings.agent.routing.type,
            routing_enabled=routing_on,
            generate_dark_mode=active_settings.agent.dark_mode.enabled,
            max_web_width=active_settings.agent.responsive.max_web_width,
            architecture=architecture,
            package_name=package_name,
            use_package_imports=True,
            state_management_type=active_settings.agent.state_management.type,
            theme_variant=active_settings.agent.theme.variant,
        )
    )

    written: dict[str, str] = {}
    for rel_path, content in planned.items():
        target = project_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written[rel_path] = content
        logger.info("Deployed debug bundle section to {}", rel_path)

    return written


def launch_debug_view(
    project_dir: Path,
    *,
    feature_name: str,
    source: DebugViewSource | None = None,
    bundle_path: Path | None = None,
    device_id: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Deploy a cached bundle and run ``flutter run``.

    Args:
        project_dir: Flutter project root.
        feature_name: Manifest feature slug.
        source: ``dart`` (final), ``dart_plan``, or ``reference`` bundle (ignored when
            ``bundle_path`` is set).
        bundle_path: Resolved bundle file; skips lookup when provided.
        device_id: Optional ``flutter run -d`` target.
        settings: Optional agent settings.

    Returns:
        True when ``flutter run`` exits cleanly; False when stopped by the user.

    Raises:
        FlutterProjectError: When the bundle is missing or Flutter commands fail.
    """
    if bundle_path is None:
        if source is None:
            raise FlutterProjectError("launch_debug_view requires source or bundle_path")
        bundle_path = resolve_debug_view_bundle_path(project_dir, feature_name, source)
    config_path = ensure_project_config(project_dir)
    active_settings = settings or load_settings(config_path)
    deploy_debug_bundle_to_project(
        project_dir,
        bundle_path,
        feature_name=feature_name,
        settings=active_settings,
    )
    dump_path: Path | None = None
    try:
        dump_path = build_run_plan(
            project_dir=project_dir,
            screen_name=feature_name,
        ).dump_path
    except (FileNotFoundError, ValueError):
        logger.debug("No manifest dump for {} — Chrome artboard sizing skipped", feature_name)
    return launch_flutter_app(
        project_dir,
        device_id=device_id,
        flutter_sdk=active_settings.flutter_sdk or None,
        dump_path=dump_path,
        settings=active_settings,
    )
