"""Batch screen manifest for multi-screen agent testing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruamel.yaml import YAML

from figma_flutter_agent.debug.paths import raw_dump_path
from figma_flutter_agent.generator.layout.common import to_snake_case


@dataclass(frozen=True)
class ScreenEntry:
    """One screen in a batch manifest."""

    feature: str
    node_id: str
    dump: Path | None = None
    figma_url: str | None = None


@dataclass(frozen=True)
class BatchManifest:
    """YAML manifest describing multiple Figma screens."""

    file_key: str
    project_dir: Path
    screens: tuple[ScreenEntry, ...]
    figma_file_url: str | None = None


def _normalize_node_id(raw: str) -> str:
    return raw.replace("-", ":")


def load_batch_manifest(path: Path) -> BatchManifest:
    """Load a batch manifest YAML file.

    Args:
        path: Path to ``screens.yaml`` (or similar).

    Returns:
        Parsed ``BatchManifest``.
    """
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"Batch manifest at {path} must be a mapping."
        raise ValueError(msg)
    manifest_dir = path.parent
    project_raw = payload.get("project_dir", ".")
    project_dir = Path(str(project_raw)).expanduser()
    if not project_dir.is_absolute():
        project_dir = (manifest_dir / project_dir).resolve()
    screens: list[ScreenEntry] = []
    for item in payload.get("screens", []):
        dump_path: Path | None = None
        if item.get("dump"):
            dump_raw = Path(str(item["dump"]))
            dump_path = dump_raw if dump_raw.is_absolute() else project_dir / dump_raw
        screens.append(
            ScreenEntry(
                feature=str(item["feature"]),
                node_id=_normalize_node_id(str(item["node_id"])),
                dump=dump_path,
                figma_url=item.get("figma_url"),
            )
        )
    return BatchManifest(
        file_key=str(payload["file_key"]),
        project_dir=project_dir,
        screens=tuple(screens),
        figma_file_url=payload.get("figma_file_url"),
    )


def default_dump_path(project_dir: Path, feature_name: str) -> Path:
    """Return the canonical raw dump path for ``feature_name``."""
    return raw_dump_path(project_dir, feature_name)


def write_batch_manifest(path: Path, manifest: BatchManifest) -> None:
    """Write a batch manifest YAML file.

    Args:
        path: Destination path (``screens.yaml``).
        manifest: Manifest to serialize.
    """
    yaml = YAML()
    yaml.default_flow_style = False
    screens: list[dict[str, str]] = []
    for screen in manifest.screens:
        item: dict[str, str] = {
            "feature": screen.feature,
            "node_id": screen.node_id,
        }
        if screen.dump is not None:
            try:
                item["dump"] = screen.dump.relative_to(manifest.project_dir).as_posix()
            except ValueError:
                item["dump"] = screen.dump.as_posix()
        screens.append(item)
    payload = {
        "file_key": manifest.file_key,
        "project_dir": ".",
        "screens": screens,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def find_screen_entry(manifest: BatchManifest, name: str) -> ScreenEntry:
    """Resolve a manifest screen by feature slug or fuzzy alias.

    Args:
        manifest: Loaded batch manifest.
        name: User input such as ``sign_in``, ``sign-in``, or ``Sign In``.

    Returns:
        Matching ``ScreenEntry``.

    Raises:
        ValueError: When the name is empty, unknown, or ambiguous.
    """
    query = to_snake_case(name.strip())
    if not query:
        msg = "Screen name is empty."
        raise ValueError(msg)

    for screen in manifest.screens:
        if screen.feature == query:
            return screen

    compact = query.replace("_", "")
    compact_matches = [
        screen for screen in manifest.screens if screen.feature.replace("_", "") == compact
    ]
    if len(compact_matches) == 1:
        return compact_matches[0]

    prefix_matches = [
        screen
        for screen in manifest.screens
        if screen.feature.startswith(query) or query.startswith(screen.feature)
    ]
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    if len(compact_matches) > 1 or len(prefix_matches) > 1:
        ambiguous = {screen.feature for screen in (*compact_matches, *prefix_matches)}
        msg = f"Ambiguous screen {name!r}; matches: {', '.join(sorted(ambiguous))}"
        raise ValueError(msg)

    known = ", ".join(screen.feature for screen in manifest.screens)
    msg = f"Unknown screen {name!r}. Available: {known}"
    raise ValueError(msg)


def merge_manifest_screens(
    existing: BatchManifest,
    new_screens: tuple[ScreenEntry, ...],
) -> BatchManifest:
    """Merge ``new_screens`` into ``existing``, replacing entries with the same ``node_id``.

    Args:
        existing: Current batch manifest.
        new_screens: Screen entries to insert or update.

    Returns:
        Merged manifest preserving unrelated existing screens.
    """
    new_by_node = {screen.node_id: screen for screen in new_screens}
    kept = [screen for screen in existing.screens if screen.node_id not in new_by_node]
    merged = tuple(kept + list(new_by_node.values()))
    return BatchManifest(
        file_key=existing.file_key,
        project_dir=existing.project_dir,
        screens=merged,
        figma_file_url=existing.figma_file_url,
    )


def remove_screens_from_manifest(
    path: Path,
    names: list[str],
    *,
    delete_dumps: bool = True,
) -> tuple[BatchManifest, tuple[str, ...]]:
    """Remove screens from a manifest by feature slug.

    Args:
        path: Path to ``screens.yaml``.
        names: Feature slugs or aliases accepted by ``find_screen_entry``.
        delete_dumps: When True, delete each removed screen dump file from disk.

    Returns:
        Updated manifest and removed feature slugs (deduplicated, sorted).

    Raises:
        ValueError: When ``names`` is empty or no screens matched.
    """
    if not names:
        msg = "At least one screen name is required."
        raise ValueError(msg)
    manifest = load_batch_manifest(path)
    to_remove: set[str] = set()
    for name in names:
        to_remove.add(find_screen_entry(manifest, name).feature)
    if not to_remove:
        msg = "No matching screens to remove."
        raise ValueError(msg)
    if delete_dumps:
        for screen in manifest.screens:
            if screen.feature in to_remove and screen.dump is not None and screen.dump.is_file():
                screen.dump.unlink()
    remaining = tuple(screen for screen in manifest.screens if screen.feature not in to_remove)
    updated = BatchManifest(
        file_key=manifest.file_key,
        project_dir=manifest.project_dir,
        screens=remaining,
        figma_file_url=manifest.figma_file_url,
    )
    write_batch_manifest(path, updated)
    return updated, tuple(sorted(to_remove))


def format_screen_list(manifest: BatchManifest, *, active: str | None = None) -> str:
    """Return a plain-text list of manifest screen feature names."""
    lines: list[str] = []
    if active is not None:
        lines.append(f"Active screen (main.dart): {active}")
    elif manifest.screens:
        lines.append("Active screen (main.dart): not set")
    for index, screen in enumerate(manifest.screens, start=1):
        marker = " *" if screen.feature == active else "  "
        lines.append(f"  {index}.{marker} {screen.feature}")
    return "\n".join(lines)
