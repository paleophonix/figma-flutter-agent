"""Figma connectivity criterion for spec-23."""

from __future__ import annotations

import asyncio
import inspect

from figma_flutter_agent.config import Settings
from figma_flutter_agent.figma.client import FigmaConnector
from figma_flutter_agent.validation.spec23.models import Spec23CriterionResult


def _criterion_figma_connectivity(
    *, strict: bool, settings: Settings | None = None
) -> Spec23CriterionResult:
    settings = settings or Settings()
    if strict:
        passed = (
            inspect.iscoroutinefunction(FigmaConnector.fetch_nodes)
            and inspect.iscoroutinefunction(FigmaConnector.__aenter__)
            and callable(getattr(FigmaConnector, "_request", None))
        )
        detail = "connector API surface (live fetch: use live-check / live_figma tests)"

        token = settings.figma_token().strip()
        file_key = settings.figma_smoke_file_key.strip()
        node_id = settings.figma_smoke_node_id.strip()
        if token and file_key and node_id:
            try:

                async def check_live() -> None:
                    async with FigmaConnector(token) as connector:
                        await connector.fetch_nodes(file_key, [node_id])

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    from concurrent.futures import ThreadPoolExecutor

                    with ThreadPoolExecutor() as executor:
                        future = executor.submit(asyncio.run, check_live())
                        future.result()
                else:
                    asyncio.run(check_live())
                detail = f"connector API surface + live fetch OK ({node_id} in {file_key})"
            except Exception as exc:
                passed = False
                detail = f"live fetch failed: {exc}"
    else:
        from figma_flutter_agent.figma.url import parse_figma_url

        try:
            parse_figma_url("https://www.figma.com/file/ABC/test?node-id=1-1")
            passed = FigmaConnector is not None
            detail = "connector available"
        except Exception:
            passed = False
            detail = "URL parsing failed"
    return Spec23CriterionResult(name="figma_connectivity", passed=passed, detail=detail)
