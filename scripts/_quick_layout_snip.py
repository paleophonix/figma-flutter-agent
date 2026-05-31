from figma_flutter_agent.fixtures.golden_planned import build_fixture_planned_files
from figma_flutter_agent.generator.planned_dart import reconcile_planned_dart_files
import subprocess, tempfile
from pathlib import Path

p = reconcile_planned_dart_files(build_fixture_planned_files("sign_up_and_sign_in"))
layout = p["lib/generated/sign_up_and_sign_in_layout.dart"]
i = layout.find("1_3973")
snip = layout[max(0, i - 30) : i + 400]
print(snip)
f = Path(tempfile.mkdtemp()) / "l.dart"
f.write_text("import 'package:flutter/material.dart';\nimport 'package:flutter/gestures.dart';\n" + layout, encoding="utf-8")
r = subprocess.run([r"F:\src\flutter\bin\dart.bat", "format", str(f)], capture_output=True, text=True)
print("format", r.returncode, r.stderr[:200] if r.stderr else "ok")
