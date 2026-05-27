"""Tests for Dart import URI resolution."""

from figma_flutter_agent.generator.paths import ImportContext


def test_import_context_uses_package_uri_by_default() -> None:
    ctx = ImportContext(package_name="demo_app", source_file="lib/features/home/home_screen.dart")

    assert ctx.uri("theme/app_layout.dart") == "package:demo_app/theme/app_layout.dart"
    assert ctx.uri("generated/home_layout.dart") == "package:demo_app/generated/home_layout.dart"


def test_import_context_falls_back_to_relative_imports() -> None:
    ctx = ImportContext(
        package_name="demo_app",
        use_package_imports=False,
        source_file="lib/features/home/home_screen.dart",
    )

    assert ctx.uri("theme/app_layout.dart") == "../../theme/app_layout.dart"
    assert ctx.uri("widgets/card.dart") == "../../widgets/card.dart"
