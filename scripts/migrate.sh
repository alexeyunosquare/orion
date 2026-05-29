#!/usr/bin/env bash
# Run Alembic database migrations.
# Usage: ./scripts/migrate.sh [revision]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

REVISION="${1:-head}"
echo "Running Alembic migration to: $REVISION"
exec python -m alembic -c src/orion/alembic/alembic.ini upgrade "$REVISION"
