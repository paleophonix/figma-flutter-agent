"""Shared fingerprint baseline utilities for codex enforcement lint gates."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

CONTEXT_LINES = 3


@dataclass(frozen=True)
class ViolationFingerprint:
    """Stable identity for one lint violation occurrence."""

    path: str
    snippet_hash: str
    category: str
    owner_epic: str

    @property
    def key(self) -> str:
        return f"{self.path}|{self.snippet_hash}|{self.category}"

    @property
    def identity(self) -> tuple[str, str]:
        """Category + snippet hash pair used to detect relocation."""
        return (self.category, self.snippet_hash)

    def format_line(self) -> str:
        return f"{self.path} | {self.snippet_hash} | {self.category} | {self.owner_epic}"


@dataclass(frozen=True)
class FingerprintComparison:
    """Result of comparing current violations against a fingerprint baseline."""

    added: tuple[str, ...]
    removed: tuple[str, ...]
    relocated: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.added and not self.relocated


def normalize_snippet(text: str, match_start: int, *, context_lines: int = CONTEXT_LINES) -> str:
    """Normalize a source window around ``match_start`` for stable hashing."""
    lines = text.splitlines()
    line_no = text.count("\n", 0, match_start)
    lo = max(0, line_no - context_lines)
    hi = min(len(lines), line_no + context_lines + 1)
    chunk = "\n".join(line.strip() for line in lines[lo:hi])
    return re.sub(r"\s+", " ", chunk).strip()


def snippet_hash(normalized: str) -> str:
    """Return a short stable hash for a normalized snippet."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]


def load_fingerprint_baseline(path: Path) -> dict[str, ViolationFingerprint]:
    """Load allowlisted violation fingerprints from a baseline file."""
    if not path.is_file():
        return {}
    baseline: dict[str, ViolationFingerprint] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            continue
        entry = ViolationFingerprint(
            path=parts[0],
            snippet_hash=parts[1],
            category=parts[2],
            owner_epic=parts[3],
        )
        baseline[entry.key] = entry
    return baseline


def write_fingerprint_baseline(
    fingerprints: list[ViolationFingerprint],
    path: Path,
) -> None:
    """Write stable violation fingerprints to the baseline ratchet file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    unique = {item.key: item for item in fingerprints}
    lines = [
        "# path | normalized_snippet_hash | category | owner_epic",
        *(unique[key].format_line() for key in sorted(unique)),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def compare_fingerprints(
    baseline: dict[str, ViolationFingerprint],
    current: list[ViolationFingerprint],
) -> FingerprintComparison:
    """Compare current violations to baseline; detect add/remove/relocate."""
    current_map = {item.key: item for item in current}
    baseline_keys = set(baseline)
    current_keys = set(current_map)

    added = sorted(current_keys - baseline_keys)
    removed = sorted(baseline_keys - current_keys)

    baseline_identities = {
        item.identity: item.path for item in baseline.values()
    }
    relocated: list[str] = []
    for key in added:
        item = current_map[key]
        baseline_path = baseline_identities.get(item.identity)
        if baseline_path is not None and baseline_path != item.path:
            relocated.append(key)

    return FingerprintComparison(
        added=tuple(added),
        removed=tuple(removed),
        relocated=tuple(sorted(relocated)),
    )


def write_burndown_report(
    *,
    baseline: dict[str, ViolationFingerprint],
    current: list[ViolationFingerprint],
    output_path: Path,
    comparison: FingerprintComparison | None = None,
) -> dict[str, object]:
    """Write PR burn-down artifact for grandfathered lint debt."""
    resolved = comparison or compare_fingerprints(baseline, current)
    current_map = {item.key: item for item in current}
    by_module = Counter(item.path.split("/")[0] for item in current_map.values())
    payload: dict[str, object] = {
        "baselineCount": len(baseline),
        "currentCount": len(current_map),
        "removed": list(resolved.removed),
        "added": list(resolved.added),
        "relocated": list(resolved.relocated),
        "removedCount": len(resolved.removed),
        "addedCount": len(resolved.added),
        "relocatedCount": len(resolved.relocated),
        "fingerprint_ok": resolved.ok,
        "byModule": dict(sorted(by_module.items())),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def gate_exit_code(
    comparison: FingerprintComparison,
    *,
    gate_name: str,
) -> tuple[int, list[str]]:
    """Return exit code and human-readable failure lines for a fingerprint gate."""
    errors: list[str] = []
    if comparison.added:
        errors.append(f"{gate_name}: {len(comparison.added)} new fingerprint(s) outside baseline")
        errors.extend(f"  added: {key}" for key in comparison.added[:20])
        if len(comparison.added) > 20:
            errors.append(f"  ... and {len(comparison.added) - 20} more")
    if comparison.relocated:
        errors.append(f"{gate_name}: {len(comparison.relocated)} relocated fingerprint(s)")
        errors.extend(f"  relocated: {key}" for key in comparison.relocated[:20])
        if len(comparison.relocated) > 20:
            errors.append(f"  ... and {len(comparison.relocated) - 20} more")
    return (1 if errors else 0, errors)
