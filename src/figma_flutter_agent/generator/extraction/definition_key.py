"""Cluster definition identity and shadow mapping (Program 04 P0-2)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.compiler.m3_authority import route_enforce_enabled
from figma_flutter_agent.compiler.m3_policy import DEFAULT_M3_POLICY, M3Policy
from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec


@dataclass(frozen=True, slots=True)
class DefinitionKey:
    """Authoritative cluster definition identity (topology-aware)."""

    cluster_id: str
    topology_variant: str
    representative_node_id: str

    @classmethod
    def from_spec(cls, spec: ClusterWidgetSpec, *, topology_variant: str | None = None) -> DefinitionKey:
        """Build key from extraction spec and variant label."""
        rep = spec.representative.id if spec.representative else spec.cluster_id
        variant = topology_variant if topology_variant is not None else rep
        return cls(
            cluster_id=spec.cluster_id,
            topology_variant=variant,
            representative_node_id=rep,
        )

    def legacy_cluster_id(self) -> str:
        """Legacy dict key — authoritative until 04-P0-2b."""
        return self.cluster_id


def topology_variant_for_spec(spec: ClusterWidgetSpec) -> str:
    """Variant label keyed by representative node id (not cluster_id last-wins)."""
    if spec.representative is None:
        return spec.cluster_id
    return spec.representative.id


@dataclass(frozen=True, slots=True)
class DefinitionKeyShadowReport:
    """Parallel shadow mapping diagnostics (pre-authority)."""

    legacy_map: dict[str, str]
    shadow_map: dict[DefinitionKey, str]
    mismatches: tuple[tuple[str, str, str], ...]
    duplicate_shadow_keys: tuple[str, ...]
    duplicate_body_keys: tuple[str, ...]
    duplicate_class_names: tuple[str, ...]


def build_legacy_cluster_classes(specs: list[ClusterWidgetSpec]) -> dict[str, str]:
    """Legacy last-wins cluster_id → class_name map (still authoritative pre-M2)."""
    return {spec.cluster_id: spec.class_name for spec in specs}


def _duplicate_class_names(specs: list[ClusterWidgetSpec]) -> tuple[str, ...]:
    by_name: dict[str, list[ClusterWidgetSpec]] = {}
    for spec in specs:
        by_name.setdefault(spec.class_name, []).append(spec)
    return tuple(name for name, items in sorted(by_name.items()) if len(items) > 1)


def build_shadow_definition_map(
    specs: list[ClusterWidgetSpec],
) -> tuple[dict[DefinitionKey, str], tuple[str, ...], tuple[str, ...]]:
    """Build shadow map with pre-dict collision validation."""
    entries: list[tuple[DefinitionKey, str]] = []
    duplicate_keys: list[str] = []
    duplicate_bodies: list[str] = []
    for spec in specs:
        key = DefinitionKey.from_spec(spec, topology_variant=topology_variant_for_spec(spec))
        for existing_key, existing_class in entries:
            if existing_key == key and existing_class != spec.class_name:
                duplicate_bodies.append(f"{key.cluster_id}:{key.topology_variant}")
            elif (
                existing_key.cluster_id == key.cluster_id
                and existing_key.topology_variant == key.topology_variant
                and existing_key != key
            ):
                duplicate_keys.append(f"{key.cluster_id}:{key.topology_variant}")
        entries.append((key, spec.class_name))
    return dict(entries), tuple(duplicate_keys), tuple(duplicate_bodies)


def lookup_cluster_class_authoritative(
    shadow_map: dict[DefinitionKey, str],
    legacy_map: dict[str, str],
    *,
    key: DefinitionKey,
    policy: M3Policy = DEFAULT_M3_POLICY,
) -> str | None:
    """Return class name using DefinitionKey when route enforce enabled, else legacy."""
    if route_enforce_enabled("definition_key", policy):
        return shadow_map.get(key)
    return legacy_map.get(key.legacy_cluster_id())


def compare_definition_key_shadow(
    specs: list[ClusterWidgetSpec],
) -> DefinitionKeyShadowReport:
    """Compare legacy last-wins dict against shadow DefinitionKey map."""
    legacy = build_legacy_cluster_classes(specs)
    shadow, duplicate_keys, duplicate_bodies = build_shadow_definition_map(specs)
    mismatches: list[tuple[str, str, str]] = []
    for spec in specs:
        key = DefinitionKey.from_spec(spec, topology_variant=topology_variant_for_spec(spec))
        legacy_class = legacy.get(spec.cluster_id)
        shadow_class = shadow.get(key)
        if legacy_class != shadow_class:
            mismatches.append((spec.cluster_id, legacy_class or "", shadow_class or ""))
    return DefinitionKeyShadowReport(
        legacy_map=legacy,
        shadow_map=shadow,
        mismatches=tuple(mismatches),
        duplicate_shadow_keys=duplicate_keys,
        duplicate_body_keys=duplicate_bodies,
        duplicate_class_names=_duplicate_class_names(specs),
    )
