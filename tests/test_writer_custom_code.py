from figma_flutter_agent.generator.writing.custom_code import (
    extract_custom_code_blocks,
    merge_custom_code,
)


def test_extract_custom_code_blocks_supports_named_zones() -> None:
    content = "\n".join(
        [
            "// <custom-code:onContinue>",
            "void _onContinue() {}",
            "// </custom-code:onContinue>",
            "// <custom-code>",
            "int counter = 1;",
            "// </custom-code>",
        ]
    )

    blocks = extract_custom_code_blocks(content)

    assert blocks == {"onContinue": "void _onContinue() {}", "": "int counter = 1;"}


def test_merge_custom_code_rebases_indentation() -> None:
    existing = "\n".join(
        [
            "// <custom-code>",
            "    void kept() {",
            "      debugPrint('x');",
            "    }",
            "// </custom-code>",
        ]
    )
    new_content = "\n".join(
        [
            "class Screen {",
            "  void build() {",
            "    // <custom-code>",
            "    // </custom-code>",
            "  }",
            "}",
        ]
    )

    merged = merge_custom_code(new_content, existing)

    assert "void kept() {" in merged
    assert "      debugPrint('x');" in merged


def test_merge_custom_code_accepts_flexible_markers() -> None:
    existing = "//  <  custom-code  >\nkeep = 1;\n//  </  custom-code  >"
    new_content = "//<custom-code>\n//</custom-code>\nclass X {}"

    merged = merge_custom_code(new_content, existing)

    assert "keep = 1;" in merged


def test_merge_custom_code_preserves_named_and_legacy_blocks() -> None:
    existing = "\n".join(
        [
            "// <custom-code:onContinue>",
            "void _onContinue() {}",
            "// </custom-code:onContinue>",
            "// <custom-code>",
            "int counter = 1;",
            "// </custom-code>",
        ]
    )
    new_content = "\n".join(
        [
            "// <custom-code:onContinue>",
            "// </custom-code:onContinue>",
            "// <custom-code>",
            "// </custom-code>",
            "class Screen {}",
        ]
    )

    merged = merge_custom_code(new_content, existing)

    assert "void _onContinue() {}" in merged
    assert "int counter = 1;" in merged
    assert "class Screen {}" in merged


def test_merge_custom_code_preserves_unmatched_blocks_when_template_lacks_zones() -> None:
    existing = "// <custom-code:legacy>\nkeep()\n// </custom-code:legacy>"
    new_content = "class Generated {}"

    merged = merge_custom_code(new_content, existing)

    assert "keep()" in merged
    assert "// <custom-code:legacy>" in merged
    assert "class Generated {}" in merged


def test_merge_custom_code_preserves_five_named_zones() -> None:
    zone_names = ("onInit", "onContinue", "onDispose", "header", "footer")
    existing_lines: list[str] = []
    new_lines: list[str] = []
    for index, name in enumerate(zone_names):
        body = f"void _handler{index}() {{}}"
        existing_lines.extend(
            [
                f"// <custom-code:{name}>",
                body,
                f"// </custom-code:{name}>",
            ]
        )
        new_lines.extend(
            [
                f"// <custom-code:{name}>",
                f"// </custom-code:{name}>",
            ]
        )
    existing = "\n".join(existing_lines)
    new_content = "\n".join([*new_lines, "class Screen {}"])

    merged = merge_custom_code(new_content, existing)

    for index, name in enumerate(zone_names):
        assert f"void _handler{index}()" in merged
        assert f"custom-code:{name}" in merged


def test_merge_custom_code_preserves_duplicate_named_zones_in_order() -> None:
    existing = "\n".join(
        [
            "// <custom-code:bottom-nav>",
            "debugPrint('kept');",
            "// </custom-code:bottom-nav>",
            "// <custom-code:bottom-nav>",
            "",
            "// </custom-code:bottom-nav>",
        ]
    )
    new_content = "\n".join(
        [
            "// <custom-code:bottom-nav>",
            "// </custom-code:bottom-nav>",
            "// <custom-code:bottom-nav>",
            "// </custom-code:bottom-nav>",
            "class Screen {}",
        ]
    )

    merged = merge_custom_code(new_content, existing)

    assert merged.index("debugPrint('kept');") < merged.rindex("custom-code:bottom-nav")


def test_merge_custom_code_inserts_unmatched_blocks_after_imports() -> None:
    existing = "// <custom-code:legacy>\nkeep()\n// </custom-code:legacy>"
    new_content = "\n".join(
        [
            "import 'package:flutter/material.dart';",
            "",
            "class Generated {}",
        ]
    )

    merged = merge_custom_code(new_content, existing)
    lines = merged.splitlines()

    import_index = lines.index("import 'package:flutter/material.dart';")
    legacy_index = next(i for i, line in enumerate(lines) if "custom-code:legacy" in line)
    class_index = lines.index("class Generated {}")

    assert import_index < legacy_index < class_index
