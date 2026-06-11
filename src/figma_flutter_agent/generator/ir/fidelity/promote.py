"""Offline manifest promotion from golden/signoff evidence (EPIC 4.5)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from figma_flutter_agent.errors import GenerationError
from figma_flutter_agent.generator.ir.fidelity.manifest import (
    ManifestEntry,
    load_fidelity_manifest,
    package_fidelity_manifest_path,
)
from figma_flutter_agent.schemas import FidelityTier, WidgetIrKind


@dataclass(frozen=True)
class PromotionRequest:
    """Inputs for a manifest promotion operation."""

    kind: WidgetIrKind
    tier: FidelityTier
    fixture_id: str
    feature_profile: str = "material"
    template_version: str = "1"
    epsilon: float | None = 0.02
    manifest_path: Path | None = None


@dataclass(frozen=True)
class PromotionResult:
    """Outcome of a manifest promotion."""

    manifest_path: Path
    dry_run: bool
    entry: ManifestEntry


def _known_fixture_ids() -> set[str]:
    from figma_flutter_agent.fixtures.screens_manifest import load_screens_manifest

    manifest = load_screens_manifest()
    ids: set[str] = set()
    for screen in manifest.screens:
        ids.add(screen.id)
        if screen.golden_id:
            ids.add(screen.golden_id)
    return ids


def validate_manifest_entries(manifest_path: Path | None = None) -> list[str]:
    """Validate shipped fidelity manifest invariants for signoff."""
    manifest = load_fidelity_manifest(manifest_path)
    errors: list[str] = []
    for entry in manifest.entries:
        if entry.default_tier == FidelityTier.NATIVE_VERIFIED and not entry.fixture_ids:
            errors.append(
                f"native_verified kind {entry.kind.value} missing fixture_ids "
                f"(profile={entry.feature_profile}, version={entry.template_version})",
            )
    return errors


def promote_manifest_entry(request: PromotionRequest, *, dry_run: bool = False) -> PromotionResult:
    """Promote or update one manifest entry with runtime signoff metadata."""
    if request.fixture_id not in _known_fixture_ids():
        msg = (
            f"fixture_id {request.fixture_id!r} not found in tests/fixtures/screens.yaml "
            "golden corpus"
        )
        raise GenerationError(msg)

    target = request.manifest_path or package_fidelity_manifest_path()
    entry = ManifestEntry(
        kind=request.kind,
        feature_profile=request.feature_profile,
        template_version=request.template_version,
        default_tier=request.tier,
        fixture_ids=(request.fixture_id,),
        epsilon=request.epsilon,
    )

    if dry_run:
        return PromotionResult(manifest_path=target, dry_run=True, entry=entry)

    raw = _load_or_create_manifest_document(target)
    entries = [row for row in raw.get("entries") or [] if isinstance(row, dict)]
    entries = [
        row
        for row in entries
        if not (
            row.get("kind") == request.kind.value
            and str(row.get("feature_profile", "material")) == request.feature_profile
            and str(row.get("template_version", "1")) == request.template_version
        )
    ]
    entries.append(
        {
            "kind": request.kind.value,
            "feature_profile": request.feature_profile,
            "template_version": request.template_version,
            "default_tier": request.tier.value,
            "fixture_ids": [request.fixture_id],
            "epsilon": request.epsilon,
            "tier_source": "runtime_signoff",
        },
    )
    raw["entries"] = entries
    if "kinds" in raw:
        del raw["kinds"]
    _write_manifest_document(target, raw)
    return PromotionResult(manifest_path=target, dry_run=False, entry=entry)


def _load_or_create_manifest_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "default_tier": "native_unverified",
            "template_version": "1",
            "default_feature_profile": "material",
            "entries": [],
        }
    loader = YAML(typ="safe")
    payload = loader.load(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return payload
    return {}


def _write_manifest_document(path: Path, payload: dict[str, Any]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)
