"""Load pipeline fetch state from cached Figma node dumps."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from figma_flutter_agent.errors import FlutterProjectError
from figma_flutter_agent.parser.prototype import collect_prototype_links, index_frames
from figma_flutter_agent.stages.fetch import FigmaFetchResult


@dataclass(frozen=True)
class DumpFrameMetadata:
    """Figma file/node identifiers resolved for an offline raw dump."""

    file_key: str
    node_id: str
    feature_name: str | None = None


def _feature_name_from_dump_filename(dump_path: Path) -> str | None:
    """Infer feature slug from dump path (v3 ``raw.json`` or v2 ``*_layout.json``)."""
    if dump_path.name == "raw.json" and dump_path.parent.name == "primary":
        return dump_path.parent.parent.name
    name = dump_path.name
    suffix = "_layout.json"
    if name.endswith(suffix) and len(name) > len(suffix):
        return name[: -len(suffix)]
    return None


def _resolve_existing_raw_dump_path(
    project_dir: Path,
    dump_path: Path,
    *,
    feature_name: str | None = None,
) -> Path:
    """Return an on-disk raw dump path, following v3 migration from v2 layouts."""
    resolved = dump_path.expanduser().resolve()
    if resolved.is_file():
        return resolved
    from figma_flutter_agent.debug.paths import resolve_raw_dump_path

    inferred = feature_name or _feature_name_from_dump_filename(resolved)
    if inferred is not None:
        migrated = resolve_raw_dump_path(project_dir, inferred)
        if migrated is not None:
            return migrated
    raise FlutterProjectError(f"Dump file not found: {resolved.as_posix()}")


def _node_id_from_dump_root(dump_path: Path) -> str | None:
    """Read the root Figma node id from serialized dump JSON."""
    try:
        payload = json.loads(dump_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_id = payload.get("id")
    if raw_id is None:
        return None
    return str(raw_id).replace("-", ":")


def resolve_frame_metadata_from_dump(
    project_dir: Path,
    dump_path: Path,
    *,
    feature_name: str | None = None,
) -> DumpFrameMetadata:
    """Resolve ``file_key`` and ``node_id`` for offline runs without ``--figma-url``.

    Resolution order:
    1. ``screens.yaml`` screen matched by ``feature_name``, dump path, or root node id.
    2. ``screens.yaml`` ``file_key`` + node id from dump JSON root.
    3. Node id from dump JSON only is not enough (``file_key`` is unknown).

    Args:
        project_dir: Flutter project root (may contain ``screens.yaml``).
        dump_path: Path to ``.debug/raw/<feature>_layout.json``.
        feature_name: Optional manifest feature slug override.

    Returns:
        Resolved identifiers for ``load_fetch_result_from_dump`` / ``parse_figma_url``.

    Raises:
        FlutterProjectError: When the dump file is missing or metadata cannot be resolved.
    """
    from figma_flutter_agent.batch.manifest import load_batch_manifest

    resolved_dump = _resolve_existing_raw_dump_path(
        project_dir,
        dump_path,
        feature_name=feature_name,
    )

    inferred_feature = feature_name or _feature_name_from_dump_filename(resolved_dump)
    node_from_json = _node_id_from_dump_root(resolved_dump)

    manifest_path = project_dir / "screens.yaml"
    if manifest_path.is_file():
        try:
            manifest = load_batch_manifest(manifest_path)
        except (OSError, ValueError) as exc:
            raise FlutterProjectError(
                f"Could not read screens.yaml at {manifest_path.as_posix()}: {exc}"
            ) from exc

        screen = _match_manifest_screen(
            manifest,
            dump_path=resolved_dump,
            feature_name=inferred_feature,
            node_id=node_from_json,
        )
        if screen is not None:
            return DumpFrameMetadata(
                file_key=manifest.file_key,
                node_id=screen.node_id,
                feature_name=screen.feature,
            )
        if node_from_json is not None:
            return DumpFrameMetadata(
                file_key=manifest.file_key,
                node_id=node_from_json,
                feature_name=inferred_feature,
            )

    if node_from_json is not None:
        raise FlutterProjectError(
            "Cannot resolve Figma file_key for --from-dump without screens.yaml in the "
            f"project ({project_dir.as_posix()}). Add a manifest or pass --figma-url."
        )

    raise FlutterProjectError(
        "Cannot resolve frame metadata from dump: missing screens.yaml match and no "
        f"\"id\" field in {resolved_dump.as_posix()}."
    )


def _match_manifest_screen(
    manifest,
    *,
    dump_path: Path,
    feature_name: str | None,
    node_id: str | None,
):
    """Return the best ``ScreenEntry`` for a dump path, or ``None``."""
    from figma_flutter_agent.batch.manifest import find_screen_entry
    from figma_flutter_agent.batch.run import _resolve_dump

    if feature_name:
        try:
            return find_screen_entry(manifest, feature_name)
        except ValueError:
            pass

    if node_id is not None:
        matched = [screen for screen in manifest.screens if screen.node_id == node_id]
        if len(matched) == 1:
            return matched[0]

    for screen in manifest.screens:
        if _resolve_dump(screen, manifest.project_dir).resolve() == dump_path:
            return screen

    return None


def is_processed_dump_payload(root: dict[str, object]) -> bool:
    """Return True when JSON is a parsed processed dump, not raw Figma frame JSON."""
    return "parserVersion" in root or ("cleanTree" in root and "tokens" in root)


def reject_processed_dump_payload(root: dict[str, object], dump_path: Path) -> None:
    """Raise when a processed dump is passed to the raw fetch loader.

    Args:
        root: Parsed JSON object from disk.
        dump_path: Path that was read (for the error message).

    Raises:
        FlutterProjectError: When the payload looks like a processed design-tree dump.
    """
    if not is_processed_dump_payload(root):
        return
    raise FlutterProjectError(
        f"Dump at {dump_path.as_posix()} is a processed design-tree snapshot "
        "(parserVersion/cleanTree), not raw Figma frame JSON. "
        "Use .debug/<feature>/primary/raw.json for --from-dump, "
        "or delete .debug/processed/ and re-run generate."
    )


def load_fetch_result_from_dump(
    dump_path: Path,
    *,
    file_key: str,
    node_id: str,
) -> FigmaFetchResult:
    """Build a ``FigmaFetchResult`` from a cached raw layout dump file.

    Args:
        dump_path: Path to serialized Figma frame document JSON (``.debug/raw/*``).
        file_key: Figma file key for metadata.
        node_id: Target node id (``page:frame``).

    Returns:
        Fetch result suitable for ``parse_figma_frame``.

    Raises:
        FlutterProjectError: When the file is a processed dump rather than raw Figma JSON.
    """
    root = json.loads(dump_path.read_text(encoding="utf-8"))
    if not isinstance(root, dict):
        msg = f"Dump at {dump_path} must contain a JSON object."
        raise ValueError(msg)
    reject_processed_dump_payload(root, dump_path)
    return FigmaFetchResult(
        file_key=file_key,
        node_id=node_id,
        root=root,
        variables_payload=None,
        published_styles={},
        components={},
        component_sets={},
        prototype_links=collect_prototype_links(root),
        frame_index=index_frames(root),
    )
