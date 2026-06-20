# `src/` layout

| Path | Role |
|------|------|
| [`figma_flutter_agent/`](figma_flutter_agent/) | Figma → Flutter compiler (Python, shipped wheel) |
| [`control_panel/`](control_panel/) | Control plane API / Discord / workers (Python, shipped wheel) |

## OpenCode (wizard debug)

Wizard **8. debug** and headless repair talk to a running **OpenCode serve** API (default `http://127.0.0.1:4096`). Install the CLI globally:

```bash
npm install -g opencode-ai
```

Verify: `figma-flutter doctor` → `opencode_cli` row, or `opencode --version`.

Prompts and step skills live under [`.opencode/`](../.opencode/) at the repo root. Python integration: [`figma_flutter_agent/dev/opencode/`](figma_flutter_agent/dev/opencode/).

Control-plane Docker can run OpenCode in a container (`docker-compose.control-plane.yml` profile `repair`); local wizard auto-spawns `opencode serve` when the CLI is on PATH.
