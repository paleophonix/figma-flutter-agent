"""Reconcile planned Dart files before analyze and write."""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from figma_flutter_agent.assets.screen_frame import sanitize_dart_blocked_assets
from figma_flutter_agent.generator.dart.postprocess import (
    discover_widgets_requiring_on_pressed,
    ensure_required_on_pressed_callbacks,
    process_generated_dart_source,
    sanitize_named_only_widget_calls,
)
from figma_flutter_agent.generator.figma_anchor import ensure_screen_stack_paint_order
from figma_flutter_agent.schemas import CleanDesignTreeNode, DesignTokens

# --------------------------------------------------------------------------- #
# Re-exports — public API unchanged                                            #
# --------------------------------------------------------------------------- #
from .ast_helpers import (
    _find_matching_brace,
    _find_matching_paren,
    _iter_top_level_brace_inners,
    _primary_public_widget_class_name,
    _strip_named_param_in_widget_calls,
    _widget_declares_param,
)
from .class_inspect import (
    _FLUTTER_SDK_WIDGET_CTORS,
    _WIDGET_CTOR_CALL_RE,
    _bare_widget_ctor_return_class,
    _build_contains_self_widget_ctor,
    _collect_widget_use_class_names,
    _dedupe_screen_class_definitions,
    _group_paths_by_class,
    _is_cluster_sibling_widget_delegate,
    _is_ctor_self_referential_widget_build,
    _is_foreign_delegate_widget_build,
    _is_self_referential_widget_build,
    _is_shrink_only_widget_source,
    _pick_canonical_widget_path,
    _planned_has_widget_consumers,
    _strip_nested_self_widget_ctors,
    _widget_build_snippet,
    _widget_class_build_bounds,
    _widget_class_build_header_match,
    _widget_class_decl_index,
    _widget_class_names_by_path,
    _widget_class_paths,
    consolidate_planned_widget_paths,
    ensure_planned_widget_manifest,
    find_missing_planned_widget_classes,
    reconcile_cluster_variant_args,
    transitively_referenced_widget_paths,
)
from .ctor_repair import (
    _constructor_decl_limit,
    _constructor_param_identity,
    _normalize_widget_constructor_param_segments,
    _replace_mangled_widget_constructor,
    _widget_constructor_needs_repair,
    sync_widget_class_constructors,
)
from .delegate import (
    _apply_oversized_layout_splits,
    _generated_layout_path_for_feature,
    _inject_artboard_preview_fields_if_missing,
    _layout_delegate_available,
    _layout_source_for_feature,
    _screen_is_layout_delegate,
    _screen_needs_layout_delegate_fallback,
    fallback_unparseable_screens_to_layout,
    force_oversized_feature_screens_to_layout,
    force_polluted_feature_screens_to_layout,
    force_static_mode_screens_to_layout,
    refresh_shrunk_and_delegate_planned_widgets,
    split_oversized_layout_dart,
)
from .delegate_repair import (
    _build_return_expression_site,
    _extract_build_return_expression,
    _foreign_delegate_target_class,
    _replace_build_return_expression,
    _replace_foreign_delegate_build,
    _replace_self_referential_build,
    _try_inline_foreign_delegate_build,
    _widget_body_is_inlinable_target,
    repair_foreign_delegate_widget_builds,
    repair_self_referential_widget_builds,
    repair_stale_widget_ctor_names_in_planned,
)
from .hydrate import (
    _any_widget_needs_disk_recovery,
    _hydrate_content_digest,
    _sanitize_ingested_widget_source,
    _stamp_hydrate_digest,
    _sync_widget_build_class_references,
    _widget_body_needs_recovery,
    absorb_disk_widget_alias_bodies,
    align_widget_class_with_file_stem,
    hydrate_planned_widget_files_from_project,
    prune_disk_widget_stem_aliases,
)
from .imports import (
    _LLM_WIDGET_IMPORT_COMMENT_RE,
    _RELATIVE_IMPORT_RE,
    _WIDGET_IMPORT_RE,
    _consumer_paths_needing_widget_imports,
    _insert_import_lines,
    _insert_missing_widget_imports,
    ensure_planned_widget_import_closure,
    ensure_referenced_widget_imports,
    ensure_widget_sibling_imports,
    filter_widget_import_stems,
    find_stale_widget_package_imports,
    redirect_widget_imports_to_canonical,
    strip_all_orphan_widget_imports_in_consumers,
    strip_ambiguous_widget_imports,
    strip_llm_relative_widget_imports,
    strip_orphan_widget_imports,
    strip_unused_widget_imports,
    sync_widget_consumer_imports,
    widget_import_stems_for_screen,
)
from .paths import (
    _LARGE_PLANNED_DART_BYTES,
    _PACKAGE_IMPORT_RE,
    _SDK_PACKAGE_NAMES,
    _dart_accepts_on_pressed_call_sites,
    _detect_package_name,
    _is_deterministic_widget_path,
    _is_generated_layout_path,
    _is_large_planned_dart,
    _is_widget_consumer_entry_path,
    _normalized_widget_stem,
    _path_skips_ast_reconcile,
    _scoped_ast_reconcile_paths,
    _skips_codegen_ast_pass,
    _skips_typography_collapse,
    _tree_has_layout_slots,
    _use_ast_sidecar_enabled,
    _widget_lib_path_for_class,
    canonicalize_planned_path_keys,
    planned_content_for_path,
    preferred_widget_path_for_class,
)
from .shell import (
    _default_generated_screen_shell,
    _extract_generated_screen_shell,
    _screen_shell_block_for_fallback,
)
from .syntax_repair import (
    _balance_planned_widget_delimiters,
    _sanitize_planned_dart_syntax,
    _sanitize_screen_dart_syntax,
    _sanitize_widget_dart_syntax,
    repair_planned_format_parse_failures,
    repair_planned_misplaced_text_style_params,
    sanitize_screen_emit_syntax,
)
from .widget_prune import (
    drop_unparseable_planned_widget_files,
    prune_duplicate_widget_classes,
    prune_unreferenced_planned_widgets,
    strip_inline_widget_duplicates_from_screen,
    strip_inline_widget_duplicates_from_screens,
)

