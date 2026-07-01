"""Acceptance evaluator for spec §23 criteria."""

from __future__ import annotations

import shutil
from typing import Any

from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.checks.validate import validate_generated_dart
from figma_flutter_agent.generator.dart.project_validation import validate_planned_dart_files
from figma_flutter_agent.schemas import FlutterGenerationResponse
from figma_flutter_agent.validation.spec23.assets import _criterion_asset_export
from figma_flutter_agent.validation.spec23.figma import _criterion_figma_connectivity
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult, Spec23Report
from figma_flutter_agent.validation.spec23.planning import (
    _criterion_flutter_optimization,
    _criterion_responsive_layouts,
    _plan_for_spec23,
)
from figma_flutter_agent.validation.spec23.preservation import (
    _criterion_developer_changes_preserved,
)
from figma_flutter_agent.validation.spec23.emit_contracts import (
    _criterion_emit_fidelity_contracts,
)
from figma_flutter_agent.validation.spec23.styles import _criterion_rest_css_synthesis


def evaluate_spec23(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str | None = None,
    package_name: str = "demo_app",
    generation: FlutterGenerationResponse | None = None,
    strict: bool = False,
) -> Spec23Report:
    """Evaluate section-23 acceptance criteria against a Figma frame fixture."""
    resolved_node_id = node_id or str(root["id"])
    mode = "llm-ir"
    criteria: list[Spec23CriterionResult] = [
        _criterion_figma_connectivity(strict=strict, settings=settings),
        _criterion_rest_css_synthesis(root, strict=strict),
    ]

    planned, tree = _plan_for_spec23(
        root,
        settings,
        node_id=resolved_node_id,
        package_name=package_name,
        generation=generation,
    )
    screen_key = next((path for path in planned if path.endswith("_screen.dart")), "")
    screen_source = planned.get(screen_key, "")
    layout_sources = "\n".join(
        content for path, content in planned.items() if path.endswith("_layout.dart")
    )
    if strict:
        responsive_layout_contract = (
            "LayoutBuilder" in screen_source
            or "LayoutBuilder" in layout_sources
            or "AppBreakpoints" in (screen_source + layout_sources)
            or "responsiveValue(" in (screen_source + layout_sources)
        )
        screen_routes_into_layout = bool(screen_key) and (
            "GeneratedScreenShell" in screen_source
            or "return const " in screen_source and "Layout();" in screen_source
            or "return " in screen_source and "Layout(" in screen_source
        )
        responsive_passed = screen_routes_into_layout
        responsive_passed = responsive_passed and responsive_layout_contract
        responsive_passed = responsive_passed and "textScalerOf(context)" in (
            screen_source + layout_sources
        )
    else:
        responsive_passed = bool(screen_key) and (
            "GeneratedScreenShell" in screen_source or "LayoutBuilder" in screen_source
        )
    criteria.append(
        Spec23CriterionResult(
            name="responsive_flutter_ui",
            passed=responsive_passed,
            detail=mode,
        )
    )
    widget_count = sum(1 for path in planned if path.startswith("lib/widgets/"))
    has_layout_delegate = any(
        path.startswith("lib/generated/") and path.endswith("_layout.dart") for path in planned
    )
    if strict:
        reusable_passed = widget_count >= 1 or has_layout_delegate
        reusable_detail = f"widgets={widget_count}; layout_delegate={has_layout_delegate}"
    else:
        reusable_passed = bool(planned) and (
            widget_count >= 1
            or has_layout_delegate
            or any(path.startswith("lib/features/") for path in planned)
        )
        reusable_detail = f"planned_files={len(planned)}"
    criteria.append(
        Spec23CriterionResult(
            name="reusable_widgets",
            passed=reusable_passed,
            detail=reusable_detail,
        )
    )
    theme_paths: tuple[str, ...] = (
        "lib/theme/app_colors.dart",
        "lib/theme/app_typography.dart",
        "lib/theme/app_spacing.dart",
    )
    if strict:
        theme_paths = (
            *theme_paths,
            "lib/theme/app_radius.dart",
            "lib/theme/app_elevation.dart",
            "lib/theme/app_theme.dart",
        )
    criteria.append(
        Spec23CriterionResult(
            name="design_system",
            passed=all(path in planned for path in theme_paths),
        )
    )

    criteria.append(_criterion_asset_export(root, strict=strict))
    criteria.append(_criterion_responsive_layouts(planned, strict=strict))
    criteria.append(_criterion_flutter_optimization(planned, tree, strict=strict))

    prod_passed = True
    prod_detail = mode
    try:
        validate_generated_dart(
            planned,
            tree,
            responsive_enabled=settings.agent.responsive.enabled,
            avoid_fixed_sizes=settings.agent.layout.avoid_fixed_sizes,
            require_reflow=settings.agent.responsive.require_reflow,
        )
    except GenerationError as exc:
        prod_passed = False
        prod_detail = str(exc)

    validation = settings.agent.validation
    if strict and validation.spec23_dart_analyze:
        analyze_ok, analyze_detail = validate_planned_dart_files(
            planned,
            package_name=package_name,
            require_dart_sdk=validation.require_dart_sdk,
            analyze_scope=validation.analyze_scope,
        )
        prod_passed = prod_passed and analyze_ok
        prod_detail = f"{prod_detail}; {analyze_detail}"
    elif strict and validation.require_dart_sdk and shutil.which("dart") is None:
        prod_passed = False
        prod_detail = f"{prod_detail}; dart SDK required (validation.require_dart_sdk)"

    criteria.append(
        Spec23CriterionResult(
            name="production_ready_code",
            passed=prod_passed,
            detail=prod_detail,
        )
    )

    criteria.append(_criterion_developer_changes_preserved(strict=strict))
    criteria.append(
        _criterion_emit_fidelity_contracts(
            tree,
            layout_sources,
            settings=settings,
            strict=strict,
        )
    )

    return Spec23Report(criteria=criteria, generation_mode=mode)


def evaluate_spec23_llm_path(
    root: dict[str, Any],
    settings: Settings,
    generation: FlutterGenerationResponse,
    *,
    node_id: str | None = None,
    package_name: str = "demo_app",
    strict: bool = True,
) -> Spec23Report:
    """Evaluate section-23 criteria using fixture-backed LLM screen output."""
    return evaluate_spec23(
        root,
        settings,
        node_id=node_id,
        package_name=package_name,
        generation=generation,
        strict=strict,
    )
