# OpenCode VPS smoke checklist (auto-repair)

Run on the target VPS **before** locking production transport in `control_panel.repair`.

## Pin version

```bash
npm install -g opencode-ai@<PINNED_VERSION>
opencode --version
```

Record the pinned version in `.env` / compose (`OPENCODE_VERSION`).

## Auth and health

```bash
export OPENCODE_SERVER_PASSWORD='<secret>'
export OPENCODE_SERVER_USERNAME='opencode'
opencode serve --hostname 127.0.0.1 --port 4096
```

| Check | Command | Pass |
|-------|---------|------|
| Health | `curl -u opencode:$OPENCODE_SERVER_PASSWORD http://127.0.0.1:4096/global/health` | `healthy: true` |
| OpenAPI | open `http://127.0.0.1:4096/doc` | spec loads |

Behind reverse proxy: confirm health probe uses **Basic Auth** or TCP-only check (see GitHub issue #12805).

## Transport matrix

### A — Sync message (MVP default)

```bash
# create session
curl -u ... -X POST http://127.0.0.1:4096/session -H 'Content-Type: application/json' -d '{"title":"smoke-sync"}'
# long prompt
curl -u ... -X POST http://127.0.0.1:4096/session/<id>/message \
  -H 'Content-Type: application/json' \
  -d '{"parts":[{"type":"text","text":"Reply with OK only."}]}'
```

Pass: completes without proxy 524 within ARQ `job_timeout`.

### B — Async + SSE (optional upgrade)

```bash
curl -u ... -X POST http://127.0.0.1:4096/session/<id>/prompt_async ...
curl -u ... -N http://127.0.0.1:4096/global/event
```

Pass: `session.idle` or terminal `message.updated` after async prompt.

## Structured output field

On pinned `/doc`, confirm request body uses `format` or `outputFormat` for JSON schema prompts.
Update `SyncMessageTransport` if the spec differs.

## Worktree directory header

Confirm client can pass worktree via `x-opencode-directory` (SDK) or directory query on file APIs.

## Sign-off

| Item | Result | Version / notes |
|------|--------|-----------------|
| Sync transport | | |
| Async+SSE | | |
| Structured output field | | |
| Basic auth health | | |
