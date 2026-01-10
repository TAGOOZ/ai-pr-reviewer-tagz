#!/bin/bash
# Simple Start Script

echo "======================================"
echo "Starting CodeRabbit Services"
echo "======================================"

# Kill any existing
pkill -f coderabbit 2>/dev/null
sleep 2

# Start Python AI Pipeline
echo "🚀 Starting Python AI Pipeline..."
cd "$(dirname "$0")/.."
nohup /teamspace/studios/this_studio/.local/bin/poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000 > logs/ai-pipeline.log 2>&1 &

PYTHON_PID=$!
echo "   Python AI Pipeline started (PID: $PYTHON_PID)"

# Give Python time to start
sleep 3

# Start API Gateway (without cargo)
echo "🚀 Starting API Gateway..."
cd "$(dirname "$0")/.."
# Run Rust directly if cargo available, otherwise skip
if command -v cargo; then
    nohup cargo run --bin coderabbit-api-gateway > logs/api-gateway.log 2>&1 &
    API_PID=$!
    echo "   API Gateway started (PID: $API_PID)"
else
    echo "   ⚠️  cargo not found, API Gateway not started"
    API_PID=""
fi

echo ""
echo "======================================"
echo "Service Status"
echo "======================================"

if [ -n "$PYTHON_PID" ] && ps -p $PYTHON_PID > /dev/null 2>&1; then
    echo "✅ Python AI Pipeline: Running (PID: $PYTHON_PID)"
else
    echo "❌ Python AI Pipeline: FAILED"
fi

if [ -n "$API_PID" ] && ps -p $API_PID > /dev/null 2>&1; then
    echo "✅ API Gateway: Running (PID: $API_PID)"
else
    echo "❌ API Gateway: FAILED or cargo not available"
fi

echo "======================================"
echo ""
echo "Logs:"
echo "  API Gateway: tail -f logs/api-gateway.log"
echo "  Python AI Pipeline: tail -f logs/ai-pipeline.log"
echo ""
echo "To stop: pkill -f coderabbit"
