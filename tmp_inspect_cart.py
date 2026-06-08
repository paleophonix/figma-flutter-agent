import re
from pathlib import Path

text = Path(r"E:/@dev/flutter-demo-project/ataev/lib/generated/cart_layout.dart").read_text(
    encoding="utf-8"
)
for m in re.finditer(r"EdgeInsets\.[^(]+\([^)]*-[\d]", text):
    start = max(0, m.start() - 30)
    print("NEG", repr(text[start : m.end() + 40]))
print("--- Image.asset ---")
for m in sorted(set(re.findall(r"Image\.asset\('[^']+'", text))):
    print(m)
print("--- SvgPicture (first 15) ---")
for m in sorted(set(re.findall(r"SvgPicture\.asset\('[^']+'", text)))[:15]:
    print(m)
print("--- Icons ---")
for m in sorted(set(re.findall(r"Icons\.\w+", text))):
    print(m)
print("--- InkWell count ---", text.count("InkWell"))
