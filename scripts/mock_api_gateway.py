#!/usr/bin/env python3
"""Simple mock API Gateway for testing purposes.

This is a minimal FastAPI server that mimics API Gateway health endpoints
and forwards GitHub webhooks to Python AI Pipeline for review.
"""

from fastapi import FastAPI, Request
from datetime import datetime
import os
import httpx

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


@app.post("/webhooks/github")
async def github_webhook(request: Request):
    """
    Receive GitHub webhook and forward to Python AI Pipeline for review.

    This endpoint receives PR events from GitHub and triggers
    CodeRabbit AI review process.
    """
    try:
        webhook_data = await request.json()

        # Check if this is a PR event that needs review
        action = webhook_data.get("action", "")
        if action not in ["opened", "synchronize", "reopened"]:
            return {
                "status": "ignored",
                "reason": f"Action '{action}' does not trigger review",
            }

        # Extract PR info
        pull_request = webhook_data.get("pull_request", {})
        repository = webhook_data.get("repository", {})

        if not pull_request or not repository:
            return {"status": "error", "reason": "Invalid webhook payload"}

        pr_number = pull_request.get("number")
        repo_name = repository.get("full_name", repository.get("name", ""))

        print(
            f"📥 Received webhook for PR #{pr_number} in {repo_name} (action: {action})"
        )

        # Trigger review with Python AI Pipeline
        async with httpx.AsyncClient(timeout=60.0) as client:
            review_request = {
                "repository": {
                    "id": str(repository.get("id", "")),
                    "name": repository.get("name", ""),
                    "owner": repository.get("owner", {}).get("login", ""),
                    "platform": "github",
                    "clone_url": repository.get("clone_url", ""),
                    "default_branch": repository.get("default_branch", "main"),
                },
                "pull_request": {
                    "number": pr_number,
                    "id": str(pull_request.get("id", "")),
                    "title": pull_request.get("title", ""),
                    "body": pull_request.get("body", ""),
                    "author": pull_request.get("user", {}).get("login", ""),
                    "head": {
                        "ref": pull_request.get("head", {}).get("ref", ""),
                        "sha": pull_request.get("head", {}).get("sha", ""),
                    },
                    "base": {"ref": pull_request.get("base", {}).get("ref", "")},
                    "state": pull_request.get("state", "open"),
                },
                "config": {
                    "max_comments": 50,
                    "enable_security": True,
                    "enable_performance": True,
                    "enable_style": True,
                },
            }

            response = await client.post(
                "http://127.0.0.1:8000/review",
                json=review_request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                print(f"✅ Review triggered successfully for PR #{pr_number}")
                return {"status": "review_triggered", "pr_number": pr_number}
            else:
                print(f"❌ Failed to trigger review: {response.status_code}")
                print(f"Response: {response.text}")
                return {
                    "status": "error",
                    "pr_number": pr_number,
                    "error": response.text,
                }

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_GATEWAY_PORT", "8080"))
    host = os.getenv("API_GATEWAY_HOST", "127.0.0.1")

    print(f"🚀 Starting Mock API Gateway")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Health: http://{host}:{port}/health")
    print(f"Ready:  http://{host}:{port}/ready")
    print(f"Webhook: http://{host}:{port}/webhooks/github")
    print("")

    uvicorn.run(app, host=host, port=port, log_level="info")
