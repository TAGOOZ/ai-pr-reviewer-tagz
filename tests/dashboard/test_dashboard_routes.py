"""Unit tests for Dashboard."""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi.responses import HTMLResponse
import psutil

from coderabbit_ai.dashboard import (
    get_system_metrics,
    get_component_status,
    get_environment_variables,
    get_recent_test_results,
    dashboard_home,
    api_metrics,
    api_components,
    api_env_vars,
    api_run_tests,
    router
)


@pytest.fixture
def client():
    """Create a test client for dashboard routes."""
    return TestClient(router)


class TestSystemMetrics:
    """Test suite for get_system_metrics()."""

    @patch('coderabbit_ai.dashboard.psutil.cpu_percent')
    @patch('coderabbit_ai.dashboard.psutil.cpu_count')
    @patch('coderabbit_ai.dashboard.psutil.virtual_memory')
    @patch('coderabbit_ai.dashboard.psutil.disk_usage')
    def test_get_system_metrics_success(self, mock_cpu, mock_count, mock_memory, mock_disk):
        """Test successful retrieval of system metrics."""
        mock_cpu.return_value = 45.5
        mock_count.return_value = 4
        mock_memory.return_value = Mock(total=16*1024**3, used=8*1024**3, percent=50.0)
        mock_disk.return_value = Mock(total=500*1024**3, used=250*1024**3, percent=50.0)

        result = get_system_metrics()

        assert "cpu" in result
        assert result["cpu"]["usage_percent"] == 45.5
        assert result["cpu"]["count"] == 4

        assert "memory" in result
        assert result["memory"]["total_gb"] == 16.0
        assert result["memory"]["used_gb"] == 8.0
        assert result["memory"]["percent"] == 50.0

        assert "disk" in result
        assert result["disk"]["total_gb"] == 500.0
        assert result["disk"]["used_gb"] == 250.0
        assert result["disk"]["percent"] == 50.0

    @patch('coderabbit_ai.dashboard.psutil.cpu_percent')
    def test_get_system_metrics_failure(self, mock_cpu):
        """Test handling of psutil failure."""
        mock_cpu.side_effect = Exception("Failed to get CPU metrics")

        result = get_system_metrics()

        assert result == {}


