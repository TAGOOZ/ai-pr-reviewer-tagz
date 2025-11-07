"""Tests for StaticAnalysisAggregator."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from coderabbit_ai.analyzers.static_analysis_aggregator import StaticAnalysisAggregator
from coderabbit_ai.models import SecurityFinding, SecuritySummary


@pytest.fixture
def temp_project_dir():
    """Create temporary project directory."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_python_files(temp_project_dir):
    """Create sample Python files."""
    # File with issues
    file1 = temp_project_dir / "app.py"
    file1.write_text('''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id={user_id}"
    cursor.execute(query)
    return cursor.fetchone()

def unused_function():
    x = 1  # Unused variable
''')

    # Clean file
    file2 = temp_project_dir / "utils.py"
    file2.write_text('''
def clean_function():
    return "hello"
''')

    return ["app.py", "utils.py"]


class TestStaticAnalysisAggregator:
    """Test suite for StaticAnalysisAggregator."""

    def test_initialization_default(self):
        """Test default initialization."""
        aggregator = StaticAnalysisAggregator()
        assert aggregator.enable_linters is True
        # astgrep enabled status depends on config

    def test_initialization_custom(self):
        """Test initialization with custom settings."""
        aggregator = StaticAnalysisAggregator(
            enable_astgrep=False,
            enable_linters=False
        )
        assert aggregator.enable_astgrep is False
        assert aggregator.enable_linters is False
        assert aggregator.astgrep_scanner is None

    @patch('coderabbit_ai.analyzers.static_analysis_aggregator.AstGrepScanner')
    def test_initialization_with_astgrep(self, mock_astgrep_class):
        """Test initialization with ast-grep enabled."""
        mock_scanner = Mock()
        mock_astgrep_class.return_value = mock_scanner

        aggregator = StaticAnalysisAggregator(enable_astgrep=True)

        assert aggregator.astgrep_scanner == mock_scanner
        mock_astgrep_class.assert_called_once()

    @patch.object(StaticAnalysisAggregator, '_run_linters')
    @patch.object(StaticAnalysisAggregator, '_run_astgrep')
    def test_analyze_with_all_tools(self, mock_astgrep, mock_linters, temp_project_dir):
        """Test analyze() with all tools enabled."""
        # Mock linter results
        mock_linters.return_value = [
            {
                "tool": "flake8",
                "issues": [
                    {"file": "app.py", "line": 8, "severity": "warning", "message": "Unused variable"}
                ]
            }
        ]

        # Mock ast-grep results
        mock_astgrep.return_value = {
            "tool": "ast-grep",
            "findings": [
                {
                    "tool": "ast-grep",
                    "rule_id": "python/security/sql-injection",
                    "severity": "critical",
                    "category": "security",
                    "file": "app.py",
                    "line": 3,
                    "message": "SQL injection vulnerability",
                    "confidence": 0.95
                }
            ],
            "stats": {"scan_time_ms": 150}
        }

        aggregator = StaticAnalysisAggregator(
            enable_astgrep=True,
            enable_linters=True
        )
        aggregator.astgrep_scanner = Mock()  # Mock scanner

        result = aggregator.analyze(
            changed_files=["app.py", "utils.py"],
            project_root=str(temp_project_dir)
        )

        # Verify structure
        assert "linter_results" in result
        assert "security_findings" in result
        assert "security_summary" in result
        assert "stats" in result

        # Verify linter results
        assert len(result["linter_results"]) == 1
        assert result["linter_results"][0]["tool"] == "flake8"

        # Verify security findings
        assert len(result["security_findings"]) == 1
        assert result["security_findings"][0]["severity"] == "critical"

        # Verify stats
        assert result["stats"]["files_analyzed"] == 2
        assert "flake8" in result["stats"]["tools_run"]
        assert "ast-grep" in result["stats"]["tools_run"]

    @patch.object(StaticAnalysisAggregator, '_run_linters')
    @patch.object(StaticAnalysisAggregator, '_run_astgrep')
    def test_analyze_linters_only(self, mock_astgrep, mock_linters, temp_project_dir):
        """Test analyze() with only linters enabled."""
        mock_linters.return_value = [
            {"tool": "flake8", "issues": []}
        ]

        aggregator = StaticAnalysisAggregator(
            enable_astgrep=False,
            enable_linters=True
        )

        result = aggregator.analyze(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        # Linters called, ast-grep not called
        mock_linters.assert_called_once()
        mock_astgrep.assert_not_called()

        assert len(result["linter_results"]) == 1
        assert len(result["security_findings"]) == 0

    @patch.object(StaticAnalysisAggregator, '_run_linters')
    @patch.object(StaticAnalysisAggregator, '_run_astgrep')
    def test_analyze_astgrep_only(self, mock_astgrep, mock_linters, temp_project_dir):
        """Test analyze() with only ast-grep enabled."""
        mock_astgrep.return_value = {
            "findings": [],
            "stats": {"scan_time_ms": 0}
        }

        aggregator = StaticAnalysisAggregator(
            enable_astgrep=True,
            enable_linters=False
        )
        aggregator.astgrep_scanner = Mock()

        result = aggregator.analyze(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        # ast-grep called, linters not called
        mock_astgrep.assert_called_once()
        mock_linters.assert_not_called()

        assert len(result["linter_results"]) == 0

    @patch('subprocess.run')
    def test_run_flake8_success(self, mock_run, temp_project_dir):
        """Test successful flake8 execution."""
        # Mock flake8 JSON output
        flake8_output = {
            "app.py": [
                {
                    "line_number": 8,
                    "column_number": 5,
                    "code": "W0612",
                    "text": "Unused variable 'x'"
                }
            ]
        }

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(flake8_output),
            stderr=""
        )

        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        result = aggregator._run_flake8(["app.py"], str(temp_project_dir))

        assert result is not None
        assert result["tool"] == "flake8"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["severity"] == "warning"

    @patch('subprocess.run')
    def test_run_flake8_not_installed(self, mock_run, temp_project_dir):
        """Test flake8 when not installed."""
        mock_run.side_effect = FileNotFoundError()

        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        result = aggregator._run_flake8(["app.py"], str(temp_project_dir))

        assert result is None

    @patch('subprocess.run')
    def test_run_flake8_timeout(self, mock_run, temp_project_dir):
        """Test flake8 timeout handling."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["flake8"], timeout=30)

        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        result = aggregator._run_flake8(["app.py"], str(temp_project_dir))

        assert result is None

    @patch('subprocess.run')
    def test_run_eslint_success(self, mock_run, temp_project_dir):
        """Test successful ESLint execution."""
        # Mock ESLint JSON output
        eslint_output = [
            {
                "filePath": f"{temp_project_dir}/app.js",
                "messages": [
                    {
                        "line": 10,
                        "column": 5,
                        "severity": 2,
                        "message": "Unexpected console statement",
                        "ruleId": "no-console"
                    }
                ]
            }
        ]

        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps(eslint_output),
            stderr=""
        )

        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        result = aggregator._run_eslint(["app.js"], str(temp_project_dir))

        assert result is not None
        assert result["tool"] == "eslint"
        assert len(result["issues"]) == 1
        assert result["issues"][0]["file"] == "app.js"

    def test_run_astgrep_success(self, temp_project_dir):
        """Test successful ast-grep execution."""
        mock_scanner = Mock()
        mock_scanner.scan.return_value = {
            "findings": [
                {
                    "tool": "ast-grep",
                    "rule_id": "python/security/test",
                    "severity": "high",
                    "category": "security",
                    "file": "app.py",
                    "line": 5,
                    "message": "Security issue",
                    "confidence": 0.9
                }
            ],
            "stats": {"scan_time_ms": 100}
        }

        aggregator = StaticAnalysisAggregator(enable_astgrep=True)
        aggregator.astgrep_scanner = mock_scanner

        result = aggregator._run_astgrep(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        assert result is not None
        assert len(result["findings"]) == 1
        mock_scanner.scan.assert_called_once()

    def test_run_astgrep_scanner_not_available(self, temp_project_dir):
        """Test ast-grep when scanner not available."""
        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        aggregator.astgrep_scanner = None

        result = aggregator._run_astgrep(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        assert result is None

    def test_generate_security_summary_empty(self):
        """Test security summary generation with no findings."""
        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        summary = aggregator._generate_security_summary([])

        assert summary.total_findings == 0
        assert len(summary.by_severity) == 0
        assert len(summary.by_category) == 0
        assert len(summary.critical_files) == 0

    def test_generate_security_summary_with_findings(self):
        """Test security summary generation with findings."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/sql-injection",
                severity="critical",
                category="security",
                file="app.py",
                line=10,
                message="SQL injection"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/xss",
                severity="high",
                category="security",
                file="web.py",
                line=20,
                message="XSS vulnerability"
            ),
            SecurityFinding(
                tool="semgrep",
                rule_id="python/best-practice/logging",
                severity="low",
                category="best-practice",
                file="app.py",
                line=30,
                message="Missing logging"
            )
        ]

        aggregator = StaticAnalysisAggregator(enable_astgrep=False)
        summary = aggregator._generate_security_summary(findings)

        assert summary.total_findings == 3
        assert summary.by_severity["critical"] == 1
        assert summary.by_severity["high"] == 1
        assert summary.by_severity["low"] == 1
        assert summary.by_category["security"] == 2
        assert summary.by_category["best-practice"] == 1
        assert set(summary.critical_files) == {"app.py", "web.py"}
        assert set(summary.tools_used) == {"ast-grep", "semgrep"}

    def test_run_linters_python_files(self, temp_project_dir):
        """Test running linters on Python files."""
        with patch.object(StaticAnalysisAggregator, '_run_flake8') as mock_flake8:
            mock_flake8.return_value = {"tool": "flake8", "issues": []}

            aggregator = StaticAnalysisAggregator(enable_astgrep=False)
            results = aggregator._run_linters(
                ["app.py", "test.py"],
                str(temp_project_dir)
            )

            # Flake8 should be called with Python files
            mock_flake8.assert_called_once_with(
                ["app.py", "test.py"],
                str(temp_project_dir)
            )
            assert len(results) == 1

    def test_run_linters_javascript_files(self, temp_project_dir):
        """Test running linters on JavaScript files."""
        with patch.object(StaticAnalysisAggregator, '_run_eslint') as mock_eslint:
            mock_eslint.return_value = {"tool": "eslint", "issues": []}

            aggregator = StaticAnalysisAggregator(enable_astgrep=False)
            results = aggregator._run_linters(
                ["app.js", "test.tsx"],
                str(temp_project_dir)
            )

            # ESLint should be called with JS/TS files
            mock_eslint.assert_called_once_with(
                ["app.js", "test.tsx"],
                str(temp_project_dir)
            )
            assert len(results) == 1

    def test_run_linters_mixed_files(self, temp_project_dir):
        """Test running linters on mixed file types."""
        with patch.object(StaticAnalysisAggregator, '_run_flake8') as mock_flake8, \
             patch.object(StaticAnalysisAggregator, '_run_eslint') as mock_eslint:

            mock_flake8.return_value = {"tool": "flake8", "issues": []}
            mock_eslint.return_value = {"tool": "eslint", "issues": []}

            aggregator = StaticAnalysisAggregator(enable_astgrep=False)
            results = aggregator._run_linters(
                ["app.py", "app.js", "test.tsx"],
                str(temp_project_dir)
            )

            # Both linters should be called
            mock_flake8.assert_called_once()
            mock_eslint.assert_called_once()
            assert len(results) == 2

    @patch('subprocess.run')
    def test_check_tools_installed(self, mock_run):
        """Test checking which tools are installed."""
        # Mock all tools as installed
        mock_run.return_value = Mock(returncode=0)

        aggregator = StaticAnalysisAggregator(enable_astgrep=True)
        if aggregator.astgrep_scanner:
            aggregator.astgrep_scanner.check_installation = Mock(return_value=True)

        status = aggregator.check_tools_installed()

        assert isinstance(status, dict)
        assert "ast-grep" in status
        assert "flake8" in status
        assert "eslint" in status

    @patch.object(StaticAnalysisAggregator, '_run_linters')
    def test_analyze_handles_linter_errors_gracefully(self, mock_linters, temp_project_dir):
        """Test that analyze() handles linter errors gracefully."""
        # Mock linters to raise exception
        mock_linters.side_effect = Exception("Linter crashed")

        aggregator = StaticAnalysisAggregator(
            enable_astgrep=False,
            enable_linters=True
        )

        # Should not raise, should return empty results
        result = aggregator.analyze(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        assert result["linter_results"] == []
        assert result["stats"]["total_issues"] == 0

    @patch.object(StaticAnalysisAggregator, '_run_astgrep')
    def test_analyze_handles_astgrep_errors_gracefully(self, mock_astgrep, temp_project_dir):
        """Test that analyze() handles ast-grep errors gracefully."""
        # Mock ast-grep to raise exception
        mock_astgrep.side_effect = Exception("AST-Grep crashed")

        aggregator = StaticAnalysisAggregator(
            enable_astgrep=True,
            enable_linters=False
        )
        aggregator.astgrep_scanner = Mock()

        # Should not raise, should return empty results
        result = aggregator.analyze(
            changed_files=["app.py"],
            project_root=str(temp_project_dir)
        )

        assert result["security_findings"] == []
        assert result["stats"]["total_issues"] == 0
