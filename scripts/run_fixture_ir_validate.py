#!/usr/bin/env python3
"""Run IR guardrails on all entries in tests/fixtures/screens.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from figma_flutter_agent.fixtures.bulk_ir_validate import validate_all_fixture_screens


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--screen",
        action="append",
        dest="screens",
        help="Manifest screen id (default: all)",
    )
    parser.add_argument(
        "--no-guards",
        action="store_true",
        help="Skip apply_ir_guards (validate structure only)",
    )
    args = parser.parse_args()

    results = validate_all_fixture_screens(
        screen_ids=args.screens,
        apply_guards=not args.no_guards,
        validate=True,
    )
    failures = 0
    for item in results:
        if item.ok:
            print(f"OK  {item.screen_id}")
        else:
            failures += 1
            print(f"FAIL {item.screen_id}: {item.error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
