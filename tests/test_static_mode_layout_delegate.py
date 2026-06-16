"""Static mode must delegate feature screens to deterministic layout widgets."""

from __future__ import annotations

from figma_flutter_agent.generator.ir.context import IrEmitContext
from figma_flutter_agent.generator.ir.tree import default_screen_ir
from figma_flutter_agent.generator.planned.reconcile import (
    _LARGE_PLANNED_DART_BYTES,
    force_static_mode_screens_to_layout,
)
from figma_flutter_agent.generator.planner.context import GenerationPlanContext
from figma_flutter_agent.generator.planner.ir_render import materialize_ir_generations
from figma_flutter_agent.schemas import (
    CleanDesignTreeNode,
    DesignTokens,
    FlutterGenerationResponse,
    NodeType,
)


def _static_settings():
    from figma_flutter_agent.config import Settings

    settings = Settings()
    return settings.model_copy(
        update={
            "agent": settings.agent.model_copy(
                update={
                    "responsive": settings.agent.responsive.model_copy(update={"mode": "static"}),
                }
            )
        }
    )


def test_materialize_ir_generations_static_mode_uses_layout_delegate_stub() -> None:
    child = CleanDesignTreeNode(
        id="2",
        name="Label",
        type=NodeType.TEXT,
        text="Reflow me",
    )
    root = CleanDesignTreeNode(
        id="1",
        name="Screen",
        type=NodeType.COLUMN,
        children=[child],
    )
    generation = FlutterGenerationResponse(screen_ir=default_screen_ir(root))
    context = GenerationPlanContext(
        settings=_static_settings(),
        clean_tree=root,
        tokens=DesignTokens(),
        resolved_feature="sleep",
        node_id="1",
        cluster_summary={},
        generation=generation,
    )
    updated = materialize_ir_generations(
        context,
        ir_emit_ctx=IrEmitContext(uses_svg=False, responsive_enabled=False, is_layout_root=True),
        use_auto_route=False,
        responsive_shell=False,
    )
    assert updated.generation is not None
    screen = updated.generation.screen_code or ""
    assert "const SleepLayout()" in screen
    assert "ListView" not in screen
    assert "Reflow me" not in screen


def test_force_static_mode_screens_to_layout_replaces_ir_reflow_body() -> None:
    padding = "x" * (_LARGE_PLANNED_DART_BYTES + 100)
    screen_path = "lib/features/sleep/sleep_screen.dart"
    layout_path = "lib/generated/sleep_layout.dart"
    planned = {
        screen_path: (
            f"class SleepScreen extends StatelessWidget {{ {padding} "
            "Widget build(BuildContext c) => ListView(children: [Text('x')]); }}"
        ),
        layout_path: (
            "class SleepLayout extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => Stack(children: []);\n"
            "}\n"
        ),
    }
    updated = force_static_mode_screens_to_layout(
        planned,
        package_name="demo_app",
        responsive_enabled=False,
    )
    screen = updated[screen_path]
    assert "ListView" not in screen
    assert "return const SleepLayout();" in screen
    assert "GeneratedScreenShell" not in screen
