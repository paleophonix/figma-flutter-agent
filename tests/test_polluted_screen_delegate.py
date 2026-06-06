"""Polluted LLM screens fall back to deterministic layout delegates."""

from __future__ import annotations

from figma_flutter_agent.generator.dart.syntax_repairs import (
    repair_broken_artboard_preview_declarations,
)
from figma_flutter_agent.generator.planned_dart import (
    _screen_needs_layout_delegate_fallback,
    force_polluted_feature_screens_to_layout,
)


def test_screen_needs_layout_delegate_fallback_detects_design_width() -> None:
    source = (
        "class ChatsScreen extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return SizedBox(width: designWidth, child: const Placeholder());\n"
        "  }\n"
        "}\n"
    )
    assert _screen_needs_layout_delegate_fallback(source) is True


def test_screen_needs_layout_delegate_fallback_skips_clean_delegate() -> None:
    source = (
        "class ChatsScreen extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return GeneratedScreenShell(child: const ChatsLayout());\n"
        "  }\n"
        "}\n"
    )
    assert _screen_needs_layout_delegate_fallback(source) is False


def test_force_polluted_feature_screens_to_layout() -> None:
    screen_path = "lib/features/chats/chats_screen.dart"
    layout_path = "lib/generated/chats_layout.dart"
    planned = {
        screen_path: (
            "class ChatsScreen extends StatelessWidget {\n"
            "  Widget build(BuildContext context) {\n"
            "    return SizedBox(width: designWidth, child: const Placeholder());\n"
            "  }\n"
            "}\n"
        ),
        layout_path: (
            "class ChatsLayout extends StatelessWidget {\n"
            "  @override\n"
            "  Widget build(BuildContext context) => Stack(children: const []);\n"
            "}\n"
        ),
    }
    updated = force_polluted_feature_screens_to_layout(
        planned,
        package_name="demo_app",
    )
    screen = updated[screen_path]
    assert "designWidth" not in screen
    assert "GeneratedScreenShell(child: const ChatsLayout())" in screen


def test_prepare_files_for_write_commit_strips_design_width(tmp_path) -> None:
    from figma_flutter_agent.generator.planned_dart import prepare_files_for_write_commit

    layout_path = tmp_path / "lib" / "generated" / "chats_layout.dart"
    layout_path.parent.mkdir(parents=True)
    layout_path.write_text(
        "class ChatsLayout extends StatelessWidget {\n"
        "  @override\n"
        "  Widget build(BuildContext context) => Stack(children: const []);\n"
        "}\n",
        encoding="utf-8",
    )
    screen_path = "lib/features/chats/chats_screen.dart"
    polluted = (
        "class ChatsScreen extends StatelessWidget {\n"
        "  Widget build(BuildContext context) {\n"
        "    return SizedBox(width: designWidth, child: const Placeholder());\n"
        "  }\n"
        "}\n"
    )
    prepared = prepare_files_for_write_commit(
        {screen_path: polluted},
        {screen_path: polluted},
        package_name="demo_app",
        project_dir=tmp_path,
    )
    assert "designWidth" not in prepared[screen_path]
    assert "GeneratedScreenShell(child: const ChatsLayout())" in prepared[screen_path]


def test_repair_broken_artboard_preview_declarations() -> None:
    broken = (
        "class DemoLayout extends StatelessWidget {\n"
        "  static final double _artboardPreviewWidth = "
        "double.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH');\n"
        "}\n"
    )
    repaired = repair_broken_artboard_preview_declarations(broken)
    assert "double.fromEnvironment" not in repaired
    assert "String.fromEnvironment('FIGMA_FLUTTER_ARTBOARD_PREVIEW_WIDTH')" in repaired
    assert "double.tryParse" in repaired
