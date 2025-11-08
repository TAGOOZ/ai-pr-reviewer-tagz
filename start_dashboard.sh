#!/bin/bash
# Start CodeRabbit AI Server with Dashboard

echo "🚀 Starting CodeRabbit AI Server with Dashboard..."
echo ""

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Error: Python not found!"
    exit 1
fi

# Set environment variables (customize these as needed)
export SERVER_HOST="${SERVER_HOST:-0.0.0.0}"
export SERVER_PORT="${SERVER_PORT:-8000}"
export SERVER_WORKERS="${SERVER_WORKERS:-4}"
export ENVIRONMENT="${ENVIRONMENT:-development}"
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Optional: Set ASTGREP defaults if not set
export ASTGREP_ENABLED="${ASTGREP_ENABLED:-true}"
export ASTGREP_RULES_PATH="${ASTGREP_RULES_PATH:-/tmp/ast-grep-rules}"

echo "Server Configuration:"
echo "  Host: $SERVER_HOST"
echo "  Port: $SERVER_PORT"
echo "  Workers: $SERVER_WORKERS"
echo "  Environment: $ENVIRONMENT"
echo "  Log Level: $LOG_LEVEL"
echo ""

# Check if port is already in use
if lsof -Pi :$SERVER_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  Warning: Port $SERVER_PORT is already in use!"
    echo "   Kill existing process with: lsof -ti:$SERVER_PORT | xargs kill -9"
    read -p "   Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

echo "Starting server..."
echo ""

# Start the server
cd "$(dirname "$0")"
python -m coderabbit_ai.server &
SERVER_PID=$!

echo "✅ Server started (PID: $SERVER_PID)"
echo ""
echo "Dashboard URLs:"
echo "  🌐 Dashboard:  http://localhost:$SERVER_PORT/dashboard"
echo "  📊 Health:     http://localhost:$SERVER_PORT/health"
echo "  📚 API Docs:   http://localhost:$SERVER_PORT/docs"
echo "  📝 Stats:      http://localhost:$SERVER_PORT/pipeline/stats"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Wait for interrupt
trap "echo ''; echo 'Stopping server...'; kill $SERVER_PID 2>/dev/null; exit 0" INT TERM

# Keep script running
wait $SERVER_PID
