"""Asset file writes and derivative formats."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.assets.effects import write_webp_copy
from figma_flutter_agent.assets.optimize import optimize_svg, svg_has_unsupported_filter
from figma_flutter_agent.schemas import AssetManifestEntry


class AssetFileDownloadMixin:
    async def _download_to_file(
        self, url: str, target: Path, *, optimize_svg_enabled: bool = False
    ) -> bool:
        """Download asset bytes to ``target``. Returns True when SVG has blur filters."""
        content = await self._connector.download_bytes(url)
        if optimize_svg_enabled and target.suffix.lower() == ".svg":
            decoded = content.decode("utf-8")
            target.write_text(optimize_svg(decoded), encoding="utf-8")
            return svg_has_unsupported_filter(decoded)
        target.write_bytes(content)
        return False


def rewrite_entries_to_webp(
    entries: list[AssetManifestEntry],
    *,
    project_dir: Path,
) -> list[AssetManifestEntry]:
    """Convert PNG image entries to WebP where possible and return rewritten entries."""
    updated_entries: list[AssetManifestEntry] = []
    for entry in entries:
        if entry.kind not in {"image", "illustration"}:
            updated_entries.append(entry)
            continue
        png_path = project_dir.joinpath(*entry.asset_path.split("/"))
        if not png_path.is_file():
            updated_entries.append(entry)
            continue
        webp_path = write_webp_copy(png_path)
        if webp_path is None:
            updated_entries.append(entry)
            continue
        updated_entries.append(
            AssetManifestEntry(
                node_id=entry.node_id,
                asset_path=entry.asset_path.replace(".png", ".webp"),
                kind=entry.kind,
            )
        )
    return updated_entries
