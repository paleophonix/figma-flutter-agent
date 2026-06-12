# render-capture

## Purpose

Docker image and compose service for Flutter golden PNG capture (`figma-flutter-golden-capture:local`).

## Usage Example

```bash
docker compose -f tools/render-capture/docker-compose.yml build golden-capture
docker compose -f tools/render-capture/docker-compose.yml run --rm golden-capture flutter --version
```

Or: `.\scripts\update-golden-docker.ps1` / `poetry run figma-flutter doctor --build-golden`.

## LLM Context

Runtime resolves compose via `validation.golden_runtime.golden_compose_file()`; do not hardcode repo-relative paths outside that helper and `scripts/*`.
