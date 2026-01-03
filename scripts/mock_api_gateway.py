#!/usr/bin/env python3
"""Simple mock API Gateway for testing purposes.

This is a minimal FastAPI server that mimics the API Gateway health endpoints
when the actual Rust API Gateway cannot be built/started.
"""

from fastapi import FastAPI
from datetime import datetime
import os

app = FastAPI(title="Mock CodeRabbit API Gateway", version="0.1.0")


@app.get("/health")
async def health_check():
    """Basic health check - always returns healthy."""
    return {
        "status": "healthy",
        "service": "api-gateway-mock",
        "version": "0.1.0-mock",
        "config_env": os.getenv("ENVIRONMENT", "development"),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.get("/ready")
async def ready_check():
    """Readiness check - checks database and Redis."""
    # In a real gateway, this would check actual dependencies
    # For testing, we'll assume dependencies are ready
    return {
        "ready": True,
        "checks": {
            "database": {"status": "ok", "latency_ms": 5},
            "redis": {"status": "ok", "latency_ms": 2},
            "python_service": {"status": "ok", "latency_ms": 10},
        },
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint (mock)."""
    return {"# Mock metrics for testing"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_GATEWAY_PORT", "8080"))
    host = os.getenv("API_GATEWAY_HOST", "127.0.0.1")

    print(f"🚀 Starting Mock API Gateway")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Health: http://{host}:{port}/health")
    print(f"Ready:  http://{host}:{port}/ready")
    print("")

    uvicorn.run(app, host=host, port=port, log_level="info")
