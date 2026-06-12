"""Build single-file IR emitter reference bundles under ``.debug/reference``."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from figma_flutter_agent.debug.dart_bundle import build_planned_dart_bundle
from figma_flutter_agent.debug.paths import emitter_reference_bundle_path
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

    processed_path = (
        project_dir
        / ".debug"
        / "processed"
        / f"{feature_name}_layout.json"
    )
    ir_path = project_dir / ".debug" / "ir" / f"{feature_name}_pre_emit.json"
    if not processed_path.is_file():
        msg = f"Processed dump not found: {processed_path.as_posix()}"
        raise FileNotFoundError(msg)
    if not ir_path.is_file():
        msg = f"Screen IR pre_emit dump not found: {ir_path.as_posix()}"
        raise FileNotFoundError(msg)

    processed = json.loads(processed_path.read_text(encoding="utf-8"))
    clean_tree = CleanDesignTreeNode.model_validate(processed["cleanTree"])
    tokens = DesignTokens.model_validate(processed.get("tokens", {}))

    ir_payload = json.loads(ir_path.read_text(encoding="utf-8"))
    screen_ir = ScreenIr.model_validate(ir_payload["screenIr"])
    extracted = [
        ExtractedWidget.model_validate(widget)
        for widget in ir_payload.get("extractedWidgets", [])
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
            "Single-file golden for IR emitter output "
            "(merge_screen_ir + materialize + layout)."
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
            "processed": processed_path.relative_to(project_dir).as_posix(),
            "screenIr": ir_path.relative_to(project_dir).as_posix(),
        },
        "bundle": out_path.relative_to(project_dir).as_posix(),
        "spec": "docs/spec.md — theme tokens, responsive shell, const widgets, no inline fontFamily",
    }
    meta_path = out_path.parent / f"{feature_name}_reference.json"
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
