"""Tests for repair pipeline Loki-oriented logging helpers."""

from __future__ import annotations

from figma_flutter_agent.dev.opencode.repair_log import log_repair_step


def test_log_repair_step_emits_bound_message(monkeypatch) -> None:
    captured: list[dict[str, object]] = []

    class _FakeLogger:
        def bind(self, **kwargs: object) -> _FakeLogger:
            captured.append(kwargs)
            return self

        def info(self, template: str, *args: object) -> None:
            captured.append({"template": template, "args": args})

    monkeypatch.setattr(
        "figma_flutter_agent.dev.opencode.repair_log.repair_logger",
        lambda: _FakeLogger(),
    )
    log_repair_step("recognise", status="started", loop_round=1)
    assert captured[0]["step"] == "recognise"
    assert captured[0]["status"] == "started"
