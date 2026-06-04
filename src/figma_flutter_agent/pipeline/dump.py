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
    """Infer feature slug from ``<feature>_layout.json`` basename."""
    name = dump_path.name
    suffix = "_layout.json"
    if name.endswith(suffix) and len(name) > len(suffix):
        return name[: -len(suffix)]
    return None


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
        dump_path: Path to ``.figma_debug/raw/<feature>_layout.json``.
        feature_name: Optional manifest feature slug override.

    Returns:
        Resolved identifiers for ``load_fetch_result_from_dump`` / ``parse_figma_url``.

    Raises:
        FlutterProjectError: When the dump file is missing or metadata cannot be resolved.
    """
    from figma_flutter_agent.batch.manifest import find_screen_entry, load_batch_manifest

    resolved_dump = dump_path.expanduser().resolve()
    if not resolved_dump.is_file():
        raise FlutterProjectError(f"Dump file not found: {resolved_dump.as_posix()}")

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


def load_fetch_result_from_dump(
    dump_path: Path,
    *,
    file_key: str,
    node_id: str,
) -> FigmaFetchResult:
    """Build a ``FigmaFetchResult`` from a cached raw layout dump file.

    Args:
        dump_path: Path to serialized Figma frame document JSON (``.figma_debug/raw/*``).
        file_key: Figma file key for metadata.
        node_id: Target node id (``page:frame``).

    Returns:
        Fetch result suitable for ``parse_figma_frame``.
    """
    root = json.loads(dump_path.read_text(encoding="utf-8"))
    if not isinstance(root, dict):
        msg = f"Dump at {dump_path} must contain a JSON object."
        raise ValueError(msg)
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
