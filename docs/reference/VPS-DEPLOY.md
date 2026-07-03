# VPS Docker deployment

Production stack for the figma-flutter **control panel** on a single Linux VPS: FastAPI + ARQ worker, Redis, bundled Postgres, Caddy (HTTPS), optional OpenCode repair and observability profiles.

## Purpose

Run headless `/generate`, GitLab Issue workflow, preview links, and optional Discord without a developer laptop. Jobs execute in the ARQ worker; golden capture uses the host Docker socket (`FIGMA_GOLDEN_RUNTIME=docker`).

## Prerequisites

| Requirement | Notes |
| --- | --- |
| Linux VPS | 4 GB RAM minimum; 8 GB+ if repair profile + golden capture |
| Docker Engine 24+ | With Compose v2 plugin |
| DNS | `FIGMA_CP_PUBLIC_HOST` A/AAAA → VPS before first TLS issue |
| Ports | `80` and `443` open to the internet |
| Secrets | Figma token, LLM key, GitLab token, strong `FIGMA_CP_PG_PASSWORD` |

## Usage example

From the repository root on the VPS:

```bash
git clone <repo-url> /opt/figma-cp && cd /opt/figma-cp
cp env.production.example .env
cp Caddyfile.example Caddyfile
cp .control-panel.yml.example .control-panel.yml
cp .ai-figma-flutter.yml.example .ai-figma-flutter.yml
# Edit .env, .control-panel.yml (workspace_root: /workspace, control_panel_url), generation profile

chmod +x scripts/deploy-vps.sh
./scripts/deploy-vps.sh
```

Optional profiles:

```bash
./scripts/deploy-vps.sh --repair --observability
```

Manual equivalent:

```bash
docker compose -f docker-compose.deploy.yml --profile bundled-db up -d --build
```

Verify:

```bash
curl -fsS "https://cp.example.com/health"
curl -fsS "https://cp.example.com/ready"
```

## Configuration

| File | Role |
| --- | --- |
| `.env` | Secrets and `FIGMA_CP_INTERNAL_URL` (public HTTPS base) |
| `.control-panel.yml` | Repos, GitLab workflow, `projects.workspace_root: /workspace` |
| `.ai-figma-flutter.yml` | Agent compiler settings (production profile recommended) |
| `Caddyfile` | TLS reverse proxy to `control-panel:8787` |

Set in `.control-panel.yml` for production:

```yaml
internal:
  control_panel_url: "https://cp.example.com"
generation:
  use_production_profile: true
database:
  mode: bundled
  bundled_host: postgres
gitlab_workflow:
  enabled: true
discord:
  enabled: false
```

External Postgres: set `FIGMA_CP_DATABASE_MODE=external`, `FIGMA_CP_DATABASE_URL`, and start **without** `--profile bundled-db`.

## Compose files (dev vs production)

| File | When |
| --- | --- |
| `docker-compose.local.yml` | Local dev — ports `8787`/`5432`/`6379` on localhost, no TLS |
| `docker-compose.deploy.yml` | Production VPS — Caddy on `80`/`443`, DB/Redis internal only, stricter env |

Same services at the core (panel + worker + Redis + Postgres); not duplicates — different networking, secrets defaults, and edge TLS.

## Operations

| Task | Command |
| --- | --- |
| Logs | `docker compose -f docker-compose.deploy.yml logs -f control-panel arq-worker` |
| Restart | `docker compose -f docker-compose.deploy.yml restart control-panel arq-worker` |
| Migrations | Run automatically on `control-panel` start (`alembic upgrade head`) |
| Stop | `./scripts/deploy-vps.sh --down` |
| Update | `git pull && ./scripts/deploy-vps.sh --pull` |

Firewall: allow only `22`, `80`, `443`. Postgres and Redis are not published on the host.

## LLM context

This module is **ops packaging only** — no compiler logic. Runtime layout: Caddy (edge) → `control-panel:8787`; worker shares `/workspace` volume and `/var/run/docker.sock` for `tools/render-capture` golden images. Agent repo root inside the image is `/app` (`agent_repo_root()`). Debug artifacts for jobs land under `/app/.debug/screen/` inside the worker container unless publish migrates them.
