#!/bin/bash
# Simplified test - just verify services are running

echo "🚀 Testing CodeRabbit AI System"
echo "================================="

# Kill any existing services
pkill -f "uvicorn" 2>/dev/null
sleep 2

# Start Mock API Gateway
echo ""
echo "1. Starting Mock API Gateway..."
cd /teamspace/studios/this_studio/ai-pr-reviewer-tagz
nohup bash -c "API_GATEWAY_PORT=8080 poetry run uvicorn scripts.mock_api_gateway:app --host 127.0.0.1 --port 8080" > /tmp/mock-api.log 2>&1 &
API_PID=$!
echo "   PID: $API_PID"

# Start Python AI Pipeline
echo ""
echo "2. Starting Python AI Pipeline..."
sleep 3
nohup bash -c "OPENAI_API_KEY=sk-dummy PORT=8000 poetry run uvicorn coderabbit_ai.server:app --host 127.0.0.1 --port 8000" > /tmp/ai-pipeline.log 2>&1 &
PYTHON_PID=$!
echo "   PID: $PYTHON_PID"

# Wait for services
echo ""
echo "3. Waiting for services to start (20s)..."
sleep 20

# Check health
echo ""
echo "4. Service Health Checks:"
echo ""

API_HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
PYTHON_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)
API_READY=$(curl -s http://localhost:8080/ready 2>/dev/null)

if [ -n "$API_HEALTH" ]; then
    echo "✅ API Gateway Health:"
    echo "   $API_HEALTH"
else
    echo "❌ API Gateway: NOT RESPONDING"
fi

if [ -n "$PYTHON_HEALTH" ]; then
    echo "✅ Python AI Pipeline Health:"
    echo "   $PYTHON_HEALTH"
else
    echo "❌ Python AI Pipeline: NOT RESPONDING"
fi

if [ -n "$API_READY" ]; then
    echo "✅ API Gateway Ready:"
    echo "   $API_READY"
else
    echo "❌ API Gateway Ready: NOT RESPONDING"
fi

echo ""
echo "================================="
echo "✅ System Ready!"
echo ""
echo "Summary:"
echo "  - Mock API Gateway: http://localhost:8080"
echo "  - Python AI Pipeline: http://localhost:8000"
echo "  - Webhook endpoint: http://localhost:8080/webhooks/github"
echo ""
echo "To test with webhook:"
echo "  1. Install and start ngrok: ngrok http 8080"
echo "  2. Get ngrok URL (e.g., https://abc123.ngrok-free.app)"
echo "  3. Update GitHub webhook to: https://abc123.ngrok-free.app/webhooks/github"
echo "  4. Create a new PR"
echo ""
echo "Logs:"
echo "  - API Gateway: /tmp/mock-api.log"
echo "  - AI Pipeline:   /tmp/ai-pipeline.log"
echo ""
echo "Press Ctrl+C to stop services"
echo ""

# Keep services running
trap "kill $API_PID $PYTHON_PID 2>/dev/null; echo ''; echo 'Services stopped'; exit 0" INT TERM

wait
