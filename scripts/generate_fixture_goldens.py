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

from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files

from figma_flutter_agent.config import Settings
from figma_flutter_agent.fixtures.capture_context import resolve_fixture_project_dir
from figma_flutter_agent.fixtures.golden_compare import compare_fixture_golden
from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.fixtures.screens_manifest import (
    fixtures_root,
    load_layout_tree,
    load_screens_manifest,
)
from figma_flutter_agent.validation.golden_capture import (
    FixtureCaptureBatch,
    capture_planned_for_fixture,
)


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
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare capture to existing baseline instead of writing PNGs",
    )
    parser.add_argument(
        "--update-goldens",
        action="store_true",
        help="Write baseline PNGs (default when neither --check nor --update-goldens is set)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Pixel diff threshold for --check (default 0.05)",
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
    warm_project = resolve_fixture_project_dir(settings)
    batch = FixtureCaptureBatch(
        settings=settings,
        project_dir=warm_project,
        write_timings=True,
    )
    batch.golden_runtime = batch.resolved_runtime(args.golden_runtime)

    write_mode = args.update_goldens or not args.check

    for entry in entries:
        print(f"Capturing {entry.id} ({entry.feature})...", flush=True)
        if args.check:
            compare = compare_fixture_golden(
                entry,
                settings=settings,
                baseline_dir=args.output_dir,
                pixel_threshold=args.threshold,
                golden_runtime=args.golden_runtime,
                flutter_sdk=flutter_sdk,
                project_dir=warm_project,
                capture_batch=batch,
            )
            if compare.skipped:
                print(f"  SKIP: {compare.reason}", flush=True)
                failures += 1
                continue
            if compare.ok:
                ratio = compare.changed_ratio or 0.0
                print(f"  OK ({ratio:.2%} changed)", flush=True)
                continue
            print(f"  FAIL: {compare.reason}", flush=True)
            failures += 1
            continue
        if not write_mode:
            print("  SKIP: pass --update-goldens to write baseline PNGs", flush=True)
            continue
        layout_tree = load_layout_tree(entry)
        planned = build_fixture_planned_files(entry)
        planned = reconcile_planned_dart_files(planned)
        result = capture_planned_for_fixture(
            batch,
            planned,
            feature_name=entry.feature,
            layout_tree=layout_tree,
            golden_runtime=args.golden_runtime,
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
