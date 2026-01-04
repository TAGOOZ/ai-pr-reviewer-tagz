#!/bin/bash
# Test CodeRabbit AI review locally on the example vulnerabilities

echo "🚀 Starting CodeRabbit AI Services"
echo "====================================="

# Kill any existing services
pkill -f "uvicorn.*coderabbit" 2>/dev/null
pkill -f "uvicorn.*mock" 2>/dev/null

# Start Mock API Gateway
cd /teamspace/studios/this_studio/ai-pr-reviewer-tagz
echo ""
echo "1. Starting Mock API Gateway on port 8080..."
API_GATEWAY_PORT=8080 poetry run uvicorn scripts.mock_api_gateway:app --host 127.0.0.1 --port 8080 > /tmp/mock-api-gateway.log 2>&1 &
API_PID=$!
echo "   Mock API Gateway PID: $API_PID"

# Start Python AI Pipeline
echo ""
echo "2. Starting Python AI Pipeline on port 8000..."
sleep 2
OPENAI_API_KEY=sk-dummy PORT=8000 poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000 > /tmp/ai-pipeline.log 2>&1 &
PYTHON_PID=$!
echo "   Python AI Pipeline PID: $PYTHON_PID"

# Wait for services to start
echo ""
echo "3. Waiting for services to start (15s)..."
sleep 15

# Check health
echo ""
echo "4. Checking service health..."
echo "   API Gateway:"
curl -s http://localhost:8080/health | head -c 100 || echo "   ❌ Not responding"

echo ""
echo "   Python AI Pipeline:"
curl -s http://localhost:8000/health || echo "   ❌ Not responding"

echo ""
echo "====================================="
echo "✅ All services started!"
echo ""
echo "5. Running system tests..."
poetry run python scripts/run_system_tests.py

# Cleanup on Ctrl+C
trap "kill $API_PID $PYTHON_PID 2>/dev/null; echo ''; echo 'Services stopped'; exit 0" INT TERM

# Keep services running
echo ""
echo "====================================="
echo "Services running. Press Ctrl+C to stop."
echo "Logs:"
echo "  API Gateway: /tmp/mock-api-gateway.log"
echo "  AI Pipeline:   /tmp/ai-pipeline.log"
echo "====================================="

wait
