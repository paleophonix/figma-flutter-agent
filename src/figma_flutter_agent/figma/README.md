# figma

## Purpose

Figma REST integration: URL parsing, async HTTP client, and response models.

## Example

```python
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.figma.url import parse_figma_url, resolve_smoke_frame

parsed = parse_figma_url("https://www.figma.com/design/abc/App?node-id=1-2")
# live-check: resolve_smoke_frame(figma_url=url, file_key=..., node_id=...)

async with FigmaConnector(token) as connector:
    nodes = await connector.fetch_nodes(parsed.file_key, [parsed.node_id])
    styles = await connector.fetch_styles(parsed.file_key)
    components = await connector.fetch_components(parsed.file_key)
```

## LLM Context

Provide `file_key`, `node_id`, and serialized `document` JSON from `fetch_nodes`. Include `styles` and `components` maps when enriching the clean tree. Mention retry behavior on 429/5xx, null image URL retries (`IMAGE_URL_NULL_RETRIES`), and that `fetch_variables` may return `None` on 403.
