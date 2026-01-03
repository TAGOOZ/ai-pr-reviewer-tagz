"""Integration tests for security scanner aggregation."""

import pytest
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from coderabbit_ai.analyzers.astgrep_scanner import AstGrepScanner
from coderabbit_ai.models import SecurityFinding


class TestSecurityScannerAggregation:
    """Integration tests for security scanner aggregation."""

    def test_multiple_scanner_results(self):
        """Test aggregating results from multiple scanners."""
        # Simulate ast-grep scanner
        astgrep_scanner = AstGrepScanner()
        astgrep_results = astgrep_scanner.scan_files([
            {'path': 'src/api.py', 'content': 'os.system(user_input)'}
        ])

        # Simulate semgrep scanner (mocked)
        semgrep_results = [
            SecurityFinding(
                tool="semgrep",
                rule_id="python.security.sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="Potential SQL injection vulnerability",
                code_snippet='query = "SELECT * FROM users WHERE id = " + user_id'
            )
        ]

        # Aggregate results
        all_findings = astgrep_results + semgrep_results

        # Verify aggregation
        assert len(all_findings) > 0
        assert any(f.tool == "ast-grep" for f in all_findings)
        assert any(f.tool == "semgrep" for f in all_findings)

    def test_deduplicate_findings(self):
        """Test deduplicating duplicate findings."""
        # Create duplicate findings from different scanners
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="security.sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection detected",
                code_snippet='query = "SELECT * FROM users WHERE id = " + user_id'
            ),
            SecurityFinding(
                tool="semgrep",
                rule_id="python.security.sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="Potential SQL injection vulnerability",
                code_snippet='query = "SELECT * FROM users WHERE id = " + user_id'
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="security.command-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=15,
                message="Command injection detected",
                code_snippet='os.system(cmd)'
            )
        ]

        # Deduplicate by file and line number
        seen = set()
        deduplicated = []
        for finding in findings:
            key = (finding.file, finding.line)
            if key not in seen:
                seen.add(key)
                deduplicated.append(finding)

        # Verify deduplication
        assert len(deduplicated) <= len(findings)
        assert len(deduplicated) == 2  # 2 unique locations

    def test_merge_duplicate_findings(self):
        """Test merging duplicate findings with enhanced data."""
        # Create duplicate findings
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="security.sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection",
                code_snippet='query = "SELECT * FROM users WHERE id = " + user_id'
            ),
            SecurityFinding(
                tool="semgrep",
                rule_id="python.security.sql-injection",
                severity="critical",  # Higher severity
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection with user input",
                code_snippet='query = "SELECT * FROM users WHERE id = " + user_id',
                column=15  # More precise column
            )
        ]

        # Merge duplicates - keep highest severity and best metadata
        merged = {}
        for finding in findings:
            key = (finding.file, finding.line)
            if key in merged:
                # Merge - keep highest severity
                if finding.severity == "critical":
                    merged[key] = finding
                # Add more precise column if available
                if finding.column and not merged[key].column:
                    merged[key].column = finding.column
            else:
                merged[key] = finding

        result = list(merged.values())

        # Verify merge
        assert len(result) == 1
        assert result[0].severity == "critical"  # Kept higher severity
        assert result[0].column == 15  # Kept precise column

    def test_priority_based_sorting(self):
        """Test sorting findings by priority."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="low-severity",
                severity="low",
                category="security",
                file="src/low.py",
                line=1,
                message="Low severity issue"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="critical-severity",
                severity="critical",
                category="security",
                file="src/critical.py",
                line=1,
                message="Critical vulnerability"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="medium-severity",
                severity="medium",
                category="security",
                file="src/medium.py",
                line=1,
                message="Medium severity issue"
            )
        ]

        # Sort by severity priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_findings = sorted(findings, key=lambda f: priority_order.get(f.severity, 4))

        # Verify order
        assert sorted_findings[0].severity == "critical"
        assert sorted_findings[1].severity == "medium"
        assert sorted_findings[2].severity == "low"

    def test_aggregate_by_file(self):
        """Test aggregating findings by file."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="xss",
                severity="high",
                category="security",
                file="src/api.py",
                line=20,
                message="XSS vulnerability"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="hardcoded-secret",
                severity="critical",
                category="security",
                file="src/config.py",
                line=5,
                message="Hardcoded API key"
            )
        ]

        # Group by file
        by_file: Dict[str, List[SecurityFinding]] = {}
        for finding in findings:
            if finding.file not in by_file:
                by_file[finding.file] = []
            by_file[finding.file].append(finding)

        # Verify aggregation
        assert "src/api.py" in by_file
        assert "src/config.py" in by_file
        assert len(by_file["src/api.py"]) == 2
        assert len(by_file["src/config.py"]) == 1

    def test_aggregate_by_category(self):
        """Test aggregating findings by category."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="long-function",
                severity="low",
                category="performance",
                file="src/utils.py",
                line=5,
                message="Long function detected"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="xss",
                severity="high",
                category="security",
                file="src/api.py",
                line=20,
                message="XSS vulnerability"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="unused-var",
                severity="low",
                category="code-quality",
                file="src/utils.py",
                line=10,
                message="Unused variable"
            )
        ]

        # Group by category
        by_category: Dict[str, List[SecurityFinding]] = {}
        for finding in findings:
            if finding.category not in by_category:
                by_category[finding.category] = []
            by_category[finding.category].append(finding)

        # Verify aggregation
        assert "security" in by_category
        assert "performance" in by_category
        assert "code-quality" in by_category
        assert len(by_category["security"]) == 2
        assert len(by_category["performance"]) == 1
        assert len(by_category["code-quality"]) == 1

    def test_aggregate_with_confidence_scores(self):
        """Test aggregating findings with confidence scores."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="sql-injection",
                severity="high",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection",
                confidence_score=0.95  # High confidence
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="potential-xss",
                severity="medium",
                category="security",
                file="src/api.py",
                line=20,
                message="Potential XSS",
                confidence_score=0.60  # Lower confidence
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="hardcoded-secret",
                severity="critical",
                category="security",
                file="src/config.py",
                line=5,
                message="Hardcoded secret",
                confidence_score=0.85  # Medium-high confidence
            )
        ]

        # Sort by confidence score
        sorted_by_confidence = sorted(
            findings,
            key=lambda f: f.confidence_score or 0.0,
            reverse=True
        )

        # Verify ordering
        assert sorted_by_confidence[0].confidence_score == 0.95
        assert sorted_by_confidence[1].confidence_score == 0.85
        assert sorted_by_confidence[2].confidence_score == 0.60

    def test_filter_by_severity_threshold(self):
        """Test filtering findings by severity threshold."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="critical-vuln",
                severity="critical",
                category="security",
                file="src/critical.py",
                line=1,
                message="Critical"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="high-vuln",
                severity="high",
                category="security",
                file="src/high.py",
                line=1,
                message="High"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="medium-vuln",
                severity="medium",
                category="security",
                file="src/medium.py",
                line=1,
                message="Medium"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="low-vuln",
                severity="low",
                category="security",
                file="src/low.py",
                line=1,
                message="Low"
            )
        ]

        # Filter to high and critical only
        high_severity_order = {"critical": 0, "high": 1}
        filtered = [
            f for f in findings
            if f.severity in ["critical", "high"]
        ]

        # Verify filter
        assert len(filtered) == 2
        assert all(f.severity in ["critical", "high"] for f in filtered)
        assert not any(f.severity in ["medium", "low"] for f in filtered)

    def test_aggregate_statistics(self):
        """Test computing aggregation statistics."""
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="sql-injection",
                severity="critical",
                category="security",
                file="src/api.py",
                line=10,
                message="SQL injection"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="xss",
                severity="high",
                category="security",
                file="src/api.py",
                line=20,
                message="XSS"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="long-function",
                severity="low",
                category="performance",
                file="src/utils.py",
                line=5,
                message="Long function"
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="unused-var",
                severity="low",
                category="code-quality",
                file="src/utils.py",
                line=10,
                message="Unused variable"
            )
        ]

        # Compute statistics
        stats = {
            "total_findings": len(findings),
            "by_severity": {},
            "by_category": {},
            "by_tool": {}
        }

        for finding in findings:
            # By severity
            if finding.severity not in stats["by_severity"]:
                stats["by_severity"][finding.severity] = 0
            stats["by_severity"][finding.severity] += 1

            # By category
            if finding.category not in stats["by_category"]:
                stats["by_category"][finding.category] = 0
            stats["by_category"][finding.category] += 1

            # By tool
            if finding.tool not in stats["by_tool"]:
                stats["by_tool"][finding.tool] = 0
            stats["by_tool"][finding.tool] += 1

        # Verify statistics
        assert stats["total_findings"] == 4
        assert stats["by_severity"]["critical"] == 1
        assert stats["by_severity"]["high"] == 1
        assert stats["by_severity"]["low"] == 2
        assert stats["by_category"]["security"] == 2
        assert stats["by_category"]["performance"] == 1
        assert stats["by_category"]["code-quality"] == 1
        assert stats["by_tool"]["ast-grep"] == 4
