#!/bin/bash
# Start CodeRabbit AI Pipeline Server

set -e

# Default configuration
HOST="${PYTHON_SERVER_HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
WORKERS="${PYTHON_SERVER_WORKERS:-1}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# Check if OPENAI_API_KEY is set, use dummy if not
if [ -z "$OPENAI_API_KEY" ]; then
    export OPENAI_API_KEY="sk-dummy-key-for-testing"
    echo "⚠️  OPENAI_API_KEY not set, using dummy key for development"
fi

# Display configuration
echo "🚀 Starting CodeRabbit AI Pipeline Server"
echo "======================================"
echo "Host: $HOST"
echo "Port: $PORT"
echo "Workers: $WORKERS"
echo "Environment: $ENVIRONMENT"
echo "======================================"
echo ""

# Start uvicorn server
cd "$(dirname "$0")/.."
poetry run uvicorn coderabbit_ai.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --reload \
    --log-level info
