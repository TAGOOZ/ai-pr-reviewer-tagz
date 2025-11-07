"""System Dashboard for CodeRabbit AI Pipeline."""

import os
import subprocess
import json
import psutil
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu": {
                "usage_percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": disk.percent
            }
        }
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        return {}


def get_component_status() -> Dict[str, Any]:
    """Check status of all system components."""
    components = {}

    # Check Python environment
    try:
        import dspy
        components["dspy"] = {"status": "ok", "version": dspy.__version__ if hasattr(dspy, '__version__') else "unknown"}
    except ImportError:
        components["dspy"] = {"status": "error", "message": "Not installed"}

    # Check OpenAI
    openai_key = os.getenv("OPENAI_API_KEY")
    components["openai"] = {
        "status": "ok" if openai_key else "warning",
        "configured": bool(openai_key),
        "message": "API key configured" if openai_key else "API key not set"
    }

    # Check Anthropic
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    components["anthropic"] = {
        "status": "ok" if anthropic_key else "warning",
        "configured": bool(anthropic_key),
        "message": "API key configured" if anthropic_key else "API key not set"
    }

    # Check AST-Grep
    try:
        result = subprocess.run(
            ["ast-grep", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        version = result.stdout.strip() if result.returncode == 0 else "unknown"
        components["ast-grep"] = {
            "status": "ok" if result.returncode == 0 else "error",
            "version": version
        }
    except (FileNotFoundError, subprocess.TimeoutExpired):
        components["ast-grep"] = {"status": "error", "message": "Not installed or not in PATH"}

    # Check AST-Grep rules
    rules_path = os.getenv("ASTGREP_RULES_PATH", "/tmp/ast-grep-rules")
    rules_exist = os.path.exists(rules_path)
    components["ast-grep-rules"] = {
        "status": "ok" if rules_exist else "warning",
        "path": rules_path,
        "exists": rules_exist,
        "message": f"Rules found at {rules_path}" if rules_exist else "Rules not downloaded"
    }

    # Check Static Analysis Aggregator
    try:
        from coderabbit_ai.analyzers import StaticAnalysisAggregator, AstGrepScanner
        components["static-analysis"] = {"status": "ok", "message": "Aggregator available"}
    except ImportError as e:
        components["static-analysis"] = {"status": "error", "message": str(e)}

    # Check Security Aggregator
    try:
        from coderabbit_ai.analyzers import SecurityAggregator
        components["security-aggregator"] = {"status": "ok", "message": "Available"}
    except ImportError as e:
        components["security-aggregator"] = {"status": "error", "message": str(e)}

    # Check Database (if applicable)
    # Add your database check here if needed

    return components


def get_environment_variables() -> Dict[str, Any]:
    """Get relevant environment variables (sanitized)."""
    env_vars = {}

    # Important env vars to show (will mask sensitive values)
    important_vars = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "ASTGREP_ENABLED",
        "ASTGREP_RULES_PATH",
        "ASTGREP_CACHE_TTL",
        "ASTGREP_AUTO_UPDATE",
        "SECURITY_BLOCK_ON_CRITICAL",
        "SECURITY_MAX_HIGH_SEVERITY",
        "SECURITY_CONFIDENCE_THRESHOLD",
        "SERVER_HOST",
        "SERVER_PORT",
        "SERVER_WORKERS",
        "ENVIRONMENT",
        "LOG_LEVEL",
        "REDIS_URL"
    ]

    sensitive_keys = ["KEY", "SECRET", "PASSWORD", "TOKEN"]

    for var in important_vars:
        value = os.getenv(var)
        if value is not None:
            # Mask sensitive values
            if any(sensitive in var.upper() for sensitive in sensitive_keys):
                masked_value = value[:4] + "*" * (len(value) - 4) if len(value) > 4 else "***"
                env_vars[var] = {"value": masked_value, "masked": True}
            else:
                env_vars[var] = {"value": value, "masked": False}
        else:
            env_vars[var] = {"value": None, "masked": False}

    return env_vars


def get_recent_test_results() -> Dict[str, Any]:
    """Get most recent test results if available."""
    try:
        # Check for pytest cache
        cache_dir = Path(".pytest_cache")
        if cache_dir.exists():
            lastfailed_file = cache_dir / "v" / "cache" / "lastfailed"
            if lastfailed_file.exists():
                with open(lastfailed_file) as f:
                    lastfailed = json.load(f)
                    return {
                        "available": True,
                        "last_failed_count": len(lastfailed),
                        "last_failed": list(lastfailed.keys())[:10]  # Show first 10
                    }

        return {"available": False, "message": "No recent test results"}
    except Exception as e:
        logger.error(f"Failed to get test results: {e}")
        return {"available": False, "error": str(e)}


@router.get("/", response_class=HTMLResponse)
async def dashboard_home():
    """Render the dashboard HTML."""
    html_content = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeRabbit AI - System Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        header {
            background: white;
            border-radius: 12px;
            padding: 20px 30px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        header h1 {
            font-size: 28px;
            color: #667eea;
            margin-bottom: 5px;
        }
        header p {
            color: #666;
            font-size: 14px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        .card h2 {
            font-size: 20px;
            margin-bottom: 16px;
            color: #667eea;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status-ok { background: #d1fae5; color: #065f46; }
        .status-warning { background: #fef3c7; color: #92400e; }
        .status-error { background: #fee2e2; color: #991b1b; }
        .metric {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label {
            font-weight: 500;
            color: #555;
        }
        .metric-value {
            font-weight: 600;
            color: #667eea;
        }
        .progress-bar {
            width: 100%;
            height: 8px;
            background: #e5e7eb;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea, #764ba2);
            transition: width 0.3s ease;
        }
        .component-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .component-item:last-child { border-bottom: none; }
        .component-name {
            font-weight: 500;
            color: #555;
        }
        .env-var {
            font-family: 'Courier New', monospace;
            background: #f9fafb;
            padding: 8px 12px;
            border-radius: 6px;
            margin: 8px 0;
            font-size: 13px;
        }
        .env-var-name {
            color: #667eea;
            font-weight: 600;
        }
        .env-var-value {
            color: #333;
        }
        .masked { opacity: 0.6; }
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            margin: 5px;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        button:active { transform: translateY(0); }
        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        #test-output {
            background: #1e1e1e;
            color: #d4d4d4;
            font-family: 'Courier New', monospace;
            padding: 16px;
            border-radius: 8px;
            max-height: 400px;
            overflow-y: auto;
            font-size: 13px;
            line-height: 1.5;
            margin-top: 16px;
            display: none;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-left: 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .refresh-btn {
            float: right;
            padding: 8px 16px;
            font-size: 12px;
        }
        .timestamp {
            font-size: 12px;
            color: #999;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🐰 CodeRabbit AI System Dashboard</h1>
            <p>Monitor components, run tests, and manage configuration</p>
        </header>

        <div class="grid">
            <!-- System Metrics -->
            <div class="card">
                <h2>💻 System Metrics
                    <button class="refresh-btn" onclick="refreshMetrics()">🔄 Refresh</button>
                </h2>
                <div id="system-metrics">
                    <p>Loading...</p>
                </div>
            </div>

            <!-- Component Status -->
            <div class="card">
                <h2>⚙️ Component Status
                    <button class="refresh-btn" onclick="refreshComponents()">🔄 Refresh</button>
                </h2>
                <div id="component-status">
                    <p>Loading...</p>
                </div>
            </div>

            <!-- Test Runner -->
            <div class="card">
                <h2>🧪 Test Runner</h2>
                <div class="button-group">
                    <button onclick="runTests('all')">Run All Tests</button>
                    <button onclick="runTests('phase1')">Phase 1 Tests</button>
                    <button onclick="runTests('phase2')">Phase 2 Tests</button>
                    <button onclick="runTests('phase3')">Phase 3 Tests</button>
                    <button onclick="runTests('security')">Security Tests</button>
                </div>
                <div id="test-output"></div>
            </div>
        </div>

        <!-- Environment Variables -->
        <div class="card">
            <h2>🔧 Environment Variables
                <button class="refresh-btn" onclick="refreshEnvVars()">🔄 Refresh</button>
            </h2>
            <div id="env-vars">
                <p>Loading...</p>
            </div>
        </div>
    </div>

    <script>
        let testRunning = false;

        async function fetchJSON(url) {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            return await response.json();
        }

        async function refreshMetrics() {
            try {
                const data = await fetchJSON('/dashboard/api/metrics');
                const html = `
                    <div class="metric">
                        <span class="metric-label">CPU Usage</span>
                        <span class="metric-value">${data.cpu.usage_percent}% (${data.cpu.count} cores)</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${data.cpu.usage_percent}%"></div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Memory</span>
                        <span class="metric-value">${data.memory.used_gb} / ${data.memory.total_gb} GB (${data.memory.percent}%)</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${data.memory.percent}%"></div>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Disk</span>
                        <span class="metric-value">${data.disk.used_gb} / ${data.disk.total_gb} GB (${data.disk.percent}%)</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${data.disk.percent}%"></div>
                    </div>
                    <div class="timestamp">Last updated: ${new Date().toLocaleTimeString()}</div>
                `;
                document.getElementById('system-metrics').innerHTML = html;
            } catch (error) {
                document.getElementById('system-metrics').innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            }
        }

        async function refreshComponents() {
            try {
                const data = await fetchJSON('/dashboard/api/components');
                let html = '';
                for (const [name, info] of Object.entries(data)) {
                    const statusClass = `status-${info.status}`;
                    html += `
                        <div class="component-item">
                            <span class="component-name">${name}</span>
                            <span class="status-badge ${statusClass}">${info.status}</span>
                        </div>
                    `;
                }
                html += `<div class="timestamp">Last updated: ${new Date().toLocaleTimeString()}</div>`;
                document.getElementById('component-status').innerHTML = html;
            } catch (error) {
                document.getElementById('component-status').innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            }
        }

        async function refreshEnvVars() {
            try {
                const data = await fetchJSON('/dashboard/api/env-vars');
                let html = '';
                for (const [name, info] of Object.entries(data)) {
                    const valueClass = info.masked ? 'masked' : '';
                    const value = info.value !== null ? info.value : '<not set>';
                    html += `
                        <div class="env-var">
                            <span class="env-var-name">${name}</span> =
                            <span class="env-var-value ${valueClass}">${value}</span>
                        </div>
                    `;
                }
                html += `<div class="timestamp">Last updated: ${new Date().toLocaleTimeString()}</div>`;
                document.getElementById('env-vars').innerHTML = html;
            } catch (error) {
                document.getElementById('env-vars').innerHTML = `<p style="color: red;">Error: ${error.message}</p>`;
            }
        }

        async function runTests(suite) {
            if (testRunning) {
                alert('Tests are already running!');
                return;
            }

            testRunning = true;
            const output = document.getElementById('test-output');
            output.style.display = 'block';
            output.innerHTML = `Running ${suite} tests...<span class="spinner"></span>`;

            try {
                const response = await fetch(`/dashboard/api/run-tests/${suite}`, {
                    method: 'POST'
                });
                const data = await response.json();

                if (data.success) {
                    output.innerHTML = `<pre>${data.output}</pre>`;
                } else {
                    output.innerHTML = `<pre style="color: #f87171;">${data.output}</pre>`;
                }
            } catch (error) {
                output.innerHTML = `<pre style="color: #f87171;">Error: ${error.message}</pre>`;
            } finally {
                testRunning = false;
            }
        }

        // Initial load
        refreshMetrics();
        refreshComponents();
        refreshEnvVars();

        // Auto-refresh metrics every 30 seconds
        setInterval(refreshMetrics, 30000);
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)


@router.get("/api/metrics")
async def api_metrics():
    """Get system metrics."""
    return get_system_metrics()


@router.get("/api/components")
async def api_components():
    """Get component status."""
    return get_component_status()


@router.get("/api/env-vars")
async def api_env_vars():
    """Get environment variables."""
    return get_environment_variables()


@router.post("/api/run-tests/{suite}")
async def api_run_tests(suite: str):
    """Run test suite."""
    try:
        # Map suite names to pytest commands
        test_commands = {
            "all": ["python", "-m", "pytest", "tests/", "-v", "--tb=short"],
            "phase1": ["python", "-m", "pytest", "tests/test_astgrep_scanner.py", "tests/test_static_analysis_aggregator.py", "-v"],
            "phase2": ["python", "-m", "pytest", "tests/test_phase2_security_integration.py", "-v"],
            "phase3": ["python", "-m", "pytest", "tests/test_phase3_security_aggregation.py", "-v"],
            "security": ["python", "-m", "pytest", "tests/", "-k", "security", "-v"],
        }

        if suite not in test_commands:
            raise HTTPException(status_code=400, detail=f"Unknown test suite: {suite}")

        # Run tests
        result = subprocess.run(
            test_commands[suite],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        output = result.stdout + "\n" + result.stderr
        success = result.returncode == 0

        return {
            "success": success,
            "output": output,
            "return_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "Test execution timed out after 5 minutes"
        }
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        raise HTTPException(status_code=500, detail=str(e))
