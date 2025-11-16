"""PR Test Runner - Execute PR code and tests in isolated sandbox."""

import logging
import json
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, asdict

from .models import FileChange
from .codeact import CodeSandbox
from . import config

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of running PR tests."""
    passed: bool
    test_command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    tests_run: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    failed_tests: Optional[List[str]] = None
    coverage_percent: Optional[float] = None
    build_errors: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PRTestRunner:
    """
    Execute PR tests in isolated Docker sandbox.

    Features:
    - Multi-language support (Python, JavaScript, Go, etc.)
    - Auto-detects test framework
    - Runs in isolated sandbox
    - Captures test results and coverage
    - Resource limits enforced
    """

    # Test framework detection patterns
    TEST_PATTERNS = {
        "python": {
            "pytest": ["pytest.ini", "pyproject.toml", "test_*.py", "*_test.py"],
            "unittest": ["test_*.py", "tests/"],
            "tox": ["tox.ini"],
        },
        "javascript": {
            "jest": ["jest.config.js", "package.json"],
            "mocha": ["mocha.opts", ".mocharc.json"],
            "npm": ["package.json"],
        },
        "typescript": {
            "jest": ["jest.config.ts", "package.json"],
            "npm": ["package.json"],
        },
        "go": {
            "go_test": ["*_test.go", "go.mod"],
        },
        "rust": {
            "cargo": ["Cargo.toml"],
        },
    }

    def __init__(
        self,
        timeout: int = None,
        max_memory_mb: int = None,
        max_cpus: float = None,
        use_sandbox: bool = True,
    ):
        """
        Initialize PR Test Runner.

        Args:
            timeout: Max execution time in seconds
            max_memory_mb: Max memory usage in MB
            max_cpus: Max CPU cores
            use_sandbox: Whether to use Docker sandbox (recommended)
        """
        self.use_sandbox = use_sandbox
        self.timeout = timeout or config.get_env_int("PR_TEST_TIMEOUT", 300)
        self.max_memory_mb = max_memory_mb or config.get_env_int("PR_TEST_MAX_MEMORY_MB", 2048)
        self.max_cpus = max_cpus or config.get_env_float("PR_TEST_MAX_CPUS", 2.0)

        if use_sandbox:
            self.sandbox = CodeSandbox(
                timeout=self.timeout,
                max_memory_mb=self.max_memory_mb,
                max_cpus=self.max_cpus,
            )

    def run_tests(
        self,
        pr_files: List[FileChange],
        language: str = None,
        test_command: Optional[str] = None,
    ) -> TestResult:
        """
        Run PR tests.

        Args:
            pr_files: List of changed files in the PR
            language: Programming language (auto-detected if not provided)
            test_command: Custom test command (auto-detected if not provided)

        Returns:
            TestResult with test execution details
        """
        import time
        start_time = time.time()

        try:
            # Auto-detect language if not provided
            if not language:
                language = self._detect_language(pr_files)
                logger.info(f"Detected language: {language}")

            # Auto-detect test command if not provided
            if not test_command:
                test_command = self._detect_test_command(pr_files, language)
                if not test_command:
                    return TestResult(
                        passed=False,
                        test_command="",
                        exit_code=-1,
                        stdout="",
                        stderr="No test command detected. Please specify test_command.",
                        duration_ms=0,
                    )
                logger.info(f"Detected test command: {test_command}")

            # Prepare test execution code
            if self.use_sandbox:
                result = self._run_tests_sandboxed(pr_files, language, test_command)
            else:
                result = self._run_tests_direct(pr_files, language, test_command)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            result.duration_ms = duration_ms

            return result

        except Exception as e:
            logger.error(f"Test execution failed: {e}", exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            return TestResult(
                passed=False,
                test_command=test_command or "",
                exit_code=-1,
                stdout="",
                stderr=f"Test runner exception: {str(e)}",
                duration_ms=duration_ms,
            )

    def _run_tests_sandboxed(
        self,
        pr_files: List[FileChange],
        language: str,
        test_command: str,
    ) -> TestResult:
        """Run tests in Docker sandbox."""
        logger.info(f"Running tests in sandbox: {test_command}")

        # Generate test execution code
        code = self._generate_test_code(language, test_command)

        # Prepare file context
        context = {
            "files": [
                {
                    "path": f.path,
                    "content": f.content if hasattr(f, 'content') else "",
                    "diff": f.diff if hasattr(f, 'diff') else "",
                }
                for f in pr_files
            ],
            "language": language,
            "test_command": test_command,
        }

        # Execute in sandbox
        sandbox_result = self.sandbox.execute(
            code=code,
            context=context,
            allowed_imports=["subprocess", "json", "os", "pathlib", "time", "re"]
        )

        # Parse sandbox result
        if "error" in sandbox_result:
            return TestResult(
                passed=False,
                test_command=test_command,
                exit_code=-1,
                stdout="",
                stderr=sandbox_result["error"],
                duration_ms=0,
            )

        # Extract test result from sandbox response
        test_data = sandbox_result.get("result", {})

        return TestResult(
            passed=test_data.get("passed", False),
            test_command=test_command,
            exit_code=test_data.get("exit_code", -1),
            stdout=test_data.get("stdout", ""),
            stderr=test_data.get("stderr", ""),
            duration_ms=0,  # Will be set by caller
            tests_run=test_data.get("tests_run"),
            tests_passed=test_data.get("tests_passed"),
            tests_failed=test_data.get("tests_failed"),
            failed_tests=test_data.get("failed_tests"),
            coverage_percent=test_data.get("coverage_percent"),
        )

    def _run_tests_direct(
        self,
        pr_files: List[FileChange],
        language: str,
        test_command: str,
    ) -> TestResult:
        """Run tests directly without sandbox (NOT RECOMMENDED for untrusted code)."""
        import subprocess
        import tempfile

        logger.warning("Running tests WITHOUT sandbox - only use for trusted code!")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write files
            tmpdir_path = Path(tmpdir)
            for file_data in pr_files:
                file_path = tmpdir_path / file_data.path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                if hasattr(file_data, 'content') and file_data.content:
                    file_path.write_text(file_data.content)

            # Run test command
            try:
                result = subprocess.run(
                    test_command.split(),
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                return TestResult(
                    passed=result.returncode == 0,
                    test_command=test_command,
                    exit_code=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    duration_ms=0,
                )

            except subprocess.TimeoutExpired:
                return TestResult(
                    passed=False,
                    test_command=test_command,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Test execution timed out after {self.timeout}s",
                    duration_ms=0,
                )

    def _generate_test_code(self, language: str, test_command: str) -> str:
        """Generate Python code to run tests in sandbox."""
        return f'''
import subprocess
import json
import os
import re
from pathlib import Path

# Create file structure from context
for file_data in context["files"]:
    file_path = Path(file_data["path"])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_data.get("content"):
        file_path.write_text(file_data["content"])

# Install dependencies based on language
language = context["language"]
if language == "python":
    # Check for requirements.txt
    if Path("requirements.txt").exists():
        try:
            subprocess.run(
                ["pip", "install", "-q", "-r", "requirements.txt"],
                timeout=120,
                check=False
            )
        except Exception as e:
            print(f"Warning: Failed to install requirements: {{e}}")

    # Check for setup.py
    if Path("setup.py").exists():
        try:
            subprocess.run(
                ["pip", "install", "-q", "-e", "."],
                timeout=120,
                check=False
            )
        except Exception as e:
            print(f"Warning: Failed to install package: {{e}}")

elif language in ["javascript", "typescript"]:
    if Path("package.json").exists():
        try:
            subprocess.run(
                ["npm", "install", "--silent"],
                timeout=180,
                check=False
            )
        except Exception as e:
            print(f"Warning: Failed to npm install: {{e}}")

# Run test command
test_command = context["test_command"]
test_result = subprocess.run(
    test_command.split(),
    capture_output=True,
    text=True,
    timeout=240
)

# Parse test output for metrics (basic parsing)
stdout = test_result.stdout
stderr = test_result.stderr

# Try to extract test counts from pytest output
tests_run = None
tests_passed = None
tests_failed = None
failed_tests = []
coverage_percent = None

# Pytest pattern: "5 passed, 2 failed in 1.23s"
pytest_match = re.search(r'(\\d+) passed(?:, (\\d+) failed)?', stdout)
if pytest_match:
    tests_passed = int(pytest_match.group(1))
    tests_failed = int(pytest_match.group(2)) if pytest_match.group(2) else 0
    tests_run = tests_passed + tests_failed

# Jest pattern: "Tests: 3 failed, 10 passed, 13 total"
jest_match = re.search(r'Tests:\\s+(\\d+) failed,\\s+(\\d+) passed,\\s+(\\d+) total', stdout)
if jest_match:
    tests_failed = int(jest_match.group(1))
    tests_passed = int(jest_match.group(2))
    tests_run = int(jest_match.group(3))

# Coverage pattern: "TOTAL  ...  95%"
coverage_match = re.search(r'TOTAL.*?(\\d+)%', stdout)
if coverage_match:
    coverage_percent = float(coverage_match.group(1))

# Extract failed test names (pytest)
failed_pattern = r'FAILED (\\S+)::(\\S+)'
failed_matches = re.findall(failed_pattern, stdout)
if failed_matches:
    failed_tests = [f"{{module}}::{{test}}" for module, test in failed_matches]

result = {{
    "passed": test_result.returncode == 0,
    "exit_code": test_result.returncode,
    "stdout": stdout[:5000],  # Truncate long output
    "stderr": stderr[:5000],
    "tests_run": tests_run,
    "tests_passed": tests_passed,
    "tests_failed": tests_failed,
    "failed_tests": failed_tests if failed_tests else None,
    "coverage_percent": coverage_percent,
}}
'''

    def _detect_language(self, pr_files: List[FileChange]) -> str:
        """Detect programming language from PR files."""
        extensions = {}
        for f in pr_files:
            ext = Path(f.path).suffix.lower()
            extensions[ext] = extensions.get(ext, 0) + 1

        # Language mapping
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "javascript",
            ".tsx": "typescript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
        }

        # Find most common language
        for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
            if ext in lang_map:
                return lang_map[ext]

        return "unknown"

    def _detect_test_command(self, pr_files: List[FileChange], language: str) -> Optional[str]:
        """Auto-detect test command based on project files."""
        file_names = {f.path for f in pr_files}
        file_basenames = {Path(f.path).name for f in pr_files}

        if language == "python":
            # Check for pytest
            if any(p in file_basenames for p in ["pytest.ini", "pyproject.toml"]):
                return "pytest -v"
            if any(f.path.startswith("test_") or f.path.endswith("_test.py") for f in pr_files):
                return "pytest -v"
            # Check for tox
            if "tox.ini" in file_basenames:
                return "tox"
            # Default to pytest
            return "pytest -v"

        elif language in ["javascript", "typescript"]:
            # Check package.json for test script
            for f in pr_files:
                if f.path.endswith("package.json") and hasattr(f, 'content'):
                    try:
                        pkg = json.loads(f.content)
                        if "scripts" in pkg and "test" in pkg["scripts"]:
                            return "npm test"
                    except:
                        pass
            return "npm test"

        elif language == "go":
            return "go test ./..."

        elif language == "rust":
            return "cargo test"

        return None
