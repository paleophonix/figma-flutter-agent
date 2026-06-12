"""Dump raw IR emitter output for diff (do **not** overwrite the lib-sourced golden).

The canonical reference bundle is refreshed via ``scripts/refresh_reference_from_lib.py``.

Usage:
    poetry run python scripts/write_emitter_reference.py \\
        --project-dir E:/@dev/flutter-demo-project/demo_app \\
        --feature background
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from figma_flutter_agent.debug.emitter_reference import write_emitter_reference


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
        help="Flutter project root (contains .debug)",
    )
    parser.add_argument(
        "--feature",
        required=True,
        help="Screen feature slug, e.g. background",
    )
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="Omit flutter_svg imports in generated Dart",
    )
    args = parser.parse_args(argv)
    try:
        out_path = write_emitter_reference(
            args.project_dir.expanduser().resolve(),
            feature_name=args.feature,
            uses_svg=not args.no_svg,
        )
    except Exception:
        traceback.print_exc()
        return 1
    print(out_path.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
