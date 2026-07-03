"""Cluster definition identity and shadow mapping (Program 04 P0-2)."""

from __future__ import annotations

from dataclasses import dataclass

from figma_flutter_agent.generator.widget_models import ClusterWidgetSpec


@dataclass(frozen=True, slots=True)
class DefinitionKey:
    """Authoritative cluster definition identity (topology-aware)."""

    cluster_id: str
    topology_variant: str
    representative_node_id: str

    @classmethod
    def from_spec(cls, spec: ClusterWidgetSpec, *, topology_variant: str = "default") -> DefinitionKey:
        """Build key from extraction spec and topology variant label."""
        rep = spec.representative.id if spec.representative else spec.cluster_id
        return cls(
            cluster_id=spec.cluster_id,
            topology_variant=topology_variant,
            representative_node_id=rep,
        )

    def legacy_cluster_id(self) -> str:
        """Legacy dict key — authoritative until 04-P0-2b."""
        return self.cluster_id


@dataclass(frozen=True, slots=True)
class DefinitionKeyShadowReport:
    """Parallel shadow mapping diagnostics (pre-authority)."""

    legacy_map: dict[str, str]
    shadow_map: dict[DefinitionKey, str]
    mismatches: tuple[tuple[str, str, str], ...]
    duplicate_shadow_keys: tuple[str, ...]


def build_legacy_cluster_classes(specs: list[ClusterWidgetSpec]) -> dict[str, str]:
    """Legacy last-wins cluster_id → class_name map (still authoritative pre-M2)."""
    return {spec.cluster_id: spec.class_name for spec in specs}


def build_shadow_definition_map(
    specs: list[ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str] | None = None,
) -> dict[DefinitionKey, str]:
    """Shadow topology-aware map — diagnostics only until 04-P0-2b."""
    topo = topology_by_cluster or {}
    result: dict[DefinitionKey, str] = {}
    for spec in specs:
        variant = topo.get(spec.cluster_id, "default")
        key = DefinitionKey.from_spec(spec, topology_variant=variant)
        result[key] = spec.class_name
    return result


def lookup_cluster_class_authoritative(
    shadow_map: dict[DefinitionKey, str],
    legacy_map: dict[str, str],
    *,
    key: DefinitionKey,
) -> str | None:
    """Return class name using DefinitionKey when M3 authority enabled, else legacy."""
    from figma_flutter_agent.compiler.m3_authority import m3_authority_enabled

    if m3_authority_enabled():
        return shadow_map.get(key)
    return legacy_map.get(key.legacy_cluster_id())


def compare_definition_key_shadow(
    specs: list[ClusterWidgetSpec],
    *,
    topology_by_cluster: dict[str, str] | None = None,
) -> DefinitionKeyShadowReport:
    """Compare legacy last-wins dict against shadow DefinitionKey map."""
    legacy = build_legacy_cluster_classes(specs)
    shadow = build_shadow_definition_map(specs, topology_by_cluster=topology_by_cluster)
    mismatches: list[tuple[str, str, str]] = []
    for spec in specs:
        variant = (topology_by_cluster or {}).get(spec.cluster_id, "default")
        key = DefinitionKey.from_spec(spec, topology_variant=variant)
        legacy_class = legacy.get(spec.cluster_id)
        shadow_class = shadow.get(key)
        if legacy_class != shadow_class:
            mismatches.append((spec.cluster_id, legacy_class or "", shadow_class or ""))
    seen: set[DefinitionKey] = set()
    duplicate_keys: list[str] = []
    for key in shadow:
        if key in seen:
            duplicate_keys.append(f"{key.cluster_id}:{key.topology_variant}")
        seen.add(key)
    return DefinitionKeyShadowReport(
        legacy_map=legacy,
        shadow_map=shadow,
        mismatches=tuple(mismatches),
        duplicate_shadow_keys=tuple(duplicate_keys),
    )
