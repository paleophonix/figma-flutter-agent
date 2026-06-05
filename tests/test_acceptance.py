"""Acceptance checks aligned with spec §23."""


def test_spec_connectivity_modules_exist() -> None:
    import figma_flutter_agent.figma.connector as connector_module
    import figma_flutter_agent.figma.url as url_module

    assert connector_module.FigmaConnector is not None
    assert url_module.parse_figma_url is not None


def test_spec_dev_mode_and_parser_modules_exist() -> None:
    import figma_flutter_agent.parser.styles as styles_module
    import figma_flutter_agent.parser.tree as tree_module

    assert styles_module.enrich_node_style is not None
    assert tree_module.build_clean_tree is not None


def test_spec_generation_and_theme_modules_exist() -> None:
    import figma_flutter_agent.generator.renderer as renderer_module
    import figma_flutter_agent.llm.client as llm_module

    assert renderer_module.DartRenderer is not None
    assert llm_module.create_llm_client is not None


def test_spec_asset_export_and_validation_modules_exist() -> None:
    import figma_flutter_agent.assets.exporter as exporter_module
    import figma_flutter_agent.generator.codegen_checks as checks_module

    assert exporter_module.AssetExporter is not None
    assert checks_module.validate_generated_dart is not None


def test_spec_e2e_fixture_generates_deterministic_layout() -> None:
    import json
    from pathlib import Path

    from figma_flutter_agent.generator.layout.renderer import render_layout_file
    from figma_flutter_agent.parser.tree import build_clean_tree

    root = json.loads(Path("tests/fixtures/figma_node_sample.json").read_text(encoding="utf-8"))
    tree, _, _, _ = build_clean_tree(root)
    layout = render_layout_file(tree, feature_name="onboarding", uses_svg=False)[
        "lib/generated/onboarding_layout.dart"
    ]

    assert "OnboardingLayout" in layout
    assert "MediaQuery.textScalerOf(context)" in layout
    assert "Column(" in layout


def test_spec_deterministic_screen_uses_layout() -> None:
    from figma_flutter_agent.generator.layout.renderer import render_deterministic_screen_files

    files = render_deterministic_screen_files(
        feature_name="onboarding",
        screen_class="OnboardingScreen",
        uses_svg=False,
        use_auto_route=False,
        responsive_enabled=True,
        max_web_width=480,
    )
    screen = files["lib/features/onboarding/onboarding_screen.dart"]

    assert "const OnboardingLayout()" in screen
    assert "import 'package:demo_app/generated/onboarding_layout.dart';" in screen
    assert "GeneratedScreenShell" in screen


def test_spec_incremental_sync_preserves_custom_code() -> None:
    from figma_flutter_agent.generator.writer import extract_custom_code, merge_custom_code

    existing = "// <custom-code>\nfinal custom = true;\n// </custom-code>\n"
    generated = "// <custom-code>\n// </custom-code>\nclass Generated {}"
    merged = merge_custom_code(generated, existing)

    assert "final custom = true;" in merged
    assert extract_custom_code(merged) == "final custom = true;"
