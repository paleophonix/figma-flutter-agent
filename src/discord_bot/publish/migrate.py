"""Map generated sandbox files into repository paths."""

from __future__ import annotations

import shutil
from pathlib import Path

from discord_bot.config.models import CustomCodePolicy, TargetMode
from discord_bot.db.store import GenerationJob
from discord_bot.publish.policy import apply_custom_code_policy
from figma_flutter_agent.generator.paths import screen_file_path


def default_new_target_path(feature_slug: str) -> str:
    """Return the default new screen path for a feature slug."""
    return screen_file_path(feature_slug, architecture="feature_first")


def migrate_sandbox_to_repo(
    *,
    sandbox_dir: Path,
    repo_dir: Path,
    job: GenerationJob,
    custom_code_policy: CustomCodePolicy,
) -> dict[str, Path]:
    """Copy generated sandbox files into final repository-relative paths."""
    files: dict[str, Path] = {}
    lib_root = sandbox_dir / "lib"
    if not lib_root.is_dir():
        return files
    generated_dart = sorted(path for path in lib_root.rglob("*.dart") if path.is_file())
    if job.target_mode == TargetMode.EXISTING.value and job.target_file_path:
        primary_target = job.target_file_path.replace("\\", "/")
        screen_sources = [path for path in generated_dart if path.name.endswith("_screen.dart")]
        if screen_sources:
            target_abs = repo_dir / primary_target
            target_abs.parent.mkdir(parents=True, exist_ok=True)
            content = screen_sources[0].read_text(encoding="utf-8")
            merged = apply_custom_code_policy(
                policy=custom_code_policy,
                relative_path=primary_target,
                generated_content=content,
                existing_path=target_abs if target_abs.is_file() else None,
            )
            target_abs.write_text(merged, encoding="utf-8")
            files[primary_target] = target_abs
        for path in generated_dart:
            if "widgets" not in path.parts and path not in screen_sources:
                continue
            if "widgets" in path.parts:
                rel = str(Path("lib") / path.relative_to(lib_root)).replace("\\", "/")
            else:
                continue
            dest = repo_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.is_file():
                merged = apply_custom_code_policy(
                    policy=custom_code_policy,
                    relative_path=rel,
                    generated_content=path.read_text(encoding="utf-8"),
                    existing_path=dest,
                )
                dest.write_text(merged, encoding="utf-8")
            else:
                shutil.copy2(path, dest)
            files[rel] = dest
        return files

    feature_slug = job.feature_slug or "screen"
    target_rel = default_new_target_path(feature_slug)
    screen_sources = [path for path in generated_dart if path.name.endswith("_screen.dart")]
    if screen_sources:
        dest = repo_dir / target_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        merged = apply_custom_code_policy(
            policy=custom_code_policy,
            relative_path=target_rel,
            generated_content=screen_sources[0].read_text(encoding="utf-8"),
            existing_path=dest if dest.is_file() else None,
        )
        dest.write_text(merged, encoding="utf-8")
        files[target_rel] = dest
    for path in generated_dart:
        if path in screen_sources:
            continue
        rel = str(Path("lib") / path.relative_to(lib_root)).replace("\\", "/")
        dest = repo_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        files[rel] = dest
    assets_root = sandbox_dir / "assets"
    if assets_root.is_dir():
        for path in assets_root.rglob("*"):
            if not path.is_file():
                continue
            rel = str(Path("assets") / path.relative_to(assets_root)).replace("\\", "/")
            dest = repo_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            files[rel] = dest
    pubspec = sandbox_dir / "pubspec.yaml"
    if pubspec.is_file() and not (repo_dir / "pubspec.yaml").is_file():
        dest = repo_dir / "pubspec.yaml"
        shutil.copy2(pubspec, dest)
        files["pubspec.yaml"] = dest
    return files
