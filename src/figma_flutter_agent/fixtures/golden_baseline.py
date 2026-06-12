"""Safety rules for committed fixture golden PNG baseline updates."""

from __future__ import annotations

from pathlib import Path

from figma_flutter_agent.fixtures.screens_manifest import fixtures_root


def is_docker_baseline_dir(output_dir: Path) -> bool:
    """Return True when ``output_dir`` targets committed docker golden baselines."""
    resolved = output_dir.resolve()
    docker_root = (fixtures_root() / "golden" / "png" / "docker").resolve()
    return resolved == docker_root or docker_root in resolved.parents


def validate_baseline_write(
    *,
    update_goldens: bool,
    golden_runtime: str,
    output_dir: Path,
) -> str | None:
    """Validate baseline write flags.

    Returns:
        Error message when write must be blocked, otherwise None.
    """
    if not update_goldens:
        return "pass --update-goldens to write baseline PNGs"
    if is_docker_baseline_dir(output_dir) and golden_runtime != "docker":
        return (
            "--golden-runtime docker is required when writing to "
            "tests/fixtures/golden/png/docker (host captures must not overwrite docker baselines)"
        )
    return None