_CLUSTER_VARIANT_PARAMS = ("isForward",)
_PROACTIVE_LAYOUT_DELEGATE_SCREEN_BYTES = 8_192


def prepare_files_for_write_commit(
    files_to_write: dict[str, str],
    planned_files: dict[str, str] | None,
    *,
    package_name: str = "demo_app",
    project_dir: Path | None = None,
    responsive_enabled: bool = True,
) -> dict[str, str]:
    """Refresh write payloads and pull in layout/screen when widget imports were reconciled."""
    import re

    if not planned_files:
        merged = dict(files_to_write)
    else:
        merged = dict(planned_files)
        merged.update(files_to_write)
    merged = force_static_mode_screens_to_layout(
        merged,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
    )
    merged = force_polluted_feature_screens_to_layout(
        merged,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        project_dir=project_dir,
    )
    if not planned_files:
        return {path: merged[path] for path in files_to_write if path in merged}

    synced = sync_widget_consumer_imports(merged, skip_consolidate=True)
    prepared = dict(files_to_write)
    for path in list(prepared):
        if path in synced:
            prepared[path] = synced[path]

    for path, content in synced.items():
        normalized = path.replace("\\", "/")
        if normalized.endswith("_layout.dart") or (
            normalized.startswith("lib/features/") and normalized.endswith("_screen.dart")
        ):
            prepared[path] = content

    class_paths = _widget_class_paths(synced)
    for path, content in synced.items():
        if not path.replace("\\", "/").startswith("lib/widgets/"):
            continue
        prepared[path] = content

    ensure_planned_widget_manifest(synced)

    for path, content in list(synced.items()):
        normalized = path.replace("\\", "/")
        if not (
            normalized.endswith("_layout.dart")
            or (normalized.startswith("lib/features/") and normalized.endswith("_screen.dart"))
        ):
            continue
        body = content
        for class_name, widget_path in class_paths.items():
            if re.search(rf"\b{re.escape(class_name)}\b", body):
                prepared[widget_path] = synced[widget_path]
    return prepared


