"""Tests for AST-Grep scanner."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from coderabbit_ai.analyzers.astgrep_scanner import AstGrepScanner
from coderabbit_ai.models import SecurityFinding, SecuritySummary


@pytest.fixture
def temp_rules_dir():
    """Create temporary directory for rules."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_rules_repo(temp_rules_dir):
    """Create mock rules repository structure."""
    # Create rules directory structure
    rules_dir = temp_rules_dir / "rules"
    rules_dir.mkdir()

    # Python rules
    python_dir = rules_dir / "python"
    python_dir.mkdir()

    # Create a sample rule file
    rule_file = python_dir / "sql-injection.yml"
    rule_content = """
id: python/security/sql-injection
language: python
severity: critical
message: Potential SQL injection vulnerability
rule:
  pattern: execute($SQL)
  where:
    SQL: {regex: ".*f\".*"}
"""
    rule_file.write_text(rule_content)

    # Write cache timestamp
    timestamp_file = temp_rules_dir / ".cache_timestamp"
    timestamp_file.write_text(datetime.now().isoformat())

    return temp_rules_dir


@pytest.fixture
def sample_python_file(tmp_path):
    """Create sample Python file with security issue."""
    test_file = tmp_path / "test.py"
    test_file.write_text('''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id={user_id}"
    cursor.execute(query)
    return cursor.fetchone()
''')
    return test_file


