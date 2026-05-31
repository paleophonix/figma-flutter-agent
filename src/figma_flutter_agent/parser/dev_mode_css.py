"""Figma Dev Mode offline CSS dump reader and NodeStyle merge (Phase 2).

Dump format v1
--------------
The helper plugin (tools/figma_css_inspect/README.md) exports a JSON file with
this top-level shape::

    {
      "version": 1,
      "exportedAt": "<ISO-8601 timestamp>",
      "fileKey": "<figma-file-key>",
      "nodes": {
        "<nodeId>": {
          "name": "<layer name>",
          "css": {
            "<css-property>": "<value>",
            ...
          }
        },
        ...
      }
    }

Integration
-----------
When ``figma.dev_mode.inspect_css.mode == "plugin_dump"`` and a ``dump_path``
is provided, the pipeline loads the dump and calls
:func:`merge_dev_mode_css_into_style` on each node before codegen.  The merge
is *additive*: existing ``NodeStyle.css_properties`` values (from REST
synthesis) are preserved and the dump fills in gaps only.  In
``dev_mode_inspect`` source mode the dump values take precedence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Dump schema
# ---------------------------------------------------------------------------

DUMP_FORMAT_VERSION = 1

#: CSS properties extracted from the Figma inspect panel that the REST Styles
#: API does not expose reliably (e.g. composite shorthand values, clip-path).
_INSPECT_ONLY_PROPERTIES: frozenset[str] = frozenset(
    {
        "clip-path",
        "background-image",
        "backdrop-filter",
        "transform",
        "transition",
        "mix-blend-mode",
    }
)


@dataclass(frozen=True)
class DevModeCssNode:
    """Per-node entry from the dump (immutable)."""

    node_id: str
    name: str
    css: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class DevModeCssDump:
    """Full v1 dump loaded from disk."""

    version: int
    file_key: str
    exported_at: str
    nodes: dict[str, DevModeCssNode] = field(default_factory=dict)

    def get_node(self, node_id: str) -> DevModeCssNode | None:
        """Return the CSS node entry for *node_id*, or ``None`` if absent."""
        return self.nodes.get(node_id)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class DevModeCssDumpError(ValueError):
    """Raised when the dump file is missing, unreadable, or has an unknown format."""


def load_dev_mode_css_dump(path: str | Path) -> DevModeCssDump:
    """Load and validate a v1 CSS dump from *path*.

    Args:
        path: Path to the JSON dump file.

    Returns:
        Parsed :class:`DevModeCssDump` instance.

    Raises:
        DevModeCssDumpError: When the file does not exist, cannot be parsed,
            or has an unsupported ``version`` field.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise DevModeCssDumpError(
            f"Dev Mode CSS dump not found: {resolved}. "
            "Generate it with the figma-css-inspect plugin (tools/figma_css_inspect/)."
        )

    try:
        raw: dict[str, Any] = json.loads(resolved.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DevModeCssDumpError(
            f"Cannot parse Dev Mode CSS dump at {resolved}: {exc}"
        ) from exc

    version = raw.get("version")
    if version != DUMP_FORMAT_VERSION:
        raise DevModeCssDumpError(
            f"Unsupported Dev Mode CSS dump version {version!r}; expected {DUMP_FORMAT_VERSION}. "
            "Re-export from the figma-css-inspect plugin."
        )

    file_key: str = raw.get("fileKey", "")
    exported_at: str = raw.get("exportedAt", "")
    raw_nodes: dict[str, Any] = raw.get("nodes", {})

    nodes: dict[str, DevModeCssNode] = {}
    for node_id, entry in raw_nodes.items():
        if not isinstance(entry, dict):
            continue
        css = entry.get("css", {})
        if not isinstance(css, dict):
            css = {}
        nodes[node_id] = DevModeCssNode(
            node_id=node_id,
            name=str(entry.get("name", "")),
            css={str(k): str(v) for k, v in css.items()},
        )

    logger.debug(
        "Loaded Dev Mode CSS dump v{} ({} node(s), file_key={})",
        version,
        len(nodes),
        file_key or "<unknown>",
    )
    return DevModeCssDump(
        version=version,
        file_key=file_key,
        exported_at=exported_at,
        nodes=nodes,
    )


# ---------------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------------

def merge_dev_mode_css_into_style(
    existing_css: dict[str, str],
    dump_css: dict[str, str],
    *,
    override: bool = False,
) -> dict[str, str]:
    """Return a merged CSS-properties dict.

    Args:
        existing_css: CSS properties already present on ``NodeStyle``
            (from REST synthesis or previous enrichment).
        dump_css: CSS properties from the Dev Mode dump for this node.
        override: When ``True`` (``dev_mode_inspect`` source mode), dump
            values take precedence over existing ones.  When ``False``
            (``hybrid`` mode), existing values are kept and the dump only
            fills gaps.

    Returns:
        New merged dict; neither input is mutated.
    """
    if not dump_css:
        return existing_css
    if override:
        return {**existing_css, **dump_css}
    # hybrid / additive: existing values win
    return {**dump_css, **existing_css}


def apply_dump_to_node(
    node_id: str,
    existing_css: dict[str, str],
    dump: DevModeCssDump,
    *,
    override: bool = False,
) -> dict[str, str]:
    """Look up *node_id* in *dump* and merge its CSS into *existing_css*.

    Returns *existing_css* unchanged when *node_id* is not in the dump.
    """
    entry = dump.get_node(node_id)
    if entry is None:
        return existing_css
    return merge_dev_mode_css_into_style(existing_css, entry.css, override=override)


# ---------------------------------------------------------------------------
# Dump creation helpers (for tests / plugin stub)
# ---------------------------------------------------------------------------

def make_dump_dict(
    *,
    file_key: str = "",
    exported_at: str = "2026-01-01T00:00:00Z",
    nodes: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a valid v1 dump dict (used in tests and the plugin stub).

    Args:
        file_key: Figma file key.
        exported_at: ISO-8601 export timestamp.
        nodes: Mapping of ``nodeId`` → ``{"name": ..., "css": {...}}``.

    Returns:
        Dict ready to be serialised to JSON.
    """
    return {
        "version": DUMP_FORMAT_VERSION,
        "fileKey": file_key,
        "exportedAt": exported_at,
        "nodes": nodes or {},
    }
