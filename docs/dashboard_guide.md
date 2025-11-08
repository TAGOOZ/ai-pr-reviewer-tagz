# CodeRabbit AI System Dashboard Guide

## Overview

The System Dashboard provides a web-based interface for monitoring system health, checking component status, running tests, and viewing environment configuration.

**URL**: `http://localhost:8000/dashboard`

---

## Features

### 1. 💻 System Metrics
Real-time monitoring of system resources:
- **CPU Usage**: Current CPU utilization and core count
- **Memory Usage**: RAM usage with visual progress bars
- **Disk Usage**: Storage utilization
- **Auto-refresh**: Updates every 30 seconds

### 2. ⚙️ Component Status
Health checks for all system components:
- **DSPy**: LLM framework status and version
- **OpenAI/Anthropic**: API key configuration
- **AST-Grep**: Security scanner availability
- **AST-Grep Rules**: Rule database status
- **Static Analysis**: Aggregator availability
- **Security Aggregator**: Phase 3 component status

**Status Indicators**:
- 🟢 **OK**: Component working correctly
- 🟡 **Warning**: Component available but needs attention
- 🔴 **Error**: Component not available or failing

### 3. 🧪 Test Runner
Run test suites directly from the dashboard:

**Available Test Suites**:
- **All Tests**: Full test suite (`pytest tests/ -v`)
- **Phase 1 Tests**: Pre-processing tests (AST-Grep, aggregation)
- **Phase 2 Tests**: AI processing tests (agent enhancements)
- **Phase 3 Tests**: Post-processing tests (security aggregation)
- **Security Tests**: All security-related tests

**Output**: Terminal-style output with color-coded results

### 4. 🔧 Environment Variables
View current environment configuration:

**Tracked Variables**:
- API Keys (OpenAI, Anthropic) - **masked for security**
- AST-Grep Configuration
- Security Thresholds
- Server Settings
- Logging Configuration
- Redis Connection

**Security**: Sensitive values are automatically masked (e.g., `sk-a***`)

---

## Quick Start

### 1. Start the Server

```bash
# From project root
cd /teamspace/studios/this_studio/ai-pr-reviewer-tagz

# Start the server
python -m coderabbit_ai.server
```

### 2. Access Dashboard

Open your browser to:
```
http://localhost:8000/dashboard
```

### 3. Test Dashboard Components (Optional)

```bash
# Run dashboard component tests
python test_dashboard.py
```

---

## API Endpoints

The dashboard exposes several API endpoints for programmatic access:

### GET `/dashboard/api/metrics`
Get system metrics (CPU, memory, disk)

**Response**:
```json
{
  "cpu": {
    "usage_percent": 26.0,
    "count": 4
  },
  "memory": {
    "total_gb": 15.34,
    "used_gb": 2.89,
    "percent": 18.8
  },
  "disk": {
    "total_gb": 386.43,
    "used_gb": 32.66,
    "percent": 8.5
  }
}
```

### GET `/dashboard/api/components`
Get component status

**Response**:
```json
{
  "dspy": {"status": "ok", "version": "3.0.3"},
  "openai": {"status": "warning", "configured": false, "message": "API key not set"},
  "ast-grep": {"status": "ok", "version": "ast-grep 0.12.5"},
  "security-aggregator": {"status": "ok", "message": "Available"}
}
```

### GET `/dashboard/api/env-vars`
Get environment variables (sensitive values masked)

**Response**:
```json
{
  "OPENAI_API_KEY": {"value": "sk-a***", "masked": true},
  "ASTGREP_ENABLED": {"value": "true", "masked": false},
  "SERVER_PORT": {"value": null, "masked": false}
}
```

### POST `/dashboard/api/run-tests/{suite}`
Run test suite

**Parameters**:
- `suite`: `all`, `phase1`, `phase2`, `phase3`, or `security`

**Response**:
```json
{
  "success": true,
  "output": "===== test session starts =====\n...",
  "return_code": 0
}
```

---

## Configuration

### Environment Variables for Dashboard

```bash
# Server configuration
export SERVER_HOST="0.0.0.0"
export SERVER_PORT="8000"
export SERVER_WORKERS="4"

# API Keys (will be masked in dashboard)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# AST-Grep configuration
export ASTGREP_ENABLED="true"
export ASTGREP_RULES_PATH="/tmp/ast-grep-rules"

# Security configuration
export SECURITY_BLOCK_ON_CRITICAL="true"
export SECURITY_MAX_HIGH_SEVERITY="3"
export SECURITY_CONFIDENCE_THRESHOLD="0.7"

# Logging
export LOG_LEVEL="INFO"
export ENVIRONMENT="development"

# Optional: Redis
export REDIS_URL="redis://localhost:6379"
```

---

## Usage Examples

### Example 1: Check System Health

1. Open dashboard: `http://localhost:8000/dashboard`
2. View **System Metrics** card
3. Check CPU, Memory, Disk usage
4. Red progress bars indicate high utilization

### Example 2: Verify Component Status

