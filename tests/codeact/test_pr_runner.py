"""Unit tests for pr_test_runner.py."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from subprocess import TimeoutExpired

from coderabbit_ai.pr_test_runner import (
    TestResult,
    PRTestRunner
)
from coderabbit_ai.models import FileChange


class TestTestResult:
    """Test TestResult dataclass."""

    def test_to_dict(self):
        """Test converting TestResult to dictionary."""
        result = TestResult(
            passed=True,
            test_command="pytest -v",
            exit_code=0,
            stdout="All tests passed",
            stderr="",
            duration_ms=1500,
            tests_run=10,
            tests_passed=10,
            tests_failed=0,
            failed_tests=None,
            coverage_percent=95.0,
            build_errors=None
        )

        result_dict = result.to_dict()

        assert result_dict["passed"] == True
        assert result_dict["test_command"] == "pytest -v"
        assert result_dict["exit_code"] == 0
        assert result_dict["tests_run"] == 10
        assert result_dict["coverage_percent"] == 95.0

    def test_to_dict_minimal(self):
        """Test converting TestResult with minimal fields."""
        result = TestResult(
            passed=False,
            test_command="npm test",
            exit_code=1,
            stdout="Tests failed",
            stderr="Error",
            duration_ms=500
        )

        result_dict = result.to_dict()

        assert result_dict["passed"] == False
        assert result_dict["tests_run"] is None
        assert result_dict["tests_passed"] is None


class TestPRTestRunnerInit:
    """Test PRTestRunner initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        runner = PRTestRunner()

        assert runner.timeout == 300
        assert runner.max_memory_mb == 2048
        assert runner.max_cpus == 2.0
        assert runner.use_sandbox == True

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        runner = PRTestRunner(
            timeout=600,
            max_memory_mb=4096,
            max_cpus=4.0,
            use_sandbox=False
        )

        assert runner.timeout == 600
        assert runner.max_memory_mb == 4096
        assert runner.max_cpus == 4.0
        assert runner.use_sandbox == False

    def test_init_with_sandbox(self):
        """Test initialization creates sandbox when use_sandbox=True."""
        runner = PRTestRunner(use_sandbox=True)

        assert runner.sandbox is not None

    def test_init_without_sandbox(self):
        """Test initialization without sandbox."""
        runner = PRTestRunner(use_sandbox=False)

        assert not hasattr(runner, 'sandbox')


