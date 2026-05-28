"""Safe pubspec.yaml updates for generated assets and dependencies."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from ruamel.yaml import YAML

from figma_flutter_agent.schemas import FontManifest, FontPubspecFamily


def _font_asset_path(project_dir: Path, asset: str) -> Path:
    return project_dir / Path(asset.replace("\\", "/"))


def _filter_font_families_on_disk(
    project_dir: Path,
    families: list[FontPubspecFamily],
) -> list[FontPubspecFamily]:
    """Keep only font files that exist under the project root."""
    filtered: list[FontPubspecFamily] = []
    for family in families:
        fonts = [
            font
            for font in family.fonts
            if _font_asset_path(project_dir, font.asset).is_file()
        ]
        if fonts:
            filtered.append(FontPubspecFamily(family=family.family, fonts=fonts))
    return filtered


@dataclass(frozen=True)
class PubspecUpdateBatch:
    """Pending pubspec update that can be committed or rolled back."""

    backup_path: Path
    pubspec_path: Path


def read_pubspec_name(project_dir: Path) -> str:
    """Read the Flutter package name from pubspec.yaml."""
    pubspec_path = project_dir / "pubspec.yaml"
    yaml = YAML()
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"Missing package name in {pubspec_path}")
    return name.strip()


def update_pubspec(
    project_dir: Path,
    asset_dirs: list[str],
    *,
    needs_svg: bool = True,
    needs_go_router: bool = False,
    needs_auto_route: bool = False,
    state_management_type: str = "none",
    font_manifest: FontManifest | None = None,
) -> PubspecUpdateBatch:
    """Merge flutter assets and optional dependencies into pubspec.yaml.

    Args:
        project_dir: Flutter project root containing pubspec.yaml.
        asset_dirs: Asset directory paths relative to project root.
        needs_svg: When True, ensure ``flutter_svg`` is present in dependencies.
        needs_go_router: When True, ensure ``go_router`` is present in dependencies.
        needs_auto_route: When True, ensure ``auto_route`` and codegen dev deps exist.
        state_management_type: Optional state backend dependency to inject.
        font_manifest: Optional bundled font families to merge into ``flutter.fonts``.

    Returns:
        Batch handle that must be committed or rolled back by the caller.
    """
    pubspec_path = project_dir / "pubspec.yaml"
    backup_dir = Path(tempfile.mkdtemp(prefix="figma-flutter-pubspec-backup-"))
    backup_path = backup_dir / "pubspec.yaml"
    shutil.copy2(pubspec_path, backup_path)

    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(pubspec_path.read_text(encoding="utf-8"))

    dependencies = data.setdefault("dependencies", {})
    if needs_svg and "flutter_svg" not in dependencies:
        dependencies["flutter_svg"] = "^2.0.10"
    if needs_go_router and "go_router" not in dependencies:
        dependencies["go_router"] = "^14.0.0"
    if needs_auto_route and "auto_route" not in dependencies:
        dependencies["auto_route"] = "^9.2.0"
    if state_management_type == "riverpod" and "flutter_riverpod" not in dependencies:
        dependencies["flutter_riverpod"] = "^2.6.1"
    if state_management_type == "bloc" and "flutter_bloc" not in dependencies:
        dependencies["flutter_bloc"] = "^9.1.0"
    if state_management_type == "provider" and "provider" not in dependencies:
        dependencies["provider"] = "^6.1.2"

    if needs_auto_route:
        dev_dependencies = data.setdefault("dev_dependencies", {})
        if "build_runner" not in dev_dependencies:
            dev_dependencies["build_runner"] = "^2.4.0"
        if "auto_route_generator" not in dev_dependencies:
            dev_dependencies["auto_route_generator"] = "^9.0.0"

    flutter_section = data.setdefault("flutter", {})
    assets = flutter_section.setdefault("assets", [])
    existing = set(str(item) for item in assets)
    for asset_dir in asset_dirs:
        normalized = asset_dir if asset_dir.endswith("/") else f"{asset_dir}/"
        if normalized not in existing:
            assets.append(normalized)
            existing.add(normalized)

    if font_manifest is not None and font_manifest.families:
        families_on_disk = _filter_font_families_on_disk(project_dir, list(font_manifest.families))
        fonts_section: list[dict[str, object]] = []
        for family_entry in families_on_disk:
            fonts_section.append(
                {
                    "family": family_entry.family,
                    "fonts": [
                        {
                            "asset": font.asset,
                            "weight": font.weight,
                            **({"style": font.style} if font.style else {}),
                        }
                        for font in family_entry.fonts
                    ],
                }
            )
        flutter_section["fonts"] = fonts_section
        # Flutter loads font files via flutter.fonts; duplicating assets/fonts/ here breaks web.
        assets = flutter_section.get("assets")
        if isinstance(assets, list):
            flutter_section["assets"] = [
                item
                for item in assets
                if str(item).replace("\\", "/").rstrip("/") not in ("assets/fonts", "fonts")
            ]

    with pubspec_path.open("w", encoding="utf-8") as handle:
        yaml.dump(data, handle)

    return PubspecUpdateBatch(backup_path=backup_path, pubspec_path=pubspec_path)


def commit_pubspec_batch(batch: PubspecUpdateBatch | None) -> None:
    """Delete pubspec backup after validation succeeds."""
    if batch is None:
        return
    shutil.rmtree(batch.backup_path.parent, ignore_errors=True)


def rollback_pubspec_batch(batch: PubspecUpdateBatch | None) -> None:
    """Restore pubspec.yaml from backup after validation failure."""
    if batch is None:
        return
    shutil.copy2(batch.backup_path, batch.pubspec_path)
    shutil.rmtree(batch.backup_path.parent, ignore_errors=True)
    logger.info("Restored pubspec.yaml from backup")
