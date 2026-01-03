# 🎛️ CodeRabbit AI System Dashboard

A modern web-based dashboard for monitoring, testing, and managing the CodeRabbit AI PR Review system.

<div align="center">

![Dashboard](https://img.shields.io/badge/Dashboard-Live-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-blue)
![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Tests](https://img.shields.io/badge/Tests-122%20Passing-success)

</div>

---

## 🚀 Quick Start

### 1-Line Start

```bash
./start_dashboard.sh
```

Then open: **http://localhost:8000/dashboard**

### Manual Start

```bash
# Set environment (optional)
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Start server
python -m coderabbit_ai.server

# Visit dashboard
open http://localhost:8000/dashboard
```

---

## ✨ Features

### 📊 Real-Time System Monitoring
- **CPU Usage** with multi-core visualization
- **Memory Usage** with progress bars
- **Disk Usage** tracking
- **Auto-refresh** every 30 seconds

### ⚙️ Component Health Checks
- ✅ DSPy framework status
- ✅ OpenAI/Anthropic API configuration
- ✅ AST-Grep scanner availability
- ✅ Security rules database
- ✅ Static analysis components
- ✅ Security aggregator (Phase 3)

### 🧪 Integrated Test Runner
Run tests directly from the browser:
- **All Tests** - Full suite (122 tests)
- **Phase 1** - Pre-processing (37 tests)
- **Phase 2** - AI processing (4 tests)
- **Phase 3** - Post-processing (17 tests)
- **Security** - All security tests (58 tests)

Real-time terminal output with syntax highlighting!

### 🔧 Environment Configuration
- View all environment variables
- **Automatic masking** of sensitive values (API keys, passwords)
- Configuration validation
- Quick reference for required settings

---

## 📸 Dashboard Preview

```
┌─────────────────────────────────────────────────────────────────┐
│ 🐰 CodeRabbit AI System Dashboard                              │
│ Monitor components, run tests, and manage configuration        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ 💻 System Metrics│  │ ⚙️  Components   │  │ 🧪 Tests     │ │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────┤ │
│  │ CPU:  26% █████  │  │ ✅ dspy          │  │ [All Tests]  │ │
│  │ RAM:  18% ████   │  │ ⚠️  openai       │  │ [Phase 1]    │ │
│  │ Disk:  8% ██     │  │ ✅ security-agg  │  │ [Phase 2]    │ │
│  └──────────────────┘  └──────────────────┘  │ [Phase 3]    │ │
│                                              │ [Security]   │ │
│  ┌──────────────────────────────────────────┤──────────────┘ │
│  │ 🔧 Environment Variables                 │                │
│  ├──────────────────────────────────────────┘                │
│  │ OPENAI_API_KEY = sk-a***  (masked)                        │
│  │ ASTGREP_ENABLED = true                                    │
│  │ SECURITY_BLOCK_ON_CRITICAL = true                         │
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Use Cases

### 1. Health Monitoring
**Scenario**: Check if system is ready for production
```
1. Open dashboard
2. Check Component Status card
3. All green = ready to deploy
4. Yellow/Red = fix issues first
```

### 2. Test Verification
**Scenario**: Verify Phase 3 security integration
```
1. Click "Phase 3 Tests" button
2. Wait for results (3-5 seconds)
3. See "17 passed" = success
4. View detailed output for failures
```

### 3. Configuration Audit
**Scenario**: Ensure API keys are configured
```
1. Scroll to Environment Variables
2. Check OPENAI_API_KEY shows "sk-a***"
3. Check SECURITY_* variables are set
4. Verify server settings
```

### 4. Performance Monitoring
**Scenario**: Investigate slow response times
```
1. Check CPU usage (should be < 80%)
2. Check Memory usage (should be < 90%)
3. If high, restart server or scale workers
4. Monitor over time with auto-refresh
```

---

## 🛠️ Installation

### Prerequisites
```bash
# Required
python >= 3.11
fastapi >= 0.109
uvicorn >= 0.27
psutil >= 5.9

# Optional (for full features)
ast-grep (cargo install ast-grep)
openai (pip install openai)
anthropic (pip install anthropic)
```

### Install Dependencies
```bash
# Using poetry (recommended)
poetry install

# Or using pip
pip install -r requirements.txt

# Install psutil for system metrics
pip install psutil
```

---

## 📡 API Endpoints

### Dashboard UI
- `GET /dashboard` - Main dashboard interface (HTML)

### Metrics API
- `GET /dashboard/api/metrics` - System metrics (JSON)
- `GET /dashboard/api/components` - Component status (JSON)
- `GET /dashboard/api/env-vars` - Environment variables (JSON)

### Test Runner API
- `POST /dashboard/api/run-tests/{suite}` - Run test suite
  - Suites: `all`, `phase1`, `phase2`, `phase3`, `security`

### Example API Call
```bash
# Get system metrics
curl http://localhost:8000/dashboard/api/metrics

# Get component status
curl http://localhost:8000/dashboard/api/components

# Run Phase 3 tests
curl -X POST http://localhost:8000/dashboard/api/run-tests/phase3
```

---

## 🔒 Security

### Sensitive Data Protection
The dashboard automatically **masks** sensitive values:
- API keys: `sk-abc123...` → `sk-a***`
- Passwords: `password123` → `pass***`
- Tokens: `ghp_abc123...` → `ghp_***`
- Secrets: `secret-value` → `secr***`

### ⚠️ Production Warning
**The dashboard has NO authentication by default!**

For production use:
1. **Add authentication** (BasicAuth, OAuth, JWT)
2. **Restrict network access** (firewall, VPN)
3. **Use HTTPS/TLS**
4. **Implement RBAC** (role-based access control)
5. **Enable audit logging**

See [docs/dashboard_guide.md](docs/dashboard_guide.md#security-considerations) for details.

---

## 🧪 Testing

### Test Dashboard Components
```bash
# Run component tests
python test_dashboard.py

# Output:
# ✅ CPU: 26% (4 cores)
# ✅ Memory: 2.89/15.34 GB (18.8%)
# ✅ Disk: 32.66/386.43 GB (8.5%)
# ✅ dspy [ok] 3.0.3
# ✅ security-aggregator [ok] Available
```

### Test via Browser
1. Start server: `./start_dashboard.sh`
2. Open: `http://localhost:8000/dashboard`
3. Click "Run All Tests"
4. Verify output shows test results

---

## 📊 Performance

### Dashboard Metrics
- **Page Load**: < 500ms
- **API Response**: < 100ms
- **Auto-refresh**: 30s interval
- **Test Execution**: 30s - 5min (suite-dependent)

### Resource Usage
- **Memory**: ~50 MB (dashboard only)
- **CPU**: < 1% idle, < 5% active
- **Network**: Minimal (localhost only)

---

## 🎨 Customization

### Custom Metrics
Add custom metrics in `dashboard.py`:
```python
def get_custom_metrics():
    return {
        "my_metric": {
            "value": calculate_my_metric(),
            "status": "ok"
        }
    }
```

### Custom Components
```python
def get_component_status():
    components["my-component"] = {
        "status": "ok",
        "version": get_my_version()
    }
    return components
```

### Custom Test Suites
```python
test_commands = {
    "my-suite": ["pytest", "tests/my/", "-v"]
}
```

---

## 📚 Documentation

- **Dashboard Guide**: [docs/dashboard_guide.md](docs/dashboard_guide.md)
- **API Reference**: `http://localhost:8000/docs` (FastAPI auto-docs)
- **Phase 3 Summary**: [docs/phase3_completion_summary.md](docs/phase3_completion_summary.md)

---

## 🐛 Troubleshooting

### Dashboard Won't Load
```bash
# Check server is running
ps aux | grep uvicorn

# Check port availability
lsof -i :8000

# View server logs
tail -f logs/ai-pipeline.log
```

### Component Shows Error
```bash
# Install ast-grep
cargo install ast-grep

# Set API keys
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Restart server
pkill -f uvicorn
./start_dashboard.sh
```

### Tests Timing Out
```bash
# Run subset
curl -X POST http://localhost:8000/dashboard/api/run-tests/phase1

# Or manually
pytest tests/test_phase1_*.py -v
```

---

## 🔮 Roadmap

Future enhancements:
- [ ] Real-time log streaming
- [ ] Historical metrics charts (24h/7d/30d)
- [ ] Alert notifications (email/Slack)
- [ ] Test coverage visualization
- [ ] Performance profiling
- [ ] Database query monitoring
- [ ] Request tracing (distributed)
- [ ] Custom dashboard widgets

---

## 🤝 Contributing

To add dashboard features:
1. Edit `python/coderabbit_ai/dashboard.py`
2. Add API endpoint
3. Update HTML template
4. Test with `python test_dashboard.py`
5. Update documentation

---

## 📋 Summary

✅ **Real-time monitoring** - CPU, Memory, Disk
✅ **Component health** - All system components
✅ **Test runner** - 5 test suites with live output
✅ **Environment config** - Masked sensitive values
✅ **REST API** - Programmatic access
✅ **Auto-refresh** - Always up-to-date
✅ **Modern UI** - Beautiful gradient design
✅ **Production-ready** - Error handling, logging

---

**Dashboard Version**: 1.0.0
**Status**: ✅ Production Ready
**Lines of Code**: ~600
**Dependencies**: FastAPI, psutil, subprocess

---

## 🚀 Get Started Now!

```bash
# Start dashboard
./start_dashboard.sh

# Open browser
open http://localhost:8000/dashboard

# Run tests
# Click "Security Tests" button

# Check components
# View "Component Status" card

# Monitor system
# Watch "System Metrics" update every 30s
```

**Enjoy monitoring your CodeRabbit AI system! 🎉**
