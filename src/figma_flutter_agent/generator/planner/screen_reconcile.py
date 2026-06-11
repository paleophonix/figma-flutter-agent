"""Post-IR screen code reconciliation helpers for the generation planner."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.llm_codegen import (
    apply_clean_tree_text_to_screen,
    apply_safe_screen_code_patch,
)
from figma_flutter_agent.generator.figma_anchor import (
    companion_dart_sources_for_layout_inject,
    ensure_screen_stack_paint_order,
    inject_figma_keys_into_screen,
    inject_missing_layout_positioned,
)
from figma_flutter_agent.generator.planned.reconcile import (
    ensure_referenced_widget_imports,
    widget_import_stems_for_screen,
)
from figma_flutter_agent.generator.planner.context import GenerationPlanContext
from figma_flutter_agent.generator.renderer import DartRenderer
from figma_flutter_agent.generator.subtree import (
    SubtreeWidgetResult,
    merge_thin_llm_widgets_with_subtrees,
    reconcile_llm_screen_with_subtrees,
)


def merge_subtree_results(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    subtree_result: SubtreeWidgetResult | None,
    deterministic_widget_imports: list[str],
) -> tuple[dict[str, str], list[str]]:
    """Merge thin LLM widgets with subtree results and filter widget imports.

    Args:
        context: Parsed design data, settings, and optional LLM output.
        planned_files: Mapping of relative project paths to file contents.
        subtree_result: Result of subtree widget planning, or ``None``.
        deterministic_widget_imports: Widget import stems collected so far.

    Returns:
        Tuple of updated planned files and updated widget import stems.
    """
    from figma_flutter_agent.generator.planned.reconcile import filter_widget_import_stems

    if subtree_result is not None:
        planned_files = merge_thin_llm_widgets_with_subtrees(planned_files, subtree_result)
        deterministic_widget_imports = filter_widget_import_stems(
            deterministic_widget_imports,
            planned_files,
        )
    return planned_files, deterministic_widget_imports


def reconcile_screen_code_with_layout(
    context: GenerationPlanContext,
    planned_files: dict[str, str],
    *,
    subtree_result: SubtreeWidgetResult | None,
    uses_svg: bool,
    use_auto_route: bool,
    responsive_shell: bool,
    shell_safe_area: bool,
    max_web_width: int,
    layout_import_name: str,
    architecture: str,
    package_name: str,
    use_package_imports: bool,
    state_management_type: str,
    quiet_expected_fallback: bool,
) -> dict[str, str]:
    """Patch generated screen code against the layout file and re-render it.

    Applies Figma key injection, layout `Positioned` injection, clean-tree
    text sync, and stack paint-order normalization to the LLM-authored
    screen code, then re-renders the screen file if anything changed.

    Args:
        context: Parsed design data, settings, and optional LLM output.
            Mutated in place when the screen code changes.
        planned_files: Mapping of relative project paths to file contents.
        subtree_result: Result of subtree widget planning, or ``None``.
        uses_svg: Whether the design references SVG assets.
        use_auto_route: Whether routing uses `auto_route`.
        responsive_shell: Whether the responsive shell is enabled.
        shell_safe_area: Whether the shell wraps content in a safe area.
        max_web_width: Maximum web layout width.
        layout_import_name: Import name of the generated layout file.
        architecture: Configured Flutter architecture.
        package_name: Flutter package name.
        use_package_imports: Whether to emit `package:` imports.
        state_management_type: Configured state management type.
        quiet_expected_fallback: Whether to silence expected fallback warnings.

    Returns:
        Updated mapping of relative project paths to file contents.
    """
    if not (context.generation and not context.skip_screen_post_reconcile):
        return planned_files

    renderer = DartRenderer()
    generation_cfg = context.settings.agent.generation

    patched_screen_code = reconcile_llm_screen_with_subtrees(
        context.generation.screen_code,
        subtree_result=subtree_result,
        planned_files=planned_files,
        clean_tree=context.clean_tree,
        uses_svg=uses_svg,
    )
    patched_screen_code = apply_safe_screen_code_patch(
        patched_screen_code,
        lambda code: inject_figma_keys_into_screen(code, context.clean_tree),
        label="Figma key injection",
    )
    layout_path = f"lib/generated/{context.resolved_feature}_layout.dart"
    layout_source = planned_files.get(layout_path)
    skip_layout_positioned_inject = (
        generation_cfg.use_screen_ir and context.generation.screen_ir is not None
    )
    if layout_source and not skip_layout_positioned_inject:
        layout_companion_sources = companion_dart_sources_for_layout_inject(
            planned_files,
            layout_path=layout_path,
            generation=context.generation,
        )
        patched_screen_code = apply_safe_screen_code_patch(
            patched_screen_code,
            lambda code: inject_missing_layout_positioned(
                code,
                layout_source,
                context.clean_tree,
                companion_sources=layout_companion_sources,
            ),
            label="layout Positioned injection",
        )
    if layout_source and context.clean_tree is not None:
        patched_screen_code = apply_safe_screen_code_patch(
            patched_screen_code,
            lambda code: apply_clean_tree_text_to_screen(code, context.clean_tree),
            label="clean-tree text sync",
        )
    patched_screen_code = apply_safe_screen_code_patch(
        patched_screen_code,
        ensure_screen_stack_paint_order,
        label="screen stack paint order",
    )
    if patched_screen_code != context.generation.screen_code:
        context.generation = context.generation.model_copy(
            update={"screen_code": patched_screen_code},
        )
        screen_extra_imports = widget_import_stems_for_screen(
            patched_screen_code,
            planned_files,
        )
        planned_files.update(
            renderer.render_generation_files(
                context.generation,
                feature_name=context.resolved_feature,
                uses_svg=uses_svg,
                use_auto_route=use_auto_route,
                responsive_enabled=responsive_shell,
                shell_safe_area=shell_safe_area,
                max_web_width=max_web_width,
                layout_import=layout_import_name,
                architecture=architecture,
                package_name=package_name,
                use_package_imports=use_package_imports,
                state_management_type=state_management_type,
                extra_widget_imports=screen_extra_imports or None,
                screen_only=True,
                quiet_expected_fallback=quiet_expected_fallback,
            )
        )
        planned_files = ensure_referenced_widget_imports(planned_files)
    return planned_files
