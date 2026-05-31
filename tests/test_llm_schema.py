from figma_flutter_agent.llm.schema import generation_json_schema


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


def test_strict_schema_ref_properties_have_no_sibling_keywords() -> None:
    schema = generation_json_schema(strict=True)
    kind = schema["$defs"]["WidgetIrNode"]["properties"]["kind"]
    assert kind == {"$ref": "#/$defs/WidgetIrKind"}
    assert "kind" in schema["$defs"]["WidgetIrNode"]["required"]
