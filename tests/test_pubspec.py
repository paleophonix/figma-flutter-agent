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
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "helvetica_neue_500.ttf").write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 252)
    (fonts_dir / "helvetica_neue_700.ttf").write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 252)

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


def test_update_pubspec_drops_stale_font_families_and_missing_files(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "assets" / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "helvetica_neue_500.otf").write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 252)

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
                "  - family: Gilroy",
                "    fonts:",
                "    - asset: assets/fonts/gilroy_600.ttf",
                "      weight: 600",
                "  - family: Helvetica Neue",
                "    fonts:",
                "    - asset: assets/fonts/helvetica_neue_500.otf",
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
                    FontPubspecAsset(asset="assets/fonts/helvetica_neue_500.otf", weight=500),
                    FontPubspecAsset(asset="assets/fonts/gilroy_600.ttf", weight=600),
                ],
            )
        ]
    )
    batch = update_pubspec(tmp_path, ["assets/icons/"], font_manifest=manifest)
    commit_pubspec_batch(batch)
    content = pubspec.read_text(encoding="utf-8")

    assert "Gilroy" not in content
    assert "gilroy_600" not in content
    assert "helvetica_neue_500.otf" in content
    assert content.count("- family:") == 1


def test_update_pubspec_strips_assets_fonts_when_fonts_section_merged(tmp_path: Path) -> None:
    fonts_dir = tmp_path / "fonts"
    fonts_dir.mkdir(parents=True)
    (fonts_dir / "helvetica_neue_500.ttf").write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 252)

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
