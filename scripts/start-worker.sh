#!/usr/bin/env bash
# Start the Orion Temporal worker locally.
# Usage: ./scripts/start-worker.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "Starting Orion worker..."
exec python -m orion.workflow.worker
