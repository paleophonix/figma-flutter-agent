# `src/` layout

| Path | Role |
|------|------|
| [`figma_flutter_agent/`](figma_flutter_agent/) | Figma → Flutter compiler (Python, shipped wheel) |
| [`control_panel/`](control_panel/) | Control plane API / Discord / workers (Python, shipped wheel) |
| [`opencode/`](opencode/) | Vendored [OpenCode](https://github.com/anomalyco/opencode) coding agent (TypeScript/Bun monorepo, git submodule) |

## OpenCode submodule

Upstream: `https://github.com/anomalyco/opencode` (branch `dev`).

```bash
# First clone of this repo — API-only tree (no desktop/web/infra)
git submodule update --init --depth 1 src/opencode
./scripts/opencode-api-init.sh          # Linux/macOS
# .\scripts\opencode-api-init.ps1       # Windows

# Full upstream tree (all packages)
git submodule update --init --recursive src/opencode
```

OpenCode is **not** part of the `figma-flutter-agent` Python wheel. Python release gates exclude `src/opencode/` from ruff/mypy scope.

### API-only checkout (optional)

Headless API: `cd src/opencode && bun install && bun dev serve` (default port 4096).

**Why `.gitignore` alone does not hide OpenCode folders:** `src/opencode` is a git submodule — ignore rules in the parent repo do not apply inside it. Use [`scripts/opencode-api-init.ps1`](../scripts/opencode-api-init.ps1) / [`opencode-api-init.sh`](../scripts/opencode-api-init.sh) for sparse checkout (desktop, web, infra, etc. are never checked out).

MIT license — see `src/opencode/LICENSE`.
