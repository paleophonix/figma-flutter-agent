import re
from pathlib import Path

p = Path(r"E:/@dev/flutter-demo-project/ataev/lib/generated/profile_partner_layout.dart").read_text(
    encoding="utf-8"
)
heights = re.findall(r"height: ([0-9.]+)", p)
from collections import Counter

for h, c in Counter(heights).most_common(20):
    print(h, c)
print("minHeight", p.count("minHeight"))
idx = p.find("SizedBox(height: 214")
print("214 snippet", p[idx : idx + 300] if idx >= 0 else "none")
idx = p.find("height: 71.0")
print("71 snippet", p[idx - 80 : idx + 200] if idx >= 0 else "none")

chunk = Path(
    r"E:/@dev/flutter-demo-project/ataev/lib/generated/profile_partner_chunk_e5c64fa5.dart"
).read_text(encoding="utf-8")
print("chunk height 80", chunk.count("height: 80.0"))
print("chunk minHeight", chunk.count("minHeight"))
