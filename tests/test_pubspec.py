from pathlib import Path

from figma_flutter_agent.generator.pubspec import (
    commit_pubspec_batch,
    read_pubspec_name,
    update_pubspec,
)


def test_read_pubspec_name_returns_package_name(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text("name: demo_app\n", encoding="utf-8")

    assert read_pubspec_name(tmp_path) == "demo_app"


def test_update_pubspec_merges_assets_and_dependency(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )

    batch = update_pubspec(tmp_path, ["assets/icons/", "assets/images/"])
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "flutter_svg" in content
    assert "assets/icons/" in content
    assert "assets/images/" in content

    batch = update_pubspec(tmp_path, ["assets/icons/"])
    commit_pubspec_batch(batch)
    second_pass = pubspec.read_text(encoding="utf-8")
    assert second_pass.count("assets/icons/") == 1


def test_update_pubspec_skips_flutter_svg_when_not_needed(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )

    batch = update_pubspec(tmp_path, ["assets/icons/"], needs_svg=False)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "flutter_svg" not in content
    assert "assets/icons/" in content


def test_update_pubspec_adds_go_router_when_requested(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )

    batch = update_pubspec(tmp_path, [], needs_go_router=True)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "go_router" in content


def test_update_pubspec_adds_auto_route_codegen_dev_dependencies(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
            ]
        ),
        encoding="utf-8",
    )

    batch = update_pubspec(tmp_path, [], needs_auto_route=True)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "auto_route" in content
    assert "build_runner" in content
    assert "auto_route_generator" in content


def test_update_pubspec_replaces_existing_font_family(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
                "  fonts:",
                "  - family: Helvetica Neue",
                "    fonts:",
                "    - asset: fonts/helvetica_neue_500.otf",
                "      weight: 500",
            ]
        ),
        encoding="utf-8",
    )
    from figma_flutter_agent.schemas import FontManifest, FontPubspecAsset, FontPubspecFamily

    manifest = FontManifest(
        families=[
            FontPubspecFamily(
                family="Helvetica Neue",
                fonts=[
                    FontPubspecAsset(asset="fonts/helvetica_neue_500.ttf", weight=500),
                    FontPubspecAsset(asset="fonts/helvetica_neue_700.ttf", weight=700),
                ],
            )
        ]
    )
    batch = update_pubspec(tmp_path, ["fonts/"], font_manifest=manifest)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "helvetica_neue_500.ttf" in content
    assert "helvetica_neue_700.ttf" in content
    assert "helvetica_neue_500.otf" not in content
    assert content.count("family: Helvetica Neue") == 1
    assert "fonts/" not in content.split("fonts:")[0]


def test_update_pubspec_strips_assets_fonts_when_fonts_section_merged(tmp_path: Path) -> None:
    pubspec = tmp_path / "pubspec.yaml"
    pubspec.write_text(
        "\n".join(
            [
                "name: demo_app",
                "dependencies:",
                "  flutter:",
                "    sdk: flutter",
                "flutter:",
                "  uses-material-design: true",
                "  assets:",
                "  - assets/icons/",
                "  - fonts/",
            ]
        ),
        encoding="utf-8",
    )
    from figma_flutter_agent.schemas import FontManifest, FontPubspecAsset, FontPubspecFamily

    manifest = FontManifest(
        families=[
            FontPubspecFamily(
                family="Helvetica Neue",
                fonts=[FontPubspecAsset(asset="fonts/helvetica_neue_500.ttf", weight=500)],
            )
        ]
    )
    batch = update_pubspec(tmp_path, ["fonts/"], font_manifest=manifest)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")
    assert "- fonts/" not in content
    assert "fonts/helvetica_neue_500.ttf" in content
