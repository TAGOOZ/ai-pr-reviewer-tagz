#!/bin/bash

# Stop All Services

echo "======================================"
echo "Stopping CodeRabbit Services"
echo "======================================"
echo ""

# Kill all coderabbit processes
echo "Stopping all CodeRabbit processes..."
pkill -f "coderabbit" 2>/dev/null

sleep 2

# Verify stopped
if ps aux | grep -q coderabbit; then
    echo "⚠️  Some processes still running, force killing..."
    pkill -9 -f "coderabbit" 2>/dev/null
fi

echo ""
echo "✓ All services stopped"
echo ""
echo "To restart, run: ./start_services.sh"
echo ""
