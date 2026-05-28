#!/usr/bin/env python3
"""Generate docker golden PNG baselines for tests/fixtures/screens.yaml entries."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import fixtures_root, load_layout_tree, load_screens_manifest
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
from figma_flutter_agent.validation.golden_capture import capture_planned_flutter_golden_png


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen",
        action="append",
        dest="screens",
        help="Manifest screen id (default: all)",
    )
    parser.add_argument(
        "--golden-runtime",
        choices=("auto", "docker", "host"),
        default=os.environ.get("FIGMA_GOLDEN_RUNTIME", "auto"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=fixtures_root() / "golden" / "png" / "docker",
    )
    args = parser.parse_args()

    manifest = load_screens_manifest()
    entries = manifest.screens
    if args.screens:
        wanted = set(args.screens)
        entries = [entry for entry in entries if entry.id in wanted]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    settings = Settings()
    flutter_sdk = settings.flutter_sdk or None

    for entry in entries:
        print(f"Capturing {entry.id} ({entry.feature})...", flush=True)
        layout_tree = load_layout_tree(entry)
        planned = build_fixture_planned_files(entry)
        planned = reconcile_planned_dart_files(planned)
        result = capture_planned_flutter_golden_png(
            planned,
            feature_name=entry.feature,
            golden_runtime=args.golden_runtime,
            settings=settings,
            flutter_sdk=flutter_sdk,
            layout_tree=layout_tree,
        )
        if not result.ok or result.png is None:
            print(f"  FAIL: {result.reason}", flush=True)
            failures += 1
            continue
        out_path = args.output_dir / f"{entry.golden_id}.png"
        out_path.write_bytes(result.png)
        print(f"  wrote {out_path} ({len(result.png)} bytes)", flush=True)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
