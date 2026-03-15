#!/usr/bin/env bash
set -euo pipefail

echo "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if python -c "import psycopg; c=psycopg.connect('${POSTGRES_DSN}'); c.close()" 2>/dev/null; then
        echo "PostgreSQL is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: PostgreSQL not available after 60 seconds."
        exit 1
    fi
    sleep 2
done

echo "Running migrations..."
alembic upgrade head

echo "Starting agent..."
exec python -m src.main
