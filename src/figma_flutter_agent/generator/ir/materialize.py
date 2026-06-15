"""Resolve IR fields into Dart for planner/renderer output."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.generator.dart.llm_codegen import (
    _WIDGET_CLASS_RE,
    _canonical_widget_class_name,
    apply_clean_tree_text_to_screen,
    prepare_llm_extracted_widgets,
)
from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.presence import normalize_screen_ir_presence
from figma_flutter_agent.generator.ir.screen import emit_screen_code_from_ir
from figma_flutter_agent.generator.ir.validate import (
    apply_ir_guards,
    validate_extracted_widgets,
    validate_screen_ir,
)
from figma_flutter_agent.generator.layout.common import to_pascal_case
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    ExtractedWidget,
    FlutterGenerationResponse,
)


def materialize_screen_code_from_ir(
    generation: FlutterGenerationResponse,
    *,
    clean_tree: CleanDesignTreeNode,
    feature_name: str,
    ctx: IrEmitContext,
    use_auto_route: bool = False,
    use_scaffold: bool = True,
    responsive_shell: bool = False,
    prefer_existing_screen_code: bool = False,
    materialize_screen_body: bool = True,
    materialize_extracted: bool = True,
    prefer_existing_extracted_code: bool = True,
    project_dir: Path | None = None,
    tokens: DesignTokens | None = None,
    macro_height_threshold_px: int = 900,
    inject_root_scroll_host: bool = True,
) -> FlutterGenerationResponse:
    """Resolve IR fields into Dart for the existing planner/renderer path."""
    extracted_names = frozenset(widget.widget_name for widget in generation.extracted_widgets)
    if generation.screen_ir is not None:
        screen_ir = normalize_screen_ir_presence(
            generation.screen_ir,
            clean_tree,
            extracted_widget_names=extracted_names,
        )
        if screen_ir is not generation.screen_ir:
            generation = generation.model_copy(update={"screen_ir": screen_ir})
        if ctx.policy.validate:
            clean_tree = validate_screen_ir(
                generation.screen_ir,
                clean_tree,
                extracted_widget_names=extracted_names,
                project_dir=project_dir,
                tokens=tokens,
                apply_guards=ctx.policy.apply_guards,
            )
        elif ctx.policy.apply_guards:
            clean_tree = apply_ir_guards(generation.screen_ir, clean_tree, tokens=tokens)
        from figma_flutter_agent.generator.ir.passes import apply_ir_layout_passes

        updated_ir, updated_clean = apply_ir_layout_passes(
            generation.screen_ir,
            clean_tree,
            macro_height_threshold_px=macro_height_threshold_px,
            inject_root_scroll_host=inject_root_scroll_host,
        )
        generation = generation.model_copy(update={"screen_ir": updated_ir})
        clean_tree = updated_clean
        from figma_flutter_agent.generator.geometry.invariants.checkpoints import (
            run_cp_post_classify,
        )
        from figma_flutter_agent.generator.ir.passes import apply_ir_classification_passes
        from figma_flutter_agent.generator.tree_copy import deep_copy_clean_tree

        pre_classify_clean = deep_copy_clean_tree(clean_tree)
        pre_classify_ir = generation.screen_ir.model_copy(deep=True)
        classified_ir, classified_clean = apply_ir_classification_passes(
            generation.screen_ir,
            clean_tree,
        )
        run_cp_post_classify(
            pre_classify_clean,
            pre_classify_ir,
            classified_clean,
            classified_ir,
        )
        from figma_flutter_agent.generator.ir.fidelity.manifest import (
            feature_profile_from_theme,
        )
        from figma_flutter_agent.generator.ir.passes.fidelity import stamp_fidelity_tiers

        stamped_ir = stamp_fidelity_tiers(
            classified_ir,
            feature_profile=feature_profile_from_theme(ctx.theme_variant),
            clean_tree=classified_clean,
            strict_fidelity=ctx.strict_fidelity,
            strict_l10n=ctx.strict_l10n,
            strict_a11y=ctx.strict_a11y,
        )
        generation = generation.model_copy(update={"screen_ir": stamped_ir})
        clean_tree = classified_clean
        if project_dir is not None:
            from figma_flutter_agent.debug.ir_dumps import write_screen_ir_snapshot

            write_screen_ir_snapshot(
                stage="pre_emit",
                feature_name=feature_name,
                screen_ir=generation.screen_ir,
                extracted_widgets=generation.extracted_widgets or None,
                project_dir=project_dir,
            )
    if materialize_extracted and generation.extracted_widgets:
        from figma_flutter_agent.generator.ir.extracted import (
            drop_extracted_widgets_for_inline_hosts,
            materialize_extracted_widgets,
        )

        filtered_widgets = drop_extracted_widgets_for_inline_hosts(
            generation.extracted_widgets,
            clean_tree,
        )
        if len(filtered_widgets) != len(generation.extracted_widgets):
            generation = generation.model_copy(update={"extracted_widgets": filtered_widgets})
        validate_extracted_widgets(
            generation.extracted_widgets,
            clean_tree,
            project_dir=project_dir,
            tokens=tokens,
        )
        widgets = materialize_extracted_widgets(
            generation.extracted_widgets,
            clean_tree=clean_tree,
            ctx=ctx,
            prefer_existing_code=prefer_existing_extracted_code,
            project_dir=project_dir,
            tokens=tokens,
        )
        generation = generation.model_copy(update={"extracted_widgets": widgets})

    if generation.screen_ir is None or not materialize_screen_body:
        return generation
    if prefer_existing_screen_code and generation.resolved_screen_code():
        return generation

    extracted_class_map = build_extracted_class_map(generation.extracted_widgets)
    screen_class = f"{to_pascal_case(feature_name)}Screen"
    title = feature_name.replace("_", " ").strip().title() or "Screen"
    screen_code = emit_screen_code_from_ir(
        generation.screen_ir,
        clean_tree=clean_tree,
        screen_class=screen_class,
        ctx=ctx,
        use_auto_route=use_auto_route,
        use_scaffold=use_scaffold,
        app_bar_title=title,
        responsive_shell=responsive_shell,
        extracted_class_by_widget_name=extracted_class_map,
        extracted_widget_names=extracted_names,
        project_dir=project_dir,
        tokens=tokens,
    )
    from figma_flutter_agent.generator.dart.file_parts import strip_directives_from_fragment

    screen_code = strip_directives_from_fragment(
        apply_clean_tree_text_to_screen(screen_code, clean_tree),
    )
    return generation.model_copy(update={"screen_code": screen_code})


def build_extracted_class_map(
    widgets: list[ExtractedWidget],
) -> dict[str, str]:
    pairs = [
        (widget.widget_name.strip(), widget.resolved_code())
        for widget in widgets
        if widget.widget_name.strip() and widget.resolved_code()
    ]
    if pairs:
        prepared, _ = prepare_llm_extracted_widgets(pairs)
        mapping: dict[str, str] = {}
        for widget_name, code in prepared:
            match = _WIDGET_CLASS_RE.search(code)
            mapping[widget_name] = (
                match.group("name") if match else _canonical_widget_class_name(widget_name)
            )
        return mapping
    mapping = {}
    for widget in widgets:
        name = widget.widget_name.strip()
        if not name:
            continue
        mapping[name] = _canonical_widget_class_name(name)
    return mapping


materialize_generation_from_ir = materialize_screen_code_from_ir