class TestAstGrepScanner:
    """Test suite for AstGrepScanner."""

    def test_initialization(self, mock_rules_repo):
        """Test scanner initialization."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        assert scanner.rules_path == mock_rules_repo
        assert scanner.rules_repo == "coderabbitai/ast-grep-essentials"
        assert scanner.cache_ttl == 86400  # 24 hours

    def test_initialization_creates_rules_if_missing(self, temp_rules_dir):
        """Test that scanner clones rules if they don't exist."""
        with patch.object(AstGrepScanner, '_clone_rules_repo') as mock_clone:
            scanner = AstGrepScanner(
                rules_path=str(temp_rules_dir / "nonexistent"),
                auto_update=False
            )
            mock_clone.assert_called_once()

    def test_cache_staleness_check(self, mock_rules_repo):
        """Test cache staleness detection."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Fresh cache
        assert not scanner._is_cache_stale()

        # Modify timestamp to make it stale
        timestamp_file = mock_rules_repo / ".cache_timestamp"
        old_time = datetime.now() - timedelta(hours=25)
        timestamp_file.write_text(old_time.isoformat())

        assert scanner._is_cache_stale()

    def test_find_rule_files(self, mock_rules_repo):
        """Test finding rule files in repository."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Find all rules
        all_rules = scanner._find_rule_files()
        assert len(all_rules) > 0
        assert all(r.suffix in [".yml", ".yaml"] for r in all_rules)

        # Find Python rules only
        python_rules = scanner._find_rule_files(language="python")
        assert len(python_rules) > 0
        assert all("python" in str(r) for r in python_rules)

    def test_language_detection(self, mock_rules_repo):
        """Test programming language detection from file extension."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        assert scanner._detect_language("test.py") == "python"
        assert scanner._detect_language("test.js") == "javascript"
        assert scanner._detect_language("test.ts") == "typescript"
        assert scanner._detect_language("test.go") == "go"
        assert scanner._detect_language("test.unknown") is None

    def test_extract_rule_id(self, mock_rules_repo):
        """Test extracting rule ID from rule file path."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        rule_file = mock_rules_repo / "rules" / "python" / "security" / "sql-injection.yml"
        rule_file.parent.mkdir(parents=True, exist_ok=True)
        rule_file.touch()

        rule_id = scanner._extract_rule_id(rule_file)
        assert "python" in rule_id
        assert "security" in rule_id or "sql-injection" in rule_id

    def test_extract_severity(self, mock_rules_repo):
        """Test severity extraction from match data."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # From match metadata
        match_with_severity = {"severity": "HIGH"}
        rule_file = mock_rules_repo / "rules" / "test.yml"
        assert scanner._extract_severity(match_with_severity, rule_file) == "high"

        # Inferred from rule path
        match_no_severity = {}
        security_rule = mock_rules_repo / "rules" / "python" / "security" / "test.yml"
        security_rule.parent.mkdir(parents=True, exist_ok=True)
        assert scanner._extract_severity(match_no_severity, security_rule) == "high"

    def test_extract_category(self, mock_rules_repo):
        """Test category extraction from rule file path."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        security_rule = mock_rules_repo / "rules" / "python" / "security" / "test.yml"
        security_rule.parent.mkdir(parents=True, exist_ok=True)
        assert scanner._extract_category(security_rule) == "security"

        perf_rule = mock_rules_repo / "rules" / "python" / "performance" / "test.yml"
        perf_rule.parent.mkdir(parents=True, exist_ok=True)
        assert scanner._extract_category(perf_rule) == "performance"

    @patch('subprocess.run')
    def test_scan_with_no_findings(self, mock_run, mock_rules_repo, tmp_path):
        """Test scanning files with no security findings."""
        # Mock subprocess to return no findings
        mock_run.return_value = Mock(
            returncode=0,
            stdout="[]",
            stderr=""
        )

        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Create a simple file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = scanner.scan(
            changed_files=["test.py"],
            project_root=str(tmp_path)
        )

        assert result["tool"] == "ast-grep"
        assert len(result["findings"]) == 0
        assert result["summary"]["total_findings"] == 0

    @patch('subprocess.run')
    def test_scan_with_findings(self, mock_run, mock_rules_repo, tmp_path):
        """Test scanning files with security findings."""
        # Mock subprocess to return a finding
        mock_finding = {
            "message": "SQL injection detected",
            "range": {
                "start": {"line": 3, "column": 5}
            },
            "text": "cursor.execute(f\"SELECT * FROM users WHERE id={user_id}\")"
        }
        mock_run.return_value = Mock(
            returncode=0,
            stdout=json.dumps([mock_finding]),
            stderr=""
        )

        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Create a file with security issue
        test_file = tmp_path / "test.py"
        test_file.write_text('''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id={user_id}"
    cursor.execute(query)
''')

        result = scanner.scan(
            changed_files=["test.py"],
            project_root=str(tmp_path)
        )

        assert result["tool"] == "ast-grep"
        assert len(result["findings"]) > 0

        finding = result["findings"][0]
        assert finding["file"] == "test.py"
        assert finding["severity"] in ["critical", "high", "medium", "low"]
        assert "message" in finding

    @patch('subprocess.run')
    def test_scan_timeout_handling(self, mock_run, mock_rules_repo, tmp_path):
        """Test handling of scan timeouts."""
        import subprocess
        # Mock subprocess to raise timeout
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["ast-grep"], timeout=30)

        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        result = scanner.scan(
            changed_files=["test.py"],
            project_root=str(tmp_path)
        )

        # Should return empty result on timeout
        assert result["tool"] == "ast-grep"
        assert len(result["findings"]) == 0

    def test_generate_summary(self, mock_rules_repo):
        """Test summary generation from findings."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/sql-injection",
                severity="critical",
                category="security",
                file="test1.py",
                line=10,
                message="SQL injection"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/xss",
                severity="high",
                category="security",
                file="test2.py",
                line=20,
                message="XSS vulnerability"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/best-practice/logging",
                severity="low",
                category="best-practice",
                file="test1.py",
                line=30,
                message="Missing logging"
            )
        ]

        summary = scanner._generate_summary(findings)

        assert summary.total_findings == 3
        assert summary.by_severity["critical"] == 1
        assert summary.by_severity["high"] == 1
        assert summary.by_severity["low"] == 1
        assert summary.by_category["security"] == 2
        assert summary.by_category["best-practice"] == 1
        assert "test1.py" in summary.critical_files
        assert "test2.py" in summary.critical_files
        assert "ast-grep" in summary.tools_used

    def test_empty_result_structure(self, mock_rules_repo):
        """Test structure of empty result."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        result = scanner._empty_result()

        assert result["tool"] == "ast-grep"
        assert result["findings"] == []
        assert result["summary"]["total_findings"] == 0
        assert result["stats"]["files_scanned"] == 0

    @patch('subprocess.run')
    def test_check_installation(self, mock_run):
        """Test checking if ast-grep is installed."""
        # Mock successful version check
        mock_run.return_value = Mock(returncode=0, stdout="ast-grep 0.1.0")

        scanner = AstGrepScanner(auto_update=False)
        assert scanner.check_installation() is True

        # Mock failed version check
        mock_run.return_value = Mock(returncode=1)
        assert scanner.check_installation() is False

    @patch('subprocess.run')
    def test_parse_astgrep_output(self, mock_run, mock_rules_repo, tmp_path):
        """Test parsing ast-grep JSON output."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        matches = [
            {
                "message": "Security issue found",
                "range": {
                    "start": {"line": 42, "column": 10}
                },
                "text": "vulnerable_code_here()",
                "fix": "safe_code_here()"
            }
        ]

        file_path = tmp_path / "test.py"
        file_path.write_text("# test code")

        rule_file = mock_rules_repo / "rules" / "python" / "security" / "test.yml"
        rule_file.parent.mkdir(parents=True, exist_ok=True)
        rule_file.touch()

        findings = scanner._parse_astgrep_output(
            matches,
            file_path,
            str(tmp_path),
            rule_file
        )

        assert len(findings) == 1
        finding = findings[0]
        assert finding.tool == "ast-grep"
        assert finding.file == "test.py"
        assert finding.line == 42
        assert finding.column == 10
        assert finding.message == "Security issue found"
        assert finding.code_snippet == "vulnerable_code_here()"
        assert finding.suggestion == "safe_code_here()"

    @patch('subprocess.run')
    def test_scan_multiple_files(self, mock_run, mock_rules_repo, tmp_path):
        """Test scanning multiple files."""
        # Mock subprocess to return findings
        mock_run.return_value = Mock(
            returncode=0,
            stdout="[]",
            stderr=""
        )

        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Create multiple test files
        for i in range(3):
            test_file = tmp_path / f"test{i}.py"
            test_file.write_text(f"print('test {i}')")

        result = scanner.scan(
            changed_files=["test0.py", "test1.py", "test2.py"],
            project_root=str(tmp_path)
        )

        assert result["stats"]["files_scanned"] == 3

    def test_language_filter(self, mock_rules_repo, tmp_path):
        """Test scanning with language filter."""
        scanner = AstGrepScanner(
            rules_path=str(mock_rules_repo),
            auto_update=False
        )

        # Create files of different languages
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')")

        js_file = tmp_path / "test.js"
        js_file.write_text("console.log('hello');")

        # Scan only Python files
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="[]", stderr="")

            result = scanner.scan(
                changed_files=["test.py", "test.js"],
                project_root=str(tmp_path),
                language="python"
            )

            # Should only scan Python file
            assert result["tool"] == "ast-grep"