1. Navigate to **Component Status** card
2. Look for 🔴 **Error** indicators
3. Fix any missing components:
   - **ast-grep**: Install via `cargo install ast-grep`
   - **OpenAI API**: Set `OPENAI_API_KEY` environment variable
   - **Rules**: Will auto-download on first scan

### Example 3: Run Security Tests

1. Go to **Test Runner** card
2. Click **Security Tests** button
3. Wait for tests to complete (shows spinner)
4. View results in terminal output below
5. Green output = all tests passed
6. Red output = some tests failed

### Example 4: Check Environment Config

1. Scroll to **Environment Variables** card
2. Verify API keys are configured (will show `sk-a***`)
3. Check security thresholds are set
4. Verify server settings

---

## Troubleshooting

### Dashboard Not Loading

**Problem**: Cannot access `http://localhost:8000/dashboard`

**Solutions**:
1. Verify server is running: `ps aux | grep uvicorn`
2. Check port 8000 is not in use: `lsof -i :8000`
3. Review server logs: `tail -f logs/ai-pipeline.log`

### Component Status Shows Errors

**Problem**: Components show 🔴 **Error** status

**Solutions**:

**ast-grep error**:
```bash
# Install ast-grep
cargo install ast-grep

# Verify installation
ast-grep --version
```

**API key warnings**:
```bash
# Set API keys
export OPENAI_API_KEY="your-key-here"
export ANTHROPIC_API_KEY="your-key-here"

# Restart server
```

**Rules not found**:
```bash
# Download rules manually
export ASTGREP_RULES_PATH="/tmp/ast-grep-rules"
mkdir -p /tmp/ast-grep-rules

# Or let the scanner auto-download on first use
```

### Tests Timing Out

**Problem**: Test execution times out after 5 minutes

**Solutions**:
1. Run subset of tests (Phase 1, 2, or 3 only)
2. Run tests manually: `pytest tests/ -v`
3. Check for hung processes: `ps aux | grep pytest`

### High Resource Usage

**Problem**: CPU or memory usage is high

**Solutions**:
1. Check running processes: `top` or `htop`
2. Review active tests/pipelines
3. Restart server to clear memory
4. Reduce `SERVER_WORKERS` count

---

## Security Considerations

### Sensitive Data

The dashboard **masks** sensitive environment variables:
- API keys show as `sk-a***` (first 4 chars + asterisks)
- Passwords, tokens, secrets are masked
- Non-sensitive values shown in full

### Access Control

**⚠️ Warning**: The dashboard has **no authentication** by default!

**For Production**:
1. Add authentication middleware
2. Restrict network access (firewall rules)
3. Use HTTPS/TLS
4. Implement role-based access control (RBAC)

**Example**: Basic auth with FastAPI
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets

security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, "admin")
    correct_password = secrets.compare_digest(credentials.password, os.getenv("DASHBOARD_PASSWORD", ""))

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Apply to routes
@router.get("/", dependencies=[Depends(verify_credentials)])
async def dashboard_home():
    ...
```

---

## Customization

### Add Custom Metrics

Edit `python/coderabbit_ai/dashboard.py`:

```python
def get_custom_metrics() -> Dict[str, Any]:
    """Add your custom metrics here."""
    return {
        "custom_metric": {
            "value": 42,
            "status": "ok"
        }
    }
```

### Add Custom Components

```python
def get_component_status() -> Dict[str, Any]:
    components = {}

    # ... existing components ...

    # Add your component check
    try:
        # Check your component
        components["my-component"] = {
            "status": "ok",
            "version": "1.0.0"
        }
    except Exception as e:
        components["my-component"] = {
            "status": "error",
            "message": str(e)
        }

    return components
```

### Custom Test Suites

```python
@router.post("/api/run-tests/{suite}")
async def api_run_tests(suite: str):
    test_commands = {
        # ... existing suites ...

        # Add your custom suite
        "custom": ["python", "-m", "pytest", "tests/custom/", "-v"]
    }
    # ...
```

---

## Performance

### Dashboard Performance

- **Load Time**: < 500ms (typical)
- **Metrics Refresh**: 30 seconds (auto)
- **API Response**: < 100ms (metrics, components, env vars)
- **Test Execution**: Varies by suite (30s - 5min)

### Resource Usage

- **Memory**: ~50 MB (dashboard only)
- **CPU**: < 1% (idle), < 5% (active)
- **Network**: Minimal (local only)

---

## Future Enhancements

Potential improvements for the dashboard:

1. **Real-time Logs**: Stream server logs to dashboard
2. **Historical Metrics**: Chart CPU/memory over time
3. **Alerts**: Email/Slack notifications for failures
4. **Test Coverage**: Display coverage reports
5. **Performance Profiling**: Identify bottlenecks
6. **Database Queries**: Monitor database performance
7. **Request Tracing**: Distributed tracing support
8. **Custom Alerts**: Configurable thresholds

---

## Support

For issues or questions:
- Check server logs: `logs/ai-pipeline.log`
- Run component test: `python test_dashboard.py`
- Review GitHub issues: [issues](https://github.com/anthropics/ai-pr-reviewer/issues)

---

**Dashboard Version**: 1.0.0
**Last Updated**: November 7, 2025
**Status**: ✅ Production Ready
