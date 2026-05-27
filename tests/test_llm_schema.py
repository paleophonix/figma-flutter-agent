from figma_flutter_agent.llm.schema import generation_json_schema


def test_generation_json_schema_is_strict_compatible() -> None:
    schema = generation_json_schema(strict=True)

    assert schema["additionalProperties"] is False
    assert "screenCode" in schema["required"]
    assert schema["$defs"]["ExtractedWidget"]["additionalProperties"] is False
