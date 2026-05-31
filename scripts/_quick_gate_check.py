"""Quick: does reconcile break sign_up screen parse?"""
from pathlib import Path
import subprocess
import tempfile

from figma_flutter_agent.fixtures.golden_planned import fixture_design_tokens
from figma_flutter_agent.fixtures.screens_manifest import load_layout_tree
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files

path = "lib/features/sign_up_and_sign_in/sign_up_and_sign_in_screen.dart"
raw = Path(r"E:/@dev/demo_app/lib/features/sign_up_and_sign_in/sign_up_and_sign_in_screen.dart").read_text(
    encoding="utf-8"
)
tree = load_layout_tree("sign_up_and_sign_in")
heavy = reconcile_planned_dart_files(
    {path: raw},
    typography_tokens=fixture_design_tokens(),
    clean_tree=tree,
)
screen = heavy[path]
changed = screen != raw
td = Path(tempfile.mkdtemp()) / "s.dart"
td.write_text(
    "import 'package:flutter/material.dart';\n"
    "import 'package:flutter/gestures.dart';\n"
    "import 'package:demo_app/theme/app_typography.dart';\n"
    "import 'package:demo_app/theme/app_layout.dart';\n" + screen,
    encoding="utf-8",
)
r = subprocess.run(
    [r"F:\src\flutter\bin\dart.bat", "format", str(td)],
    capture_output=True,
    text=True,
)
print("changed", changed)
print("format_exit", r.returncode)
if r.returncode != 0:
    print(r.stderr[:500])
    i = screen.find("1_3973")
    if i >= 0:
        print(screen[max(0, i - 40) : i + 450])