class TestComponentStatus:
    """Test suite for get_component_status()."""

    @patch.dict(os.environ, {}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_component_status_dspy_installed(self, mock_getenv):
        """Test DSPy component installed."""
        mock_getenv.side_effect = [
            "test-dspy-key",  # DSPy
            "test-openai-key",  # OpenAI
            None,  # Anthropic
            None  # AST-Grep rules path
        ]

        with patch('coderabbit_ai.dashboard.dspy') as mock_dspy:
            mock_dspy.__version__ = "2.5.0"

            result = get_component_status()

            assert "dspy" in result
            assert result["dspy"]["status"] == "ok"
            assert result["dspy"]["version"] == "2.5.0"

    @patch.dict(os.environ, {}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_component_status_openai_missing(self, mock_getenv):
        """Test OpenAI component not configured."""
        mock_getenv.side_effect = [
            None,  # DSPy (will fail import)
            None,  # OpenAI
            None,  # Anthropic
            None
        ]

        result = get_component_status()

        assert "openai" in result
        assert result["openai"]["status"] == "warning"
        assert result["openai"]["configured"] is False

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_component_status_astgrep_installed(self, mock_run):
        """Test AST-Grep component installed."""
        mock_result = Mock(
            stdout="ast-grep 0.233.0",
            returncode=0
        )
        mock_run.return_value = mock_result

        result = get_component_status()

        assert "ast-grep" in result
        assert result["ast-grep"]["status"] == "ok"
        assert result["ast-grep"]["version"] == "0.233.0"

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_component_status_astgrep_not_found(self, mock_run):
        """Test AST-Grep not in PATH."""
        mock_run.side_effect = FileNotFoundError("ast-grep not found")

        result = get_component_status()

        assert "ast-grep" in result
        assert result["ast-grep"]["status"] == "error"
        assert result["ast-grep"]["message"] == "Not installed or not in PATH"

    @patch('coderabbit_ai.dashboard.os.path.exists')
    def test_component_status_astgrep_rules_exist(self, mock_exists):
        """Test AST-Grep rules path exists."""
        mock_exists.return_value = True
        mock_exists.side_effect = lambda path: path == "/tmp/ast-grep-rules"

        result = get_component_status()

        assert "ast-grep-rules" in result
        assert result["ast-grep-rules"]["status"] == "ok"
        assert result["ast-grep-rules"]["exists"] is True

    @patch('coderabbit_ai.dashboard.os.path.exists')
    def test_component_status_astgrep_rules_not_exist(self, mock_exists):
        """Test AST-Grep rules path doesn't exist."""
        mock_exists.return_value = False

        result = get_component_status()

        assert "ast-grep-rules" in result
        assert result["ast-grep-rules"]["status"] == "warning"
        assert result["ast-grep-rules"]["exists"] is False

    @patch('coderabbit_ai.dashboard.os.path.exists')
    @patch.dict(os.environ, {"ASTGREP_RULES_PATH": "/custom/path"}, clear=True)
    def test_component_status_custom_astgrep_path(self, mock_exists):
        """Test custom AST-Grep rules path."""
        mock_exists.return_value = True
        mock_exists.side_effect = lambda path: path == "/custom/path"

        result = get_component_status()

        assert "ast-grep-rules" in result
        assert result["ast-grep-rules"]["path"] == "/custom/path"

    @patch('coderabbit_ai.dashboard.os.path.exists')
    @patch.dict(os.environ, {}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_component_status_static_analysis_aggregator_import_success(self, mock_exists, mock_getenv):
        """Test static analysis aggregator imported successfully."""
        mock_exists.return_value = True

        with patch('coderabbit_ai.dashboard.StaticAnalysisAggregator') as mock_agg:
            result = get_component_status()

            assert "static-analysis" in result
            assert result["static-analysis"]["status"] == "ok"

    @patch('coderabbit_ai.dashboard.os.path.exists')
    def test_component_status_static_analysis_import_failure(self, mock_exists):
        """Test static analysis aggregator import failed."""
        mock_exists.return_value = False

        with patch('coderabbit_ai.dashboard.StaticAnalysisAggregator', side_effect=ImportError("Module not found")):
            result = get_component_status()

            assert "static-analysis" in result
            assert result["static-analysis"]["status"] == "error"
            assert "Module not found" in result["static-analysis"]["message"]

    @patch('coderabbit_ai.dashboard.os.path.exists')
    @patch.dict(os.environ, {}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_component_status_security_aggregator_import_success(self, mock_exists, mock_getenv):
        """Test security aggregator imported successfully."""
        mock_exists.return_value = True

        with patch('coderabbit_ai.dashboard.SecurityAggregator') as mock_agg:
            result = get_component_status()

            assert "security-aggregator" in result
            assert result["security-aggregator"]["status"] == "ok"

    @patch('coderabbit_ai.dashboard.os.path.exists')
    def test_component_status_security_aggregator_import_failure(self, mock_exists):
        """Test security aggregator import failed."""
        mock_exists.return_value = False

        with patch('coderabbit_ai.dashboard.SecurityAggregator', side_effect=ImportError("Module not found")):
            result = get_component_status()

            assert "security-aggregator" in result
            assert result["security-aggregator"]["status"] == "error"
            assert "Module not found" in result["security-aggregator"]["message"]


class TestEnvironmentVariables:
    """Test suite for get_environment_variables()."""

    @patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "ANTHROPIC_API_KEY": "test-anthropic-key",
        "SERVER_HOST": "localhost",
        "REDIS_URL": "redis://localhost:6379"
    }, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_get_env_vars_configured(self, mock_getenv):
        """Test retrieval of configured environment variables."""
        mock_getenv.side_effect = lambda key: os.environ.get(key)

        result = get_environment_variables()

        assert "OPENAI_API_KEY" in result
        assert result["OPENAI_API_KEY"]["value"] == "test-key"
        assert result["OPENAI_API_KEY"]["masked"] is True
        assert result["OPENAI_API_KEY"]["value"][:4] == "test"
        assert result["OPENAI_API_KEY"]["value"][4:] == "*" * 4

        assert "ANTHROPIC_API_KEY" in result
        assert result["ANTHROPIC_API_KEY"]["value"] == "test-anthropic-key"
        assert result["ANTHROPIC_API_KEY"]["masked"] is True
        assert result["ANTHROPIC_API_KEY"]["value"][:4] == "test"
        assert result["ANTHROPIC_API_KEY"]["value"][4:] == "*" * 4

        assert "SERVER_HOST" in result
        assert result["SERVER_HOST"]["value"] == "localhost"
        assert result["SERVER_HOST"]["masked"] is False

        assert "REDIS_URL" in result
        assert result["REDIS_URL"]["value"] == "redis://localhost:6379"
        assert result["REDIS_URL"]["masked"] is False

    @patch.dict(os.environ, {}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_get_env_vars_missing(self, mock_getenv):
        """Test handling of missing environment variables."""
        mock_getenv.return_value = None

        result = get_environment_variables()

        assert "OPENAI_API_KEY" in result
        assert result["OPENAI_API_KEY"]["value"] is None
        assert result["OPENAI_API_KEY"]["masked"] is False

        assert "REDIS_URL" in result
        assert result["REDIS_URL"]["value"] is None
        assert result["REDIS_URL"]["masked"] is False

    @patch.dict(os.environ, {"SECRET_KEY": "secret123"}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_sensitive_key_masking(self, mock_getenv):
        """Test that sensitive keys are properly masked."""
        mock_getenv.return_value = "secret123"

        result = get_environment_variables()

        assert "SECRET_KEY" in result
        assert result["SECRET_KEY"]["value"] == "secr***"
        assert result["SECRET_KEY"]["masked"] is True

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk"}, clear=True)
    @patch('coderabbit_ai.dashboard.os.getenv')
    def test_short_sensitive_value(self, mock_getenv):
        """Test that short values (< 5 chars) are not masked."""
        mock_getenv.return_value = "sk"

        result = get_environment_variables()

        assert "OPENAI_API_KEY" in result
        assert result["OPENAI_API_KEY"]["value"] == "sk"
        assert result["OPENAI_API_KEY"]["masked"] is False


class TestRecentTestResults:
    """Test suite for get_recent_test_results()."""

    @patch('coderabbit_ai.dashboard.Path')
    def test_get_test_results_available(self, mock_path):
        """Test retrieval of available test results."""
        mock_cache_dir = Mock()
        mock_cache_dir.exists.return_value = True
        mock_cache_dir.__truediv__ = ".pytest_cache"
        mock_path.return_value = mock_cache_dir

        mock_lastfailed_file = Mock()
        mock_lastfailed_file.exists.return_value = True
        mock_lastfailed_file.__str__ = mock_cache_dir / "v" / "cache" / "lastfailed"

        with open(mock_lastfailed_file.__str__, 'w') as f:
            import json
            json.dump({
                "test_file_1.py": ["error"],
                "test_file_2.py": ["error"],
                "test_file_3.py": ["error"]
            }, f)

        result = get_recent_test_results()

        assert result["available"] is True
        assert result["last_failed_count"] == 3
        assert "test_file_1.py" in result["last_failed"]
        assert "test_file_2.py" in result["last_failed"]
        assert "test_file_3.py" in result["last_failed"]

    @patch('coderabbit_ai.dashboard.Path')
    def test_get_test_results_not_available(self, mock_path):
        """Test handling when test results not available."""
        mock_cache_dir = Mock()
        mock_cache_dir.exists.return_value = False
        mock_path.return_value = mock_cache_dir

        result = get_recent_test_results()

        assert result["available"] is False
        assert "last_failed_count" not in result
        assert "last_failed" not in result

    @patch('coderabbit_ai.dashboard.Path')
    def test_get_test_results_json_error(self, mock_path):
        """Test handling of JSON parsing error."""
        mock_cache_dir = Mock()
        mock_cache_dir.exists.return_value = True
        mock_cache_dir.__truediv__ = ".pytest_cache"
        mock_path.return_value = mock_cache_dir

        mock_lastfailed_file = Mock()
        mock_lastfailed_file.exists.return_value = True

        with open(mock_lastfailed_file.__str__, 'w') as f:
            f.write("invalid json content")

        result = get_recent_test_results()

        assert result["available"] is False
        assert "error" in result


class TestDashboardRoutes:
    """Test suite for dashboard API routes."""

    def test_dashboard_home_route(self, client):
        """Test dashboard home route."""
        response = client.get("/")

        assert response.status_code == 200
        assert isinstance(response, HTMLResponse)
        assert "CodeRabbit AI System Dashboard" in response.body.decode()

    @patch('coderabbit_ai.dashboard.get_system_metrics')
    def test_api_metrics_route_success(self, mock_metrics, client):
        """Test metrics API route."""
        mock_metrics.return_value = {
            "cpu": {"usage_percent": 50.0, "count": 4},
            "memory": {"total_gb": 16.0, "used_gb": 8.0, "percent": 50.0},
            "disk": {"total_gb": 500.0, "used_gb": 250.0, "percent": 50.0}
        }

        response = client.get("/dashboard/api/metrics")

        assert response.status_code == 200
        data = response.json()
        assert data == mock_metrics.return_value

    @patch('coderabbit_ai.dashboard.get_component_status')
    def test_api_components_route_success(self, mock_components, client):
        """Test components API route."""
        mock_components.return_value = {
            "dspy": {"status": "ok", "version": "2.5.0"},
            "openai": {"status": "ok", "configured": True, "message": "API key configured"},
            "anthropic": {"status": "warning", "configured": False, "message": "API key not set"}
            "ast-grep": {"status": "ok", "version": "0.233.0"},
            "ast-grep-rules": {"status": "ok", "exists": True, "path": "/tmp/ast-grep-rules"}
        }

        response = client.get("/dashboard/api/components")

        assert response.status_code == 200
        data = response.json()
        assert data == mock_components.return_value

    @patch('coderabbit_ai.dashboard.get_environment_variables')
    def test_api_env_vars_route_success(self, mock_env_vars, client):
        """Test environment variables API route."""
        mock_env_vars.return_value = {
            "OPENAI_API_KEY": {"value": "sk-test****", "masked": True},
            "SERVER_HOST": {"value": "localhost", "masked": False},
            "REDIS_URL": {"value": "redis://localhost:6379", "masked": False}
        }

        response = client.get("/dashboard/api/env-vars")

        assert response.status_code == 200
        data = response.json()
        assert data == mock_env_vars.return_value

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_success_all(self, mock_run, client):
        """Test running all tests via API."""
        mock_result = Mock(
            stdout="All tests passed!",
            returncode=0
        )
        mock_run.return_value = mock_result

        response = client.post("/dashboard/api/run-tests/all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["return_code"] == 0
        assert "All tests passed!" in data["output"]

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_phase1(self, mock_run, client):
        """Test running phase 1 tests via API."""
        mock_result = Mock(
            stdout="Phase 1: 5 passed, 1 failed",
            returncode=1
        )
        mock_run.return_value = mock_result

        response = client.post("/dashboard/api/run-tests/phase1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["return_code"] == 1
        assert "Phase 1: 5 passed, 1 failed" in data["output"]

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_security(self, mock_run, client):
        """Test running security tests via API."""
        mock_result = Mock(
            stdout="Security tests: 10 passed",
            returncode=0
        )
        mock_run.return_value = mock_result

        response = client.post("/dashboard/api/run-tests/security")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_timeout(self, mock_run, client):
        """Test test execution timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pytest", timeout=300)

        response = client.post("/dashboard/api/run-tests/all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "timed out" in data["output"].lower()

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_unknown_suite(self, mock_run, client):
        """Test unknown test suite."""
        mock_run.return_value = Mock(returncode=0, stdout="Tests passed")

        response = client.post("/dashboard/api/run-tests/unknown")

        assert response.status_code == 400
        data = response.json()
        assert "Unknown test suite" in data["detail"]

    @patch('coderabbit_ai.dashboard.subprocess.run')
    def test_api_run_tests_subprocess_failure(self, mock_run, client):
        """Test subprocess failure during test execution."""
        import subprocess
        mock_run.side_effect = subprocess.SubprocessError("Failed to execute pytest")

        response = client.post("/dashboard/api/run-tests/all")

        assert response.status_code == 500
        data = response.json()
        assert "Failed to execute pytest" in data["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
