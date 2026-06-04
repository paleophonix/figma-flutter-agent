"""Ad-hoc: inspect background_layout.dart responsive branches."""
from __future__ import annotations

import re
from pathlib import Path

LAYOUT = Path(r"e:\@dev\flutter-demo-project\demo_app\lib\generated\background_layout.dart")


def main() -> None:
    s = LAYOUT.read_text(encoding="utf-8")
    root_lb = (
        "LayoutBuilder(builder: (context, constraints) {final width = "
        "constraints.maxWidth.clamp(0.0, 390.0);if (AppBreakpoints.isWideLayout(width))"
    )
    start = s.find(root_lb)
    print(f"root LB @ {start}")

    # All mobile fallbacks after root
    pos = start
    hits: list[int] = []
    while True:
        j = s.find("}return Column(mainAxisAlignment", pos)
        if j < 0:
            break
        hits.append(j)
        pos = j + 1
    print(f"mobile fallbacks after root: {len(hits)}")
    for i, j in enumerate(hits[:5]):
        chunk = s[j : j + 500]
        has_back = "back-nav" in s[start : j + 8000] and "back-nav" in s[j : j + 15000]
        has_327 = "figma-362_327" in s[j : j + 15000]
        has_cal = "calendar" in s[j : j + 15000]
        has_f6 = "0xFFF6F6F2" in s[j : j + 15000]
        print(
            f"  #{i} @ {j}: back-nav={has_back} 327={has_327} "
            f"calendar={has_cal} F6F6F2={has_f6}"
        )

    # Root mobile return: first }return Column after root wide Row closes
    if hits:
        root_mobile = hits[0]
        # wide branch is between start and root_mobile
        wide = s[start:root_mobile]
        print(f"\nROOT wide branch len={len(wide)}, back-nav in wide={('back-nav' in wide)}")
        mobile = s[root_mobile : root_mobile + 2500]
        print(f"ROOT mobile head has 327={('figma-362_327' in mobile[:8000])}")
        print(f"ROOT mobile head has Личные={('headlineLarge' in mobile[:3000])}")
        print(mobile[:800])

    cal = s.find("calendar_today")
    print(f"\ncalendar @ {cal}")
    if cal >= 0:
        ctx = s[cal - 800 : cal + 200]
        print(ctx)
        print("F6F6F2 in date ctx:", "0xFFF6F6F2" in ctx)

    print(f"\nPositioned top 738 @ {s.find('top: 738')}")
    print(f"Container height 626.8 count: {s.count('height: 626.8')}")
    print(f"Stack children count near root: {s.find('Stack(clipBehavior')}")


def root_layout_builder_bounds(s: str) -> tuple[int, int] | None:
    """Return [start, end) of the root responsive ``LayoutBuilder``."""
    start = s.find(
        "LayoutBuilder(builder: (context, constraints) {final width = "
        "constraints.maxWidth.clamp(0.0, 390.0);"
    )
    if start < 0:
        return None
    depth = 0
    for k in range(start, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                return start, k + 1
    return None


if __name__ == "__main__":
    main()
    s = LAYOUT.read_text(encoding="utf-8")
    bounds = root_layout_builder_bounds(s)
    if bounds:
        start, end = bounds
        chunk = s[start:end]
        print(f"\nroot LB [{start}:{end}) len={end-start}")
        print(f"  mobile return inside root LB: {'}return Column' in chunk}")
        print(f"  back-nav in root LB: {'back-nav' in chunk}")
        print(f"  tail: ...{chunk[-350:]}")
    after = s[bounds[1] : bounds[1] + 120] if bounds else ""
    print(f"after root LB: {after!r}")

    for key in ["figma-362_324", "fontSize: 17.0", "figma-362_327"]:
        for m in re.finditer(re.escape(key), s):
            # nearest preceding }return Column
            before = s.rfind("}return Column", 0, m.start())
            wide_before = s.rfind("isWideLayout(width)) {return Row", 0, m.start())
            branch = (
                "wide"
                if wide_before > before and wide_before > start
                else "mobile/other"
            )
            print(f"  {key} @ {m.start()} nearest reflow: {branch} (wide@{wide_before}, col@{before})")

    # Date: find INPUT decomposition - label without Container F6F6F2
    idx = s.find("calendar_today_outlined")
    if idx >= 0:
        before = s[max(0, idx - 2500) : idx]
        print("\nBefore calendar icon (2500 chars tail):")
        print(before[-900:])

    for pos in [2748, 68282]:
        print(f"\n=== context figma-362_327 @ {pos} ===")
        print(s[pos - 400 : pos + 600])

    # Date field branches
    cal = s.find("calendar_today_outlined")
    for pat in ["TextField(", "0xFFF6F6F2", "figma-362_356", "figma-362_355"]:
        print(f"{pat}: {s.find(pat)}")

    # All F6F6F2 contexts
    off = 0
    n = 0
    while n < 5:
        j = s.find("0xFFF6F6F2", off)
        if j < 0:
            break
        wide = s.rfind("isWideLayout(width)) {return Row", 0, j)
        col = s.rfind("}return Column", 0, j)
        branch = "wide" if wide > col else "mobile"
        print(f"  F6F6F2 #{n} @ {j} branch={branch}")
        print(f"    {s[j-120:j+180]}")
        off = j + 1
        n += 1

    # Root structure when mobile: find ROOT }return Column after start
    # Last isWideLayout in root chunk
    if bounds:
        chunk = s[bounds[0] : bounds[1]]
        last_wide = chunk.rfind("isWideLayout(width)) {return Row")
        last_mobile = chunk.rfind("}return Column(mainAxisAlignment")
        print(f"\nroot chunk: last wide @ {last_wide}, last mobile col @ {last_mobile}")
        if last_mobile > 0:
            print(chunk[last_mobile : last_mobile + 600])