def reconcile_planned_dart_files(
    planned: dict[str, str],
    *,
    blocked_asset_paths: frozenset[str] | None = None,
    use_ast_sidecar: bool | None = None,
    typography_tokens: DesignTokens | None = None,
    package_name: str = "demo_app",
    clean_tree: CleanDesignTreeNode | None = None,
    ast_full_reconcile_paths: frozenset[str] | None = None,
    incremental: bool | None = None,
    project_dir: Path | None = None,
    widget_suffix: str | None = None,
    uses_svg: bool | None = None,
    use_package_imports: bool = True,
    cluster_summary: dict[str, int] | None = None,
    cluster_min_count: int = 2,
    destination_trees: dict[str, CleanDesignTreeNode] | None = None,
    reconcile_metadata: dict[str, object] | None = None,
    responsive_enabled: bool = True,
) -> dict[str, str]:
    """Apply deterministic reconciliation and postprocess to planned Dart files."""
    from figma_flutter_agent.generator.app_typography_collapse import (
        collapse_inline_text_styles_to_app_typography,
    )

    ast_enabled = _use_ast_sidecar_enabled(use_ast_sidecar)
    ast_backends: set[str] = set()
    sidecar_skipped: set[str] = set()
    updated = force_polluted_feature_screens_to_layout(
        dict(planned),
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        project_dir=project_dir,
    )
    updated = _apply_oversized_layout_splits(updated)
    if incremental is None:
        incremental = True
    effective_ast_paths = (
        ast_full_reconcile_paths
        if ast_full_reconcile_paths is not None
        else _scoped_ast_reconcile_paths(updated)
    )
    logger.info(
        "reconcile_planned_dart_files starting ({} dart files, incremental={}, ast_scope={})",
        sum(1 for key in planned if key.endswith(".dart")),
        incremental,
        len(effective_ast_paths),
    )
    phase_t = time.monotonic()

    def _log_reconcile_phase(label: str, *, end: bool = False) -> None:
        nonlocal phase_t
        if not end:
            logger.info("Planned reconcile phase: {}", label)
            return
        elapsed = time.monotonic() - phase_t
        if elapsed >= 0.05:
            logger.info("Planned reconcile {} {:.2f}s", label, elapsed)
        phase_t = time.monotonic()

    if incremental:
        logger.info(
            "Planned Dart incremental reconcile (AST scope: {} path(s))",
            len(effective_ast_paths),
        )
    _log_reconcile_phase("cluster_variants")
    updated = reconcile_cluster_variant_args(updated)
    _log_reconcile_phase("cluster_variants", end=True)
    _log_reconcile_phase("consolidate_widgets")
    updated = consolidate_planned_widget_paths(updated)
    updated = prune_duplicate_widget_classes(updated)
    updated = repair_self_referential_widget_builds(updated)
    updated = repair_foreign_delegate_widget_builds(updated)
    updated = repair_stale_widget_ctor_names_in_planned(updated)
    _log_reconcile_phase("consolidate_widgets", end=True)
    if not incremental and _any_widget_needs_disk_recovery(updated):
        _log_reconcile_phase("hydrate_absorb")
        updated = hydrate_planned_widget_files_from_project(updated, project_dir)
        updated = absorb_disk_widget_alias_bodies(updated, project_dir)
        _log_reconcile_phase("hydrate_absorb", end=True)
        updated = prune_duplicate_widget_classes(updated)
        updated = repair_self_referential_widget_builds(updated)
        updated = repair_foreign_delegate_widget_builds(updated)
        updated = repair_stale_widget_ctor_names_in_planned(updated)
    elif not incremental:
        logger.info("Planned reconcile: skipping hydrate/absorb (widgets already complete)")
    if clean_tree is not None and cluster_summary and uses_svg is not None and widget_suffix:
        from figma_flutter_agent.generator.widget_extractor import (
            refresh_cluster_widget_planned_files,
        )

        _log_reconcile_phase("refresh_cluster")
        updated = refresh_cluster_widget_planned_files(
            updated,
            clean_tree=clean_tree,
            cluster_summary=cluster_summary,
            min_count=cluster_min_count,
            widget_suffix=widget_suffix,
            uses_svg=uses_svg,
            package_name=package_name,
            use_package_imports=use_package_imports,
            destination_trees=destination_trees,
        )
        updated = consolidate_planned_widget_paths(updated)
        _log_reconcile_phase("refresh_cluster", end=True)
    if clean_tree is not None and widget_suffix:
        from figma_flutter_agent.generator.subtree import (
            build_cluster_render_context,
            collect_subtree_widget_specs,
            refresh_subtree_widget_planned_files,
        )
        from figma_flutter_agent.generator.subtree.plan import (
            _collect_subtree_specs_to_render,
            _layout_widget_class_names,
        )

        specs = list(collect_subtree_widget_specs(clean_tree, widget_suffix=widget_suffix))
        layout_names = sorted(_layout_widget_class_names(updated))
        cluster_classes: dict[str, str] | None = None
        cluster_vector_variants: dict | None = None
        if cluster_summary and uses_svg is not None:
            cluster_classes, cluster_vector_variants = build_cluster_render_context(
                clean_tree,
                cluster_summary=cluster_summary,
                widget_suffix=widget_suffix,
                min_count=cluster_min_count,
                destination_trees=destination_trees,
            )
        if _collect_subtree_specs_to_render(
            updated,
            specs,
            layout_class_names=layout_names,
            clean_tree=clean_tree,
        ):
            _log_reconcile_phase("refresh_subtree")
            updated = refresh_subtree_widget_planned_files(
                updated,
                clean_tree=clean_tree,
                widget_suffix=widget_suffix,
                uses_svg=bool(uses_svg),
                package_name=package_name,
                use_package_imports=use_package_imports,
                cluster_classes=cluster_classes,
                cluster_vector_variants=cluster_vector_variants,
            )
            updated = consolidate_planned_widget_paths(updated)
            _log_reconcile_phase("refresh_subtree", end=True)
        else:
            logger.info("Planned reconcile: skipping refresh_subtree (widgets already valid)")
    _log_reconcile_phase("screen_dedupe")
    _log_reconcile_phase("strip_inline_widgets")
    updated = strip_inline_widget_duplicates_from_screens(updated)
    _log_reconcile_phase("strip_inline_widgets", end=True)
    _log_reconcile_phase("dedupe_screen_class")
    updated = _dedupe_screen_class_definitions(updated)
    _log_reconcile_phase("dedupe_screen_class", end=True)
    _log_reconcile_phase("balance_delimiters")
    updated = _balance_planned_widget_delimiters(updated)
    _log_reconcile_phase("balance_delimiters", end=True)
    _log_reconcile_phase("align_widget_stems")
    updated = align_widget_class_with_file_stem(updated)
    for path in list(updated.keys()):
        if path.startswith("lib/widgets/") and path.endswith(".dart"):
            synced = sync_widget_class_constructors(updated[path])
            if synced != updated[path]:
                updated[path] = synced
    _log_reconcile_phase("align_widget_stems", end=True)
    _log_reconcile_phase("prune_stale_widgets")
    updated = drop_unparseable_planned_widget_files(updated)
    updated = prune_unreferenced_planned_widgets(updated)
    updated = strip_all_orphan_widget_imports_in_consumers(updated)
    updated = repair_foreign_delegate_widget_builds(updated)
    updated = repair_self_referential_widget_builds(updated)
    _log_reconcile_phase("prune_stale_widgets", end=True)
    _log_reconcile_phase("sync_widget_imports")
    updated = sync_widget_consumer_imports(updated, skip_consolidate=True)
    _log_reconcile_phase("sync_widget_imports", end=True)
    _log_reconcile_phase("screen_dedupe", end=True)
    callback_widgets = discover_widgets_requiring_on_pressed(updated)
    blocked = blocked_asset_paths or frozenset()
    if ast_enabled:
        dart_file_count = sum(1 for key in updated if key.endswith(".dart"))
        logger.info(
            "Planned Dart reconcile starting ({} files; AST sidecar can take several minutes)",
            dart_file_count,
        )
    ast_started = time.monotonic()
    for path, content in updated.items():
        if not path.endswith(".dart"):
            continue
        if path.startswith("lib/widgets/"):
            content = sync_widget_class_constructors(content)
            from figma_flutter_agent.generator.dart.syntax_repairs import (
                strip_duplicate_key_after_super,
            )

            content = strip_duplicate_key_after_super(content)
        if path.startswith(("lib/", "test/")):
            sanitized = sanitize_dart_blocked_assets(content, blocked)
            include_text_scaler = not (
                path.startswith("lib/generated/") and path.endswith("_layout.dart")
            )
            normalized_path = path.replace("\\", "/")
            if normalized_path.startswith("test/capture/"):
                updated[path] = sanitized
                continue
            from figma_flutter_agent.generator.dart.postprocess import (
                repair_orphan_design_canvas_identifiers,
            )
            from figma_flutter_agent.generator.dart.syntax_repairs import (
                repair_broken_artboard_preview_declarations,
            )

            sanitized = repair_orphan_design_canvas_identifiers(sanitized)
            sanitized = repair_broken_artboard_preview_declarations(sanitized)
            if normalized_path.endswith("_screen.dart"):
                sanitized = _inject_artboard_preview_fields_if_missing(sanitized)
            run_full_ast = ast_enabled and normalized_path in effective_ast_paths
            if run_full_ast:
                file_started = time.monotonic()
                skip_ast = _skips_codegen_ast_pass(normalized_path, sanitized)
                if skip_ast:
                    if (
                        _is_generated_layout_path(normalized_path)
                        and _is_large_planned_dart(sanitized)
                        and clean_tree is not None
                        and _tree_has_layout_slots(clean_tree)
                    ):
                        sidecar_skipped.add(normalized_path)
                    processed = _sanitize_ingested_widget_source(
                        sanitized,
                        widget_path=normalized_path
                        if normalized_path.startswith("lib/widgets/")
                        else None,
                        package_name=package_name,
                    )
                else:
                    logger.info("AST sidecar: {}", normalized_path)
                    processed = process_generated_dart_source(
                        sanitized,
                        include_text_scaler=include_text_scaler,
                        use_ast_sidecar=True,
                        package_name=package_name,
                    )
                    ast_backends.add("subprocess")
                file_elapsed = time.monotonic() - file_started
                if file_elapsed >= 1.0 and not skip_ast:
                    logger.info("AST reconcile {:.1f}s: {}", file_elapsed, normalized_path)
            else:
                from figma_flutter_agent.generator.dart.postprocess import (
                    ensure_dart_ui_import,
                )

                if normalized_path.startswith("lib/widgets/"):
                    processed = _sanitize_ingested_widget_source(
                        sanitized,
                        widget_path=normalized_path,
                        package_name=package_name,
                    )
                elif not normalized_path.startswith("lib/features/"):
                    processed = ensure_dart_ui_import(sanitized)
                else:
                    from figma_flutter_agent.generator.dart.syntax_repairs import (
                        apply_llm_dart_syntax_repairs,
                    )

                    processed = ensure_dart_ui_import(apply_llm_dart_syntax_repairs(sanitized))
            if callback_widgets and _dart_accepts_on_pressed_call_sites(path):
                processed = ensure_required_on_pressed_callbacks(
                    processed,
                    widget_names=callback_widgets,
                )
                processed = sanitize_named_only_widget_calls(
                    processed,
                    widget_names=callback_widgets,
                )
            if (
                path.endswith("_screen.dart")
                and run_full_ast
                and not _skips_codegen_ast_pass(normalized_path, processed)
            ):
                from figma_flutter_agent.generator.dart.llm_codegen import (
                    apply_clean_tree_text_to_screen,
                    apply_safe_screen_code_patch,
                )

                processed = apply_safe_screen_code_patch(
                    processed,
                    ensure_screen_stack_paint_order,
                    label="screen stack paint order",
                )
                if clean_tree is not None:
                    from figma_flutter_agent.generator.layout.flex_reconcile import (
                        apply_flex_guards_from_tree,
                    )

                    processed = apply_safe_screen_code_patch(
                        processed,
                        lambda source: apply_flex_guards_from_tree(
                            apply_clean_tree_text_to_screen(source, clean_tree),
                            clean_tree,
                        ),
                        label="screen tree text and flex",
                    )
            if (
                typography_tokens is not None
                and path.endswith(".dart")
                and run_full_ast
                and not _skips_typography_collapse(normalized_path)
                and not _skips_codegen_ast_pass(normalized_path, processed)
            ):
                processed = collapse_inline_text_styles_to_app_typography(
                    processed,
                    typography_tokens,
                    package_name=package_name,
                )
            updated[path] = processed
    from figma_flutter_agent.generator.dart.llm_codegen import (
        repair_dart_delimiters,
        trim_surplus_dart_delimiters,
        validate_dart_delimiters,
    )

    for path, content in list(updated.items()):
        if not path.endswith(".dart"):
            continue
        normalized_path = path.replace("\\", "/")
        repaired = content
        if normalized_path.endswith("_screen.dart"):
            trimmed = trim_surplus_dart_delimiters(repaired)
            if trimmed is not None:
                repaired = trimmed
            repaired = sanitize_screen_emit_syntax(repaired)
            repaired = repair_dart_delimiters(repaired)
        elif validate_dart_delimiters(repaired) is not None:
            sanitized = _sanitize_planned_dart_syntax(path, repaired)
            if sanitized != repaired:
                repaired = sanitized
        if repaired != content:
            updated[path] = repaired
    if ast_enabled:
        if ast_backends:
            logger.info("AST sidecar reconcile backend(s): {}", ", ".join(sorted(ast_backends)))
        logger.info("Planned Dart reconcile finished in {:.1f}s", time.monotonic() - ast_started)
    missing_widgets = find_missing_planned_widget_classes(updated)
    for message in missing_widgets:
        logger.error("Planned widget manifest: {}", message)
    from figma_flutter_agent.generator.capture_screen_test import (
        refresh_capture_tests_in_planned,
    )

    updated = refresh_capture_tests_in_planned(updated, package_name=package_name)
    updated = force_static_mode_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
    )
    updated = force_polluted_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        project_dir=project_dir,
    )
    updated = force_oversized_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
        max_screen_bytes=_PROACTIVE_LAYOUT_DELEGATE_SCREEN_BYTES,
    )
    updated = force_oversized_feature_screens_to_layout(
        updated,
        package_name=package_name,
        responsive_enabled=responsive_enabled,
    )
    if reconcile_metadata is not None:
        reconcile_metadata["sidecar_skipped_paths"] = frozenset(sidecar_skipped)
    updated = repair_stale_widget_ctor_names_in_planned(updated)
    updated = repair_self_referential_widget_builds(updated)
    from figma_flutter_agent.generator.checks.text_scaler import remediate_text_scaler_contract

    updated = remediate_text_scaler_contract(updated)
    updated = sync_widget_consumer_imports(updated, skip_consolidate=True)
    ensure_planned_widget_import_closure(updated)
    return updated
