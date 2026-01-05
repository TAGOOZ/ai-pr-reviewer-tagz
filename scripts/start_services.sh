#!/bin/bash

# Start All Services (API Gateway + Python AI Pipeline)
# Using: Gemini for review, Cohere for embeddings

set -e

echo "======================================"
echo "Starting CodeRabbit Services"
echo "======================================"
echo ""

# Configuration
HOST="${PYTHON_SERVER_HOST:-127.0.0.1}"
PORT="${PYTHON_SERVER_PORT:-8000}"
ENVIRONMENT="${ENVIRONMENT:-development}"

# AI Configuration
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export ANTHROPIC_API_KEY=""  # DISABLED
export COHERE_API_KEY="${COHERE_API_KEY:-}"
export USE_GEMINI_FOR_REVIEW=true
export USE_COHERE_FOR_EMBEDDING=true

# Display configuration
echo "🤖️  AI Services:"
echo "   Review Engine: Gemini (USE_GEMINI_FOR_REVIEW=$USE_GEMINI_FOR_REVIEW)"
echo "   Embedding Engine: Cohere (USE_COHERE_FOR_EMBEDDING=$USE_COHERE_FOR_EMBEDDING)"
echo "   Anthropic: DISABLED"
echo ""
echo "🖥️  API Gateway:"
echo "   Host: $HOST"
echo "   Port: 3000"
echo "   Environment: $ENVIRONMENT"
echo ""
echo "🐍  Python AI Pipeline:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Workers: 1"
echo "======================================"
echo ""

# Kill any existing services
echo "Stopping existing services..."
pkill -f "coderabbit" 2>/dev/null
sleep 2
echo ""

# Start API Gateway
echo "🚀 Starting API Gateway..."
cd "$(dirname "$0")/.."
cargo run --bin coderabbit-api-gateway &
API_PID=$!
echo "   API Gateway started (PID: $API_PID)"
echo ""

# Start Python AI Pipeline
echo "🚀 Starting Python AI Pipeline..."
cd "$(dirname "$0")/.."
poetry run uvicorn coderabbit_ai.server:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers 1 \
    --log-level info &
PYTHON_PID=$!
echo "   Python AI Pipeline started (PID: $PYTHON_PID)"
echo ""

# Wait for services to start
sleep 5

# Check if services are running
echo ""
echo "======================================"
echo "Service Status"
echo "======================================"

if ps -p $API_PID > /dev/null 2>&1; then
    echo "✅ API Gateway: Running (PID: $API_PID)"
else
    echo "❌ API Gateway: FAILED to start"
fi

if ps -p $PYTHON_PID > /dev/null 2>&1; then
    echo "✅ Python AI Pipeline: Running (PID: $PYTHON_PID)"
else
    echo "❌ Python AI Pipeline: FAILED to start"
fi

echo "======================================"
echo ""
echo "To stop services, run: ./stop_services.sh"
echo "To view logs:"
echo "  API Gateway: tail -f logs/api-gateway.log"
echo "  Python AI: tail -f logs/ai-pipeline.log"
echo ""
echo "Webhook URL: https://earnings-statistics-minimum-candy.trycloudflare.com/api/v1/webhook/github"
