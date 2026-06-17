"""Integration tests for OpenCode transport (mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from control_panel.repair.opencode.client import OpenCodeClient
from control_panel.repair.opencode.transport import SyncMessageTransport


@pytest.mark.asyncio
async def test_sync_message_transport_delegates() -> None:
    client = OpenCodeClient(base_url="http://127.0.0.1:4096", password="")
    client.prompt_message = AsyncMock(return_value={"parts": [{"type": "text", "text": "OK"}]})
    transport = SyncMessageTransport(client)
    result = await transport.send("sess-1", text="ping", agent="repair-build")
    client.prompt_message.assert_awaited_once()
    assert result["parts"][0]["text"] == "OK"
