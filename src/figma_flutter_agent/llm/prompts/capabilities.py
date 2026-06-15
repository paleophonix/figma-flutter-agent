"""L4 prompt capabilities."""

from __future__ import annotations

# L4:CAPABILITIES
# ---------------------------------------------------------------------------

# --- generate ---
_L4_GENERATE_MATERIAL = """- Advanced execution of Material 3 design tokens (`Theme.of(context).colorScheme`, `textTheme`) without hardcoded literal injection.
- Structural constraints resolution (`Flexible`/`Expanded` positioning invariants inside horizontal containers).
- Error-free compilation of conditional typographical structures (RichText vs standard Text).
- Semantic mapping: GRID→GridView.builder, scrollAxis→ListView.builder, TABS→TabBar/TabBarView, BOTTOM_NAV→BottomNavigationBar, CAROUSEL→PageView, DIALOG→AlertDialog, CARD→Card.
- [STATEFUL VARIANT MAPPING]: Map variantProperties with MaterialStateProperty, switch expressions, or native widget APIs."""

_L4_GENERATE_CUPERTINO = """- Advanced implementation of Cupertino styling controls (`CupertinoButton`, `CupertinoTextField`, `CupertinoPageScaffold`, `CupertinoNavigationBar`).
- Material Theme Bridge logic resolution only when explicitly sharing global tokens.
- Error-free compilation of conditional typographical structures (RichText vs standard Text).
- Semantic mapping: scrollAxis→ListView.builder, TABS→CupertinoTabBar patterns, CAROUSEL→PageView, CHECKBOX/SWITCH/SLIDER→CupertinoCheckbox/CupertinoSwitch/CupertinoSlider."""

# --- repair ---
_REPAIR_L4 = """- Proficient in Dart 3.x type systems, constructor mechanics, and cascading widget definitions.
- Deep understanding of Flutter layout constraints (Flex, Stack, ParentData requirements).
- Ability to cross-reference runtime ValueKey anchors with structural design semantics."""

# --- cpi ---
_CPI_L4 = """- Expert in identifying repetitive token sequence generation (cosine similarity of code states).
- Advanced pattern recognition in compiler error logs and loop mechanics."""
