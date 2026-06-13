from figma_flutter_agent.llm.schema import generation_json_schema


def _anyof_branch_has_type(branch: object) -> bool:
    if not isinstance(branch, dict):
        return True
    if "$ref" in branch or "type" in branch:
        return True
    return "anyOf" in branch or "oneOf" in branch or "allOf" in branch


def _walk_schema_nodes(node: object) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_schema_nodes(item)
        return
    if not isinstance(node, dict):
        return
    for key in ("anyOf", "oneOf", "allOf"):
        variants = node.get(key)
        if isinstance(variants, list):
            for index, branch in enumerate(variants):
                assert _anyof_branch_has_type(branch), (
                    f"{key}[{index}] missing type in strict schema: {branch!r}"
                )
    for value in node.values():
        _walk_schema_nodes(value)


def test_generation_json_schema_is_strict_compatible() -> None:
    schema = generation_json_schema(strict=True)

    assert schema["additionalProperties"] is False
    assert "screenCode" in schema["required"]
    assert schema["$defs"]["ExtractedWidget"]["additionalProperties"] is False


def test_strict_schema_omits_openai_incompatible_map_fields() -> None:
    schema = generation_json_schema(strict=True)
    screen_ir = schema["$defs"]["ScreenIr"]
    assert "stateByFigmaId" not in screen_ir["properties"]
    assert "stateByFigmaId" not in screen_ir["required"]
    assert screen_ir["additionalProperties"] is False


def test_strict_schema_anyof_branches_declare_type() -> None:
    _walk_schema_nodes(generation_json_schema(strict=True))


def test_strict_schema_ref_properties_have_no_sibling_keywords() -> None:
    schema = generation_json_schema(strict=True)
    kind = schema["$defs"]["WidgetIrNode"]["properties"]["kind"]
    assert kind == {"$ref": "#/$defs/WidgetIrKind"}
    assert "kind" in schema["$defs"]["WidgetIrNode"]["required"]
