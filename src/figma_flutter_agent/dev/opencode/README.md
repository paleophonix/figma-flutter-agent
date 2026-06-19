# dev/opencode

## Purpose

Local OpenCode serve bootstrap and minimal HTTP client for the wizard **debug** menu.

## Usage Example

```python
import asyncio
from figma_flutter_agent.dev.opencode import OpenCodeClient, ensure_opencode_serve

async def main() -> None:
    status = await ensure_opencode_serve(
        base_url="http://127.0.0.1:4096",
        password="",
    )
    client = OpenCodeClient(base_url=status.base_url, password="")
    session_id = await client.create_session(title="debug-login_v1")
    print(session_id)

asyncio.run(main())
```

## LLM Context

Wizard debug resolves the active screen via manifest, collects `.debug` artifacts through `debug/context.py`, then calls `ensure_opencode_serve` before creating an OpenCode session stub. Agent prompts and skills are follow-ups.
