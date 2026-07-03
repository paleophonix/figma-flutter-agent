"""Build single-file IR emitter reference bundles under ``.debug/reference``."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.debug.dart_bundle import build_planned_dart_bundle
from figma_flutter_agent.debug.paths import (
    debug_path_display,
    emitter_reference_bundle_path,
    emitter_reference_metadata_path,
    processed_dump_path,
    resolve_processed_dump_path,
    resolve_screen_ir_dump_file,
    screen_ir_dump_path,
)
from figma_flutter_agent.generator.ir.context import IrEmitContext, IrEmitPolicy
from figma_flutter_agent.generator.ir.materialize import materialize_screen_code_from_ir
from figma_flutter_agent.generator.ir.tree import merge_screen_ir
from figma_flutter_agent.generator.layout import render_layout_file
from figma_flutter_agent.generator.paths import Architecture
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.theme_typography import (
    build_text_theme_size_slots,
    build_text_theme_slot_by_style_name,
)
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
    ScreenIr,
)


def write_emitter_reference(
    project_dir: Path,
    *,
    feature_name: str,
    uses_svg: bool = True,
    package_name: str | None = None,
    architecture: Architecture = "feature_first",
) -> Path:
    """Write a single-file emitter golden bundle for ``feature_name``.

    The bundle mirrors ``.debug/dart/<feature>_screen.dart``: extracted widgets,
    generated layout (IR-merged clean tree), and screen shell in one file.

    Args:
        project_dir: Flutter project root containing ``.debug`` dumps.
        feature_name: Screen feature slug (e.g. ``background``).
        uses_svg: When True, include ``flutter_svg`` imports in generated Dart.
        package_name: Pubspec package name; read from ``pubspec.yaml`` when omitted.
        architecture: Flutter project layout mode for screen path resolution.

    Returns:
        Path to the written ``.debug/reference/<feature>_screen.dart`` file.

    Raises:
        FileNotFoundError: When processed or pre_emit IR dumps are missing.
        ValueError: When the bundle cannot be assembled (missing screen path).
    """
    if package_name is None:
        from figma_flutter_agent.generator.pubspec import read_pubspec_name

        package_name = read_pubspec_name(project_dir)

    processed_path = resolve_processed_dump_path(project_dir, feature_name)
    if processed_path is None:
        msg = (
            f"Processed dump not found for {feature_name!r} under "
            f"{processed_dump_path(project_dir, feature_name).parent.as_posix()}"
        )
        raise FileNotFoundError(msg)
    ir_path = resolve_screen_ir_dump_file(project_dir, feature_name, "pre_emit")
    if ir_path is None:
        msg = (
            f"Screen IR pre_emit dump not found for {feature_name!r} under "
            f"{screen_ir_dump_path(project_dir, feature_name, 'pre_emit').parent.as_posix()}"
        )
        raise FileNotFoundError(msg)

    processed = json.loads(processed_path.read_text(encoding="utf-8"))
    clean_tree = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    tokens = DesignTokens.model_validate(processed.get("tokens", {}))

    ir_payload = json.loads(ir_path.read_text(encoding="utf-8"))
    screen_ir = ScreenIr.model_validate(ir_payload["screenIr"])
    extracted = [
        ExtractedWidget.model_validate(widget) for widget in ir_payload.get("extractedWidgets", [])
    ]

    text_slots = build_text_theme_slot_by_style_name(tokens)
    size_slots = build_text_theme_size_slots(tokens)
    merged = merge_screen_ir(clean_tree, screen_ir)

    planned_files = render_layout_file(
        merged,
        feature_name=feature_name,
        uses_svg=uses_svg,
        package_name=package_name,
        text_theme_slot_by_style_name=text_slots,
        text_theme_size_slots=size_slots,
    )

    generation = FlutterGenerationResponse(
        screen_ir=screen_ir,
        extracted_widgets=extracted,
    )
    ctx = IrEmitContext(
        uses_svg=uses_svg,
        text_theme_slot_by_style_name=text_slots,
        text_theme_size_slots=size_slots,
        policy=IrEmitPolicy(validate=True, apply_guards=True),
    )
    materialized = materialize_screen_code_from_ir(
        generation,
        clean_tree=clean_tree,
        feature_name=feature_name,
        ctx=ctx,
        tokens=tokens,
        project_dir=project_dir,
        use_scaffold=True,
        responsive_shell=True,
    )

    renderer = DartRenderer()
    planned_files.update(
        renderer.render_generation_files(
            materialized,
            feature_name=feature_name,
            uses_svg=uses_svg,
            layout_import=f"{feature_name}_layout",
            package_name=package_name,
            responsive_enabled=True,
            architecture=architecture,
        ),
    )

    bundle = build_planned_dart_bundle(
        feature_name=feature_name,
        planned_files=planned_files,
        package_name=package_name,
        architecture=architecture,
        banner="EMITTER REFERENCE",
        description=(
            "Single-file golden for IR emitter output (merge_screen_ir + materialize + layout)."
        ),
    )
    if bundle is None:
        msg = f"Could not build emitter reference bundle for feature {feature_name!r}"
        raise ValueError(msg)

    out_path = emitter_reference_bundle_path(project_dir, feature_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _remove_legacy_split_reference_files(out_path.parent, feature_name)
    out_path.write_text(bundle, encoding="utf-8")

    meta = {
        "feature": feature_name,
        "sources": {
            "processed": debug_path_display(processed_path, project_dir),
            "screenIr": debug_path_display(ir_path, project_dir),
        },
        "bundle": debug_path_display(out_path, project_dir),
        "spec": "docs/spec/26-05-24-product-spec/spec.md — theme tokens, responsive shell, const widgets, no inline fontFamily",
    }
    meta_path = emitter_reference_metadata_path(project_dir, feature_name)
    meta_path.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved emitter reference bundle to {}", out_path.as_posix())
    return out_path


def _remove_legacy_split_reference_files(ref_dir: Path, feature_name: str) -> None:
    """Delete pre-bundle split artifacts when refreshing a reference golden."""
    legacy_names = [
        f"{feature_name}_layout.dart",
        f"{feature_name}_screen_emit.dart",
        "back_icon_widget.dart",
        "calendar_icon_widget.dart",
    ]
    for name in legacy_names:
        path = ref_dir / name
        if path.is_file():
            path.unlink()
