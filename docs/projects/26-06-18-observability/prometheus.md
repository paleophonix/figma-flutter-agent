# Prometheus ops metrics

## Purpose

Ops/SLO metrics for figma-flutter-agent and the control panel. Complements Loki (logs + `run_id`) and PostHog (LLM/product analytics).

## Scrape targets

| Target | URL | Auth |
|--------|-----|------|
| Control panel | `http://<host>:8787/metrics` | `Authorization: Bearer $CONTROL_PANEL_METRICS_TOKEN` |
| ARQ worker | `http://<host>:9090/metrics` | none (internal network only) |

Docker Compose optional profile:

```bash
docker compose -f docker-compose.control-panel.yml --profile observability up
```

Mount a bearer token file for Prometheus at `docs/projects/observability/prometheus-bearer.token` when using the bundled config (not committed).

## Business events (PostHog)

| Event | When |
|-------|------|
| `team-requested-generation` | Generation job enqueued |
| `team-opened-issue` | Bug/feat tracker issue created after feedback or publish |
| `agent-committed-change` | Agent publish/repair git commit |
| `dev-committed-change` | MR/PR merged (GitLab/GitHub webhook) |
| `dev-submitted-feedback` | Quality rating (good) or feedback comment submitted |

Grammar: `{subject}-{verb}-{object}`. Properties: `job_id`, `origin`, `change_kind`, `issue_kind`, `feedback_quality` — no secrets or full Figma URLs.

- Generation success rate: `pipeline_runs_total{outcome="success"}` / sum
- P95 stage latency: `histogram_quantile(0.95, pipeline_stage_duration_seconds_bucket)`
- Repair queue: `repair_queue_depth`
- Figma 429 rate: `rate(figma_api_rate_limited_total[5m])`
- Worker load: `arq_jobs_in_flight`

## Cardinality

Never label with `job_id`, `figma_url`, `feature_slug`, `principal`, `node_id`, or full model strings.

## LLM context

Use Prometheus for alerting and SLO dashboards only. Token/cost/prompt detail stays in PostHog `$ai_generation`.
