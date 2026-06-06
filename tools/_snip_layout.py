from pathlib import Path

t = Path(
    r"e:\@dev\flutter-demo-project\demo_app\lib\generated\background_layout.dart"
).read_text(encoding="utf-8")
needle = "spacing: 16.0, children: [Flexible"
i = t.find(needle)
print(t[i - 200 : i + 1200] if i >= 0 else "not found")
