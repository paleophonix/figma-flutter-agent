"""Acceptance evaluator for spec §23 criteria."""

from __future__ import annotations

import asyncio
import inspect
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from figma_flutter_agent.assets.exporter import AssetExporter, collect_exportable_nodes
from figma_flutter_agent.config import Settings
from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.figma.connector import FigmaConnector
from figma_flutter_agent.generator.codegen_checks import validate_generated_dart
from figma_flutter_agent.generator.layout_common import to_snake_case
from figma_flutter_agent.generator.planner import (
    GenerationPlanContext,
    plan_from_figma_root,
    plan_generation_files,
)
from figma_flutter_agent.generator.validation import validate_planned_dart_files
from figma_flutter_agent.generator.writer import DartWriter, merge_custom_code
from figma_flutter_agent.parser.accessibility import apply_accessibility_fixes
from figma_flutter_agent.parser.styles import enrich_node_style
from figma_flutter_agent.parser.tokens import build_design_tokens
from figma_flutter_agent.parser.tree import build_clean_tree
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    FlutterGenerationResponse,
    NodeStyle,
    NodeType,
)


@dataclass
class Spec23CriterionResult:
    """Result for a single section-23 acceptance criterion."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class Spec23Report:
    """Aggregated section-23 acceptance report."""

    criteria: list[Spec23CriterionResult] = field(default_factory=list)
    generation_mode: str = "deterministic"

    @property
    def passed(self) -> bool:
        """Return True when every criterion passed."""
        return all(item.passed for item in self.criteria)


def _resolve_feature_name(root: dict[str, Any], settings: Settings) -> str:
    configured = settings.agent.naming.feature_name
    if configured != "auto":
        return to_snake_case(configured)
    return to_snake_case(str(root.get("name", "feature")))


def _criterion_figma_connectivity(
    *, strict: bool, settings: Settings | None = None
) -> Spec23CriterionResult:
    settings = settings or Settings()
    if strict:
        passed = (
            inspect.iscoroutinefunction(FigmaConnector.fetch_nodes)
            and inspect.iscoroutinefunction(FigmaConnector.__aenter__)
            and callable(getattr(FigmaConnector, "_request", None))
        )
        detail = "connector API surface (live fetch: use live-check / live_figma tests)"

        token = settings.figma_token().strip()
        file_key = settings.figma_smoke_file_key.strip()
        node_id = settings.figma_smoke_node_id.strip()
        if token and file_key and node_id:
            try:

                async def check_live() -> None:
                    async with FigmaConnector(token) as connector:
                        await connector.fetch_nodes(file_key, [node_id])

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    from concurrent.futures import ThreadPoolExecutor

                    with ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, check_live())
                        future.result()
                else:
                    asyncio.run(check_live())
                detail = f"connector API surface + live fetch OK ({node_id} in {file_key})"
            except Exception as exc:
                passed = False
                detail = f"live fetch failed: {exc}"
    else:
        # Non-strict: check if connector class is available and we can parse a URL
        from figma_flutter_agent.figma.url import parse_figma_url

        try:
            parse_figma_url("https://www.figma.com/file/ABC/test?node-id=1-1")
            passed = FigmaConnector is not None
            detail = "connector available"
        except Exception:
            passed = False
            detail = "URL parsing failed"
    return Spec23CriterionResult(name="figma_connectivity", passed=passed, detail=detail)


def _rest_style_from_fixture(root: dict[str, Any]) -> NodeStyle:
    """Return enriched style from the first node with REST-derived visual fields."""

    def walk(node: dict[str, Any]) -> NodeStyle | None:
        style = enrich_node_style(node, NodeStyle())
        if (
            style.background_color is not None
            or style.text_color is not None
            or style.border_radius is not None
            or style.font_size is not None
        ):
            return style
        for child in node.get("children") or []:
            if isinstance(child, dict):
                nested = walk(child)
                if nested is not None:
                    return nested
        return None

    return walk(root) or enrich_node_style(root, NodeStyle())


def _criterion_rest_css_synthesis(root: dict[str, Any], *, strict: bool) -> Spec23CriterionResult:
    """Validate REST-derived CSS-like properties (spec §5.1 strategy B — not Dev Mode API)."""
    tree, _, _, _ = build_clean_tree(root)
    if strict:
        frame_style = _rest_style_from_fixture(root)
        passed = bool(tree.children) and (
            frame_style.background_color is not None
            or frame_style.text_color is not None
            or frame_style.border_radius is not None
            or frame_style.font_size is not None
        )
        detail = (
            f"REST style synthesis background={frame_style.background_color is not None} "
            "(not Figma Dev Mode API; see README Notes & limitations)"
        )
    else:
        passed = bool(tree.children)
        detail = f"REST style synthesis (root={tree.name})"
    return Spec23CriterionResult(name="rest_css_synthesis", passed=passed, detail=detail)


def _criterion_developer_changes_preserved(*, strict: bool) -> Spec23CriterionResult:
    existing = (
        "// <auto-generated>\n"
        "class GeneratedScreen extends StatelessWidget {\n"
        "  const GeneratedScreen({super.key});\n"
        "}\n"
        "// </auto-generated>\n\n"
        "// <custom-code>\nfinal customFlag = true;\n// </custom-code>\n"
    )
    regenerated = (
        "// <auto-generated>\n"
        "class GeneratedScreen extends StatelessWidget {\n"
        "  const GeneratedScreen({super.key});\n"
        "}\n"
        "// </auto-generated>\n\n"
        "// <custom-code>\n// </custom-code>\n"
    )
    target = "lib/features/demo/demo_screen.dart"

    if not strict:
        merged = merge_custom_code(regenerated, existing)
        passed = "final customFlag = true;" in merged
        detail = "merge_custom_code"
        return Spec23CriterionResult(
            name="developer_changes_preserved",
            passed=passed,
            detail=detail,
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        project_dir = Path(tmp_dir)
        (project_dir / "pubspec.yaml").write_text("name: demo_app\n", encoding="utf-8")
        writer = DartWriter(project_dir, enable_backup=False)
        writer.write_files({target: existing})
        writer.write_files({target: regenerated})
        written = (project_dir / target).read_text(encoding="utf-8")
    passed = "final customFlag = true;" in written
    detail = "DartWriter regen"
    return Spec23CriterionResult(
        name="developer_changes_preserved",
        passed=passed,
        detail=detail,
    )


def _criterion_asset_export(root: dict[str, Any], *, strict: bool) -> Spec23CriterionResult:
    exportables = collect_exportable_nodes(root)
    if strict:
        passed = True
        detail = f"exportable_nodes={len(exportables)}"

        if exportables:
            # Mock connector to simulate real export without network
            mock_connector = MagicMock(spec=FigmaConnector)

            from figma_flutter_agent.assets.exporter import AssetExportOutcome
            from figma_flutter_agent.figma.connector import ImageUrlFetchResult

            async def mock_fetch_urls(*args: Any, **kwargs: Any) -> ImageUrlFetchResult:
                return ImageUrlFetchResult(
                    urls={
                        node_id: f"https://example.com/{node_id}.svg"
                        for node_id, _, _ in exportables
                    },
                    failed_node_ids=(),
                    rate_limited=False,
                )

            async def mock_download(*args: Any, **kwargs: Any) -> bytes:
                return b"<svg></svg>"

            mock_connector.fetch_image_urls = mock_fetch_urls
            mock_connector.download_bytes = mock_download

            exporter = AssetExporter(mock_connector)
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)

                async def run_export() -> AssetExportOutcome:
                    return await exporter.export_assets(
                        "dummy_key",
                        root,
                        project_dir,
                        svg_enabled=True,
                        png_scales=[1],
                    )

                try:
                    # Handle both sync and async environments
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None

                    if loop and loop.is_running():
                        # We are in an async loop (e.g. pytest-asyncio), use a thread pool
                        from concurrent.futures import ThreadPoolExecutor

                        with ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, run_export())
                            outcome = future.result()
                    else:
                        outcome = asyncio.run(run_export())

                    manifest = outcome.manifest
                    written_files = list(project_dir.glob("assets/**/*"))
                    # Verify that files were actually written
                    if not written_files or not manifest.entries:
                        passed = False
                        detail = f"{detail}; export failed (no files written)"
                    else:
                        detail = f"{detail}; verified export ({len(written_files)} files)"
                except Exception as exc:
                    passed = False
                    detail = f"{detail}; export error: {exc}"
    else:
        passed = isinstance(exportables, list)
        detail = f"exportable_nodes={len(exportables)}"
    return Spec23CriterionResult(name="asset_export", passed=passed, detail=detail)


def _tree_has_repaint_candidate(tree: CleanDesignTreeNode) -> bool:
    """Return True when the tree contains scrollable or heavy UI subtrees."""

    def walk(node: CleanDesignTreeNode) -> bool:
        if node.scroll_axis != "none":
            return True
        if node.type in {
            NodeType.GRID,
            NodeType.CAROUSEL,
            NodeType.TABS,
            NodeType.BOTTOM_NAV,
        }:
            return True
        return any(walk(child) for child in node.children)

    return walk(tree)


def _criterion_flutter_optimization(
    planned: dict[str, str],
    tree: CleanDesignTreeNode,
    *,
    strict: bool,
) -> Spec23CriterionResult:
    layout_sources = "\n".join(
        content for path, content in planned.items() if path.endswith("_layout.dart")
    )
    if not strict:
        passed = "RepaintBoundary" in layout_sources or not _tree_has_repaint_candidate(tree)
        return Spec23CriterionResult(
            name="flutter_optimization",
            passed=passed,
            detail="optional",
        )
    needs_boundary = _tree_has_repaint_candidate(tree)
    has_boundary = "RepaintBoundary" in layout_sources
    passed = has_boundary if needs_boundary else True
    detail = "repaint" if needs_boundary else "n/a"
    return Spec23CriterionResult(name="flutter_optimization", passed=passed, detail=detail)


def _criterion_responsive_layouts(
    planned: dict[str, str], *, strict: bool
) -> Spec23CriterionResult:
    layout_source = planned.get("lib/theme/app_layout.dart", "")
    if strict:
        passed = (
            "mobileSmallMax = 480" in layout_source
            and "mobileLargeMax = 768" in layout_source
            and "tabletMax = 1024" in layout_source
            and "isMobileSmall(double width)" in layout_source
            and "isMobileLarge(double width)" in layout_source
            and "isTablet(double width)" in layout_source
            and "isDesktop(double width) => width > tabletMax" in layout_source
            and "isWideLayout(double width)" in layout_source
        )
        detail = "spec 7.3 breakpoints (480/768/1024) + wide layout reflow"
    else:
        passed = "AppBreakpoints" in layout_source
        detail = ""
    return Spec23CriterionResult(name="responsive_layouts", passed=passed, detail=detail)


def _plan_for_spec23(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str,
    package_name: str,
    generation: FlutterGenerationResponse | None = None,
    use_deterministic_screen: bool | None = None,
) -> tuple[dict[str, str], CleanDesignTreeNode]:
    """Plan generated Dart for spec-23 evaluation."""
    if generation is None and use_deterministic_screen is None:
        planned = plan_from_figma_root(
            root,
            settings,
            node_id=node_id,
            package_name=package_name,
        )
        tree, _, _, _ = build_clean_tree(root)
        return planned, tree

    effective_settings = settings
    if use_deterministic_screen is not None:
        effective_settings = settings.with_deterministic_screen(
            use_deterministic_screen=use_deterministic_screen,
        )
    elif generation is not None:
        effective_settings = settings.with_deterministic_screen(use_deterministic_screen=False)

    tokens = build_design_tokens(root, None)
    tree, _, _, cluster_summary = build_clean_tree(root)
    if effective_settings.agent.accessibility.auto_fix:
        tree = apply_accessibility_fixes(tree)
    resolved_feature = _resolve_feature_name(root, effective_settings)
    planned = plan_generation_files(
        GenerationPlanContext(
            settings=effective_settings,
            clean_tree=tree,
            tokens=tokens,
            resolved_feature=resolved_feature,
            node_id=node_id,
            cluster_summary=cluster_summary,
            generation=generation,
            figma_root=root,
            package_name=package_name,
        )
    )
    return planned, tree


def evaluate_spec23(
    root: dict[str, Any],
    settings: Settings,
    *,
    node_id: str | None = None,
    package_name: str = "demo_app",
    generation: FlutterGenerationResponse | None = None,
    use_deterministic_screen: bool | None = None,
    strict: bool = False,
) -> Spec23Report:
    """Evaluate section-23 acceptance criteria against a Figma frame fixture.

    Args:
        root: Figma frame node dictionary.
        settings: Agent settings controlling generation mode.
        node_id: Optional node id override; defaults to ``root["id"]``.
        package_name: Flutter package name used for planned imports.
        generation: Optional LLM output for the non-deterministic generation path.
        use_deterministic_screen: Override deterministic screen planning when set.
        strict: When True, apply substantive gates instead of structural smoke checks.

    Returns:
        Report with one result per section-23 criterion.

    Raises:
        GenerationError: When production-ready codegen validation fails hard.
    """
    resolved_node_id = node_id or str(root["id"])
    mode = "llm" if generation is not None else "deterministic"
    if generation is None and use_deterministic_screen is None:
        use_deterministic_screen = True
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
        use_deterministic_screen=use_deterministic_screen,
    )
    screen_key = next((path for path in planned if path.endswith("_screen.dart")), "")
    screen_source = planned.get(screen_key, "")
    layout_sources = "\n".join(
        content for path, content in planned.items() if path.endswith("_layout.dart")
    )
    if strict:
        responsive_passed = bool(screen_key) and "GeneratedScreenShell" in screen_source
        responsive_passed = responsive_passed and (
            "LayoutBuilder" in screen_source or "LayoutBuilder" in layout_sources
        )
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
    """Evaluate section-23 criteria using fixture-backed LLM screen output.

    Args:
        root: Figma frame node dictionary.
        settings: Agent settings controlling generation mode.
        generation: Structured LLM codegen response.
        node_id: Optional node id override; defaults to ``root["id"]``.
        package_name: Flutter package name used for planned imports.

    Returns:
        Report with one result per section-23 criterion.

    Raises:
        GenerationError: When production-ready codegen validation fails hard.
    """
    return evaluate_spec23(
        root,
        settings,
        node_id=node_id,
        package_name=package_name,
        generation=generation,
        use_deterministic_screen=False,
        strict=strict,
    )