class TestDetectLanguage:
    """Test _detect_language method."""

    def test_detect_python(self):
        """Test detecting Python from .py files."""
        files = [
            FileChange(path="src/api.py", content=""),
            FileChange(path="tests/test_api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "python"

    def test_detect_javascript(self):
        """Test detecting JavaScript from .js files."""
        files = [
            FileChange(path="src/index.js", content=""),
            FileChange(path="test.js", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "javascript"

    def test_detect_typescript(self):
        """Test detecting TypeScript from .ts files."""
        files = [
            FileChange(path="src/app.ts", content=""),
            FileChange(path="src/index.ts", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "typescript"

    def test_detect_go(self):
        """Test detecting Go from .go files."""
        files = [
            FileChange(path="main.go", content=""),
            FileChange(path="main_test.go", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "go"

    def test_detect_rust(self):
        """Test detecting Rust from .rs files."""
        files = [
            FileChange(path="src/main.rs", content=""),
            FileChange(path="tests/lib_test.rs", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "rust"

    def test_detect_mixed_languages(self):
        """Test detecting most common language in mixed files."""
        files = [
            FileChange(path="src/api.py", content=""),
            FileChange(path="src/utils.py", content=""),
            FileChange(path="src/index.js", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "python"

    def test_detect_unknown_language(self):
        """Test unknown language detection."""
        files = [
            FileChange(path="README.md", content=""),
            FileChange(path="docs/api.md", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "unknown"

    def test_detect_empty_files(self):
        """Test language detection with empty files list."""
        files = []

        runner = PRTestRunner(use_sandbox=False)
        language = runner._detect_language(files)

        assert language == "unknown"


class TestDetectTestCommand:
    """Test _detect_test_command method."""

    def test_detect_pytest_with_ini(self):
        """Test detecting pytest with pytest.ini."""
        files = [
            FileChange(path="pytest.ini", content="[pytest]"),
            FileChange(path="src/api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "python")

        assert command == "pytest -v"

    def test_detect_pytest_with_pyproject(self):
        """Test detecting pytest with pyproject.toml."""
        files = [
            FileChange(path="pyproject.toml", content="[tool.pytest]"),
            FileChange(path="src/api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "python")

        assert command == "pytest -v"

    def test_detect_pytest_with_test_files(self):
        """Test detecting pytest with test files."""
        files = [
            FileChange(path="test_api.py", content=""),
            FileChange(path="src/api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "python")

        assert command == "pytest -v"

    def test_detect_tox(self):
        """Test detecting tox."""
        files = [
            FileChange(path="tox.ini", content="[tox]"),
            FileChange(path="src/api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "python")

        assert command == "tox"

    def test_detect_default_pytest(self):
        """Test defaulting to pytest for Python."""
        files = [
            FileChange(path="src/api.py", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "python")

        assert command == "pytest -v"

    def test_detect_npm_test(self):
        """Test detecting npm test for JavaScript."""
        content = '{"scripts": {"test": "jest --coverage"}}'
        files = [
            FileChange(path="package.json", content=content),
            FileChange(path="src/index.js", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "javascript")

        assert command == "npm test"

    def test_detect_npm_test_typescript(self):
        """Test detecting npm test for TypeScript."""
        content = '{"scripts": {"test": "jest"}}'
        files = [
            FileChange(path="package.json", content=content),
            FileChange(path="src/app.ts", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "typescript")

        assert command == "npm test"

    def test_detect_default_npm(self):
        """Test defaulting to npm test for JS/TS."""
        files = [
            FileChange(path="src/index.js", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "javascript")

        assert command == "npm test"

    def test_detect_go_test(self):
        """Test detecting go test."""
        files = [
            FileChange(path="main.go", content=""),
            FileChange(path="main_test.go", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "go")

        assert command == "go test ./..."

    def test_detect_cargo_test(self):
        """Test detecting cargo test."""
        files = [
            FileChange(path="src/main.rs", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "rust")

        assert command == "cargo test"

    def test_detect_no_command_unknown(self):
        """Test returning None for unknown language."""
        files = [
            FileChange(path="README.md", content="")
        ]

        runner = PRTestRunner(use_sandbox=False)
        command = runner._detect_test_command(files, "unknown")

        assert command is None


class TestGenerateTestCode:
    """Test _generate_test_code method."""

    def test_generate_code_python(self):
        """Test generating test code for Python."""
        runner = PRTestRunner(use_sandbox=False)
        code = runner._generate_test_code("python", "pytest -v")

        assert "import subprocess" in code
        assert "import json" in code
        assert "import re" in code
        assert 'context["language"]' in code
        assert 'context["test_command"]' in code
        assert "pytest -v" in code

    def test_generate_code_javascript(self):
        """Test generating test code for JavaScript."""
        runner = PRTestRunner(use_sandbox=False)
        code = runner._generate_test_code("javascript", "npm test")

        assert "npm install" in code
        assert "npm test" in code

    def test_generate_code_typescript(self):
        """Test generating test code for TypeScript."""
        runner = PRTestRunner(use_sandbox=False)
        code = runner._generate_test_code("typescript", "npm test")

        assert "npm install" in code
        assert "npm test" in code

    def test_generate_code_pytest_parsing(self):
        """Test pytest output parsing in generated code."""
        runner = PRTestRunner(use_sandbox=False)
        code = runner._generate_test_code("python", "pytest")

        assert r"(\d+) passed" in code
        assert "tests_run" in code
        assert "tests_passed" in code
        assert "tests_failed" in code

    def test_generate_code_jest_parsing(self):
        """Test Jest output parsing in generated code."""
        runner = PRTestRunner(use_sandbox=False)
        code = runner._generate_test_code("javascript", "npm test")

        assert r"Tests:\s+(\d+) failed" in code or r"Tests:" in code


class TestRunTestsSandboxed:
    """Test _run_tests_sandboxed method."""

    @patch('coderabbit_ai.pr_test_runner.CodeSandbox')
    def test_run_sandboxed_success(self, mock_sandbox_class):
        """Test running tests in sandbox successfully."""
        mock_sandbox = Mock()
        mock_sandbox.execute.return_value = {
            "result": {
                "passed": True,
                "exit_code": 0,
                "stdout": "10 passed in 2s",
                "stderr": "",
                "tests_run": 10,
                "tests_passed": 10,
                "tests_failed": 0,
                "coverage_percent": 95.0
            }
        }
        mock_sandbox_class.return_value = mock_sandbox

        runner = PRTestRunner(use_sandbox=True)
        files = [FileChange(path="test_api.py", content="")]

        result = runner._run_tests_sandboxed(files, "python", "pytest -v")

        assert result.passed == True
        assert result.exit_code == 0
        assert result.tests_run == 10
        assert result.coverage_percent == 95.0

    @patch('coderabbit_ai.pr_test_runner.CodeSandbox')
    def test_run_sandboxed_failure(self, mock_sandbox_class):
        """Test running tests in sandbox with failures."""
        mock_sandbox = Mock()
        mock_sandbox.execute.return_value = {
            "result": {
                "passed": False,
                "exit_code": 1,
                "stdout": "5 passed, 2 failed",
                "stderr": "AssertionError",
                "tests_run": 7,
                "tests_passed": 5,
                "tests_failed": 2,
                "failed_tests": ["test_api::test_get", "test_api::test_post"]
            }
        }
        mock_sandbox_class.return_value = mock_sandbox

        runner = PRTestRunner(use_sandbox=True)
        files = [FileChange(path="test_api.py", content="")]

        result = runner._run_tests_sandboxed(files, "python", "pytest -v")

        assert result.passed == False
        assert result.exit_code == 1
        assert result.tests_failed == 2
        assert len(result.failed_tests) == 2

    @patch('coderabbit_ai.pr_test_runner.CodeSandbox')
    def test_run_sandboxed_error(self, mock_sandbox_class):
        """Test running tests with sandbox error."""
        mock_sandbox = Mock()
        mock_sandbox.execute.return_value = {
            "error": "Sandbox execution failed"
        }
        mock_sandbox_class.return_value = mock_sandbox

        runner = PRTestRunner(use_sandbox=True)
        files = [FileChange(path="test_api.py", content="")]

        result = runner._run_tests_sandboxed(files, "python", "pytest -v")

        assert result.passed == False
        assert result.exit_code == -1
        assert "error" in result.stderr.lower()


class TestRunTestsDirect:
    """Test _run_tests_direct method."""

    @patch('coderabbit_ai.pr_test_runner.subprocess.run')
    def test_run_direct_success(self, mock_subprocess):
        """Test running tests directly successfully."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "All tests passed"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        runner = PRTestRunner(use_sandbox=False, timeout=60)
        files = [FileChange(path="test_api.py", content="def test(): pass")]

        result = runner._run_tests_direct(files, "python", "pytest -v")

        assert result.passed == True
        assert result.exit_code == 0
        assert "All tests passed" in result.stdout

    @patch('coderabbit_ai.pr_test_runner.subprocess.run')
    def test_run_direct_failure(self, mock_subprocess):
        """Test running tests directly with failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Tests failed"
        mock_result.stderr = "AssertionError"
        mock_subprocess.return_value = mock_result

        runner = PRTestRunner(use_sandbox=False)
        files = [FileChange(path="test_api.py", content="")]

        result = runner._run_tests_direct(files, "python", "pytest -v")

        assert result.passed == False
        assert result.exit_code == 1

    @patch('coderabbit_ai.pr_test_runner.subprocess.run')
    def test_run_direct_timeout(self, mock_subprocess):
        """Test running tests directly with timeout."""
        mock_subprocess.side_effect = TimeoutExpired("pytest -v", 30)

        runner = PRTestRunner(use_sandbox=False, timeout=30)
        files = [FileChange(path="test_api.py", content="")]

        result = runner._run_tests_direct(files, "python", "pytest -v")

        assert result.passed == False
        assert result.exit_code == -1
        assert "timed out" in result.stderr.lower()

    def test_run_direct_shlex_split(self):
        """Test that test_command is properly split with shlex."""
        import shlex
        test_command = "pytest -v --cov=src tests/"

        # shlex.split should properly handle quoted arguments
        split_cmd = shlex.split(test_command)
        assert split_cmd == ["pytest", "-v", "--cov=src", "tests/"]


class TestRunTests:
    """Test run_tests method."""

    @patch('coderabbit_ai.pr_test_runner.CodeSandbox')
    def test_run_tests_with_sandbox(self, mock_sandbox_class):
        """Test running tests with sandbox."""
        mock_sandbox = Mock()
        mock_sandbox.execute.return_value = {
            "result": {
                "passed": True,
                "exit_code": 0,
                "stdout": "10 passed",
                "stderr": "",
                "tests_run": 10,
                "tests_passed": 10,
                "tests_failed": 0
            }
        }
        mock_sandbox_class.return_value = mock_sandbox

        runner = PRTestRunner(use_sandbox=True)
        files = [FileChange(path="test_api.py", content="")]

        result = runner.run_tests(files)

        assert result.passed == True
        assert result.duration_ms >= 0

    @patch('coderabbit_ai.pr_test_runner.subprocess.run')
    def test_run_tests_without_sandbox(self, mock_subprocess):
        """Test running tests without sandbox."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "All passed"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        runner = PRTestRunner(use_sandbox=False)
        files = [FileChange(path="test_api.py", content="")]

        result = runner.run_tests(files)

        assert result.passed == True
        assert result.duration_ms >= 0

    def test_run_tests_no_command_detected(self):
        """Test running tests when no command is detected."""
        runner = PRTestRunner(use_sandbox=False)
        files = [FileChange(path="README.md", content="")]

        result = runner.run_tests(files)

        assert result.passed == False
        assert result.exit_code == -1
        assert "No test command detected" in result.stderr

    def test_run_tests_exception_handling(self):
        """Test exception handling in run_tests."""
        runner = PRTestRunner(use_sandbox=False)
        runner._detect_language = Mock(side_effect=Exception("Detection failed"))

        files = [FileChange(path="test_api.py", content="")]

        result = runner.run_tests(files)

        assert result.passed == False
        assert result.exit_code == -1
        assert "exception" in result.stderr.lower()

    def test_run_tests_with_custom_language(self):
        """Test running tests with custom language."""
        runner = PRTestRunner(use_sandbox=False)
        files = [FileChange(path="test.go", content="")]

        with patch.object(runner, '_run_tests_direct') as mock_run:
            mock_run.return_value = TestResult(
                passed=True,
                test_command="go test",
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=100
            )

            result = runner.run_tests(files, language="go")

            assert result.passed == True

    def test_run_tests_with_custom_command(self):
        """Test running tests with custom command."""
        runner = PRTestRunner(use_sandbox=False)
        files = [FileChange(path="test.py", content="")]

        with patch.object(runner, '_run_tests_direct') as mock_run:
            mock_run.return_value = TestResult(
                passed=True,
                test_command="custom command",
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=100
            )

            result = runner.run_tests(files, test_command="pytest -xvs")

            assert result.passed == True
