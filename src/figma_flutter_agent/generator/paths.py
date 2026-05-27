"""Project path helpers aligned with config architecture."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Architecture = Literal["feature_first", "layer_first"]


def screen_file_path(feature_name: str, *, architecture: Architecture = "feature_first") -> str:
    """Return the relative Dart path for a generated screen file."""
    if architecture == "layer_first":
        return f"lib/presentation/screens/{feature_name}_screen.dart"
    return f"lib/features/{feature_name}/{feature_name}_screen.dart"


def screen_import_path(feature_name: str, *, architecture: Architecture = "feature_first") -> str:
    """Return the import path used by ``main.dart`` for a standalone screen."""
    if architecture == "layer_first":
        return f"presentation/screens/{feature_name}_screen.dart"
    return f"features/{feature_name}/{feature_name}_screen.dart"


def destination_screen_file_path(
    route_name: str, *, architecture: Architecture = "feature_first"
) -> str:
    """Return the relative Dart path for a destination stub screen."""
    return screen_file_path(route_name, architecture=architecture)


def state_file_path(feature_name: str, *, architecture: Architecture = "feature_first") -> str:
    """Return the relative Dart path for a generated state stub file."""
    if architecture == "layer_first":
        return f"lib/presentation/state/{feature_name}_state.dart"
    return f"lib/features/{feature_name}/{feature_name}_state.dart"


def dart_relative_import_prefix(relative_path: str) -> str:
    """Return a ``../`` prefix from a ``lib/...`` file path up to ``lib/``."""
    if not relative_path.startswith("lib/"):
        return "../../"
    under_lib = relative_path.removeprefix("lib/")
    depth = len(under_lib.split("/")) - 1
    return "../" * max(depth, 1)


@dataclass(frozen=True)
class ImportContext:
    """Resolve Dart import URIs for generated project files."""

    package_name: str = "demo_app"
    use_package_imports: bool = True
    source_file: str | None = None

    def uri(self, path_under_lib: str) -> str:
        """Return a Dart import URI for a path relative to ``lib/``."""
        normalized = path_under_lib.removeprefix("lib/")
        if self.use_package_imports and self.package_name:
            return f"package:{self.package_name}/{normalized}"
        if self.source_file:
            prefix = dart_relative_import_prefix(self.source_file)
            return f"{prefix}{normalized}"
        return f"../{normalized}"
