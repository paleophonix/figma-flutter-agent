#!/bin/sh
set -eu

wait_for_postgres() {
    if [ "${FIGMA_CP_DATABASE_MODE:-bundled}" = "external" ]; then
        return 0
    fi
    host="${FIGMA_CP_PG_HOST:-postgres}"
    port="${FIGMA_CP_PG_PORT:-5432}"
    echo "Waiting for Postgres at ${host}:${port}..."
    until python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('${host}', int('${port}'))); s.close()" 2>/dev/null; do
        sleep 1
    done
}

if [ "${FIGMA_CP_RUN_MIGRATIONS:-0}" = "1" ]; then
    wait_for_postgres
    echo "Running Alembic migrations..."
    alembic upgrade head
fi

exec "$@"
