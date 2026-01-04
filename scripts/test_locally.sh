#!/bin/bash
# Test CodeRabbit AI by simulating webhook locally

echo "🚀 Testing CodeRabbit AI Review Locally"
echo "========================================="

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
echo "4. Checking service health..."
echo ""
API_HEALTH=$(curl -s http://localhost:8080/health 2>/dev/null)
PYTHON_HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null)

if [ -n "$API_HEALTH" ]; then
    echo "✅ API Gateway: $API_HEALTH"
else
    echo "❌ API Gateway: NOT RESPONDING"
fi

if [ -n "$PYTHON_HEALTH" ]; then
    echo "✅ Python AI Pipeline: $PYTHON_HEALTH"
else
    echo "❌ Python AI Pipeline: NOT RESPONDING"
fi

# Get PR #4 files from GitHub
echo ""
echo "5. Fetching PR #4 files..."
echo ""

# Trigger CodeRabbit review
echo "6. Triggering CodeRabbit review for PR #4..."
echo ""

REVIEW_REQUEST='{
  "repository": {
    "id": "789012",
    "name": "ai-pr-reviewer-tagz",
    "owner": "TAGOOZ",
    "platform": "github",
    "clone_url": "https://github.com/TAGOOZ/ai-pr-reviewer-tagz.git",
    "default_branch": "main"
  },
  "pull_request": {
    "number": 4,
    "id": "123456789",
    "title": "Test PR: Security vulnerabilities for CodeRabbit AI review",
    "body": "This PR is intentionally designed with security vulnerabilities to test CodeRabbit AI review system'\''s ability to detect and report security issues.",
    "author": "TAGOOZ",
    "head": {
      "ref": "feature/test-coderabbit-real-review",
      "sha": "test123"
    },
    "base": {"ref": "main"},
    "html_url": "https://github.com/TAGOOZ/ai-pr-reviewer-tagz/pull/4",
    "state": "open",
    "created_at": "2026-01-04T00:16:44Z",
    "updated_at": "2026-01-04T00:16:44Z"
  },
  "config": {
    "max_comments": 50,
    "enable_security": true,
    "enable_performance": true,
    "enable_style": true
  }
}'

echo "Sending review request..."
echo ""

RESPONSE=$(curl -s -X POST http://localhost:8000/review \
  -H "Content-Type: application/json" \
  -d "$REVIEW_REQUEST" 2>&1)

echo "$RESPONSE" | head -100

echo ""
echo "========================================="
echo ""
echo "📊 Check results:"
echo "  - Look for review comments identifying security vulnerabilities"
echo "  - Check for SQL injection alerts"
echo "  - Check for command injection alerts"
echo "  - Check for path traversal alerts"
echo ""
echo "📁 Logs:"
echo "  - API Gateway: /tmp/mock-api.log"
echo "  - AI Pipeline:   /tmp/ai-pipeline.log"
echo ""
echo "Press Ctrl+C to stop services"
echo ""

# Keep services running
trap "kill $API_PID $PYTHON_PID 2>/dev/null; echo ''; echo 'Services stopped'; exit 0" INT TERM

wait
