#!/usr/bin/env bash
# Bootstrap figma-flutter control panel on a Linux VPS (Docker + Compose v2).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

COMPOSE_FILE="docker-compose.deploy.yml"
PROFILES=(bundled-db)

usage() {
    cat <<'EOF'
Usage: ./scripts/deploy-vps.sh [--repair] [--observability] [--pull] [--down]

First run copies env.production.example → .env and Caddyfile.example → Caddyfile
when missing. Edit .env, .control-panel.yml, and .ai-figma-flutter.yml before production traffic.

Default: docker compose -f docker-compose.deploy.yml --profile bundled-db up -d --build
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repair) PROFILES+=(repair) ;;
        --observability) PROFILES+=(observability) ;;
        --pull) DO_PULL=1 ;;
        --down) DO_DOWN=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
    shift
done

if [[ ! -f .env ]]; then
    cp env.production.example .env
    echo "Created .env from env.production.example — edit secrets before going live."
fi

if [[ ! -f Caddyfile ]]; then
    cp Caddyfile.example Caddyfile
    echo "Created Caddyfile from example."
fi

if [[ ! -f .control-panel.yml ]]; then
    cp .control-panel.yml.example .control-panel.yml
    echo "Created .control-panel.yml from example."
fi

if [[ ! -f .ai-figma-flutter.yml ]]; then
    cp .ai-figma-flutter.yml.example .ai-figma-flutter.yml
    echo "Created .ai-figma-flutter.yml from example."
fi

mkdir -p .data/postgres .data/redis .data/workspace .data/repair-worktrees

profile_args=()
for p in "${PROFILES[@]}"; do
    profile_args+=(--profile "$p")
done

if [[ "${DO_DOWN:-0}" == 1 ]]; then
    docker compose -f "$COMPOSE_FILE" "${profile_args[@]}" down
    exit 0
fi

if [[ "${DO_PULL:-0}" == 1 ]]; then
    git pull --ff-only
fi

echo "Starting VPS stack (${PROFILES[*]})..."
docker compose -f "$COMPOSE_FILE" "${profile_args[@]}" up -d --build

echo "Done. Check: docker compose -f $COMPOSE_FILE ps"
echo "Health: curl -fsS \"\${FIGMA_CP_INTERNAL_URL:-https://your-host}/health\""
