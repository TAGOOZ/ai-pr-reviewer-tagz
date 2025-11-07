"""Phase 3 Integration Tests: Security aggregation and output formatting."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from coderabbit_ai.analyzers import SecurityAggregator
from coderabbit_ai.models import SecurityFinding, SecuritySummary, ReviewComment


@pytest.fixture
def sample_security_findings():
    """Create sample security findings for testing."""
    return [
        SecurityFinding(
            tool="ast-grep",
            rule_id="python/security/sql-injection",
            severity="critical",
            category="security",
            file="src/api.py",
            line=42,
            message="SQL injection vulnerability detected",
            code_snippet='query = f"SELECT * FROM users WHERE id={user_id}"',
            suggestion="Use parameterized queries",
            cwe_id="CWE-89",
            confidence=0.95
        ),
        SecurityFinding(
            tool="ast-grep",
            rule_id="python/security/sql-injection",
            severity="critical",
            category="security",
            file="src/api.py",
            line=44,  # Close to line 42 - should be deduplicated
            message="SQL injection vulnerability detected",
            code_snippet='query = f"SELECT * FROM users WHERE name={name}"',
            suggestion="Use parameterized queries",
            cwe_id="CWE-89",
            confidence=0.92
        ),
        SecurityFinding(
            tool="ast-grep",
            rule_id="python/security/xss",
            severity="high",
            category="security",
            file="src/views.py",
            line=28,
            message="Cross-site scripting vulnerability",
            confidence=0.88
        ),
        SecurityFinding(
            tool="semgrep",
            rule_id="python/security/hardcoded-password",
            severity="high",
            category="security",
            file="src/config.py",
            line=15,
            message="Hardcoded password detected",
            code_snippet='password = "admin123"',
            suggestion="Use environment variables or secrets manager",
            confidence=0.91
        ),
        SecurityFinding(
            tool="ast-grep",
            rule_id="python/best-practice/logging",
            severity="medium",
            category="best-practice",
            file="src/utils.py",
            line=100,
            message="Missing error logging",
            confidence=0.75
        ),
        SecurityFinding(
            tool="ast-grep",
            rule_id="python/style/line-length",
            severity="low",
            category="style",
            file="src/helpers.py",
            line=200,
            message="Line too long",
            confidence=0.65  # Below threshold
        )
    ]


class TestSecurityAggregator:
    """Test suite for SecurityAggregator (Phase 3)."""

    def test_initialization_default(self):
        """Test default initialization."""
        aggregator = SecurityAggregator()
        assert aggregator.block_on_critical is True
        assert aggregator.max_high_severity == 3
        assert aggregator.confidence_threshold == 0.7

    def test_initialization_custom(self):
        """Test initialization with custom settings."""
        aggregator = SecurityAggregator(
            block_on_critical=False,
            max_high_severity=5,
            confidence_threshold=0.8
        )
        assert aggregator.block_on_critical is False
        assert aggregator.max_high_severity == 5
        assert aggregator.confidence_threshold == 0.8

    def test_deduplication_same_line(self, sample_security_findings):
        """Test deduplication of findings on same line."""
        aggregator = SecurityAggregator()

        # Create two identical findings
        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/test",
                severity="high",
                category="security",
                file="test.py",
                line=10,
                message="Test issue",
                confidence=0.8
            ),
            SecurityFinding(
                tool="semgrep",
                rule_id="python/security/test",
                severity="high",
                category="security",
                file="test.py",
                line=10,
                message="Test issue",
                confidence=0.9  # Higher confidence
            )
        ]

        deduplicated = aggregator._deduplicate_findings(findings)

        # Should keep only one (highest confidence)
        assert len(deduplicated) == 1
        assert deduplicated[0].confidence == 0.9

    def test_deduplication_within_5_lines(self, sample_security_findings):
        """Test deduplication of findings within 5 lines."""
        aggregator = SecurityAggregator()

        # Get the two SQL injection findings (lines 42 and 44)
        sql_injection_findings = [f for f in sample_security_findings
                                  if f.rule_id == "python/security/sql-injection"]

        deduplicated = aggregator._deduplicate_findings(sql_injection_findings)

        # Should merge into one (lines 42 and 44 are within 5 lines)
        assert len(deduplicated) == 1
        assert deduplicated[0].confidence == 0.95  # Keep highest confidence

    def test_filter_by_confidence(self, sample_security_findings):
        """Test filtering by confidence threshold."""
        aggregator = SecurityAggregator(confidence_threshold=0.7)

        filtered = aggregator._filter_by_confidence(sample_security_findings, 0.7)

        # Should exclude the one with confidence 0.65
        assert len(filtered) == len(sample_security_findings) - 1
        assert all(f.confidence >= 0.7 for f in filtered)

    def test_prioritization_by_severity(self):
        """Test prioritization by severity."""
        aggregator = SecurityAggregator()

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="test1",
                severity="low",
                category="security",
                file="test.py",
                line=10,
                message="Low severity",
                confidence=0.9
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="test2",
                severity="critical",
                category="security",
                file="test.py",
                line=20,
                message="Critical severity",
                confidence=0.8
            ),
            SecurityFinding(
                tool="ast-grep",
                rule_id="test3",
                severity="high",
                category="security",
                file="test.py",
                line=30,
                message="High severity",
                confidence=0.95
            )
        ]

        prioritized = aggregator._prioritize_findings(findings)

        # Should be ordered: critical, high, low
        assert prioritized[0].severity == "critical"
        assert prioritized[1].severity == "high"
        assert prioritized[2].severity == "low"

    def test_generate_summary(self, sample_security_findings):
        """Test security summary generation."""
        aggregator = SecurityAggregator()

        # Filter to remove low-confidence findings
        filtered = [f for f in sample_security_findings if f.confidence >= 0.7]

        summary = aggregator._generate_summary(filtered)

        assert summary.total_findings == len(filtered)
        assert summary.by_severity["critical"] == 2  # Two SQL injection (before dedup)
        assert summary.by_severity["high"] == 2
        assert summary.by_severity["medium"] == 1
        assert len(summary.critical_files) > 0
        assert "ast-grep" in summary.tools_used

    def test_recommendation_block_on_critical(self, sample_security_findings):
        """Test recommendation: BLOCK on critical issues."""
        aggregator = SecurityAggregator(block_on_critical=True)

        filtered = [f for f in sample_security_findings if f.confidence >= 0.7]
        summary = aggregator._generate_summary(filtered)
        recommendation = aggregator._generate_recommendation(filtered, summary)

        assert recommendation.action == "block"
        assert recommendation.severity_level == "critical"
        assert "BLOCK MERGE" in recommendation.message
        assert recommendation.total_issues > 0

    def test_recommendation_caution_on_high(self):
        """Test recommendation: CAUTION on high-severity issues."""
        aggregator = SecurityAggregator(block_on_critical=False, max_high_severity=3)

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id=f"test{i}",
                severity="high",
                category="security",
                file="test.py",
                line=i*10,
                message=f"High issue {i}",
                confidence=0.9
            )
            for i in range(2)  # 2 high-severity issues
        ]

        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        assert recommendation.action == "caution"
        assert "CAUTION" in recommendation.message

    def test_recommendation_warning_on_medium(self):
        """Test recommendation: WARNING on medium-severity issues."""
        aggregator = SecurityAggregator()

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="test1",
                severity="medium",
                category="security",
                file="test.py",
                line=10,
                message="Medium issue",
                confidence=0.8
            )
        ]

        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        assert recommendation.action == "warning"
        assert "WARNING" in recommendation.message

    def test_recommendation_approve_no_issues(self):
        """Test recommendation: APPROVE when no issues."""
        aggregator = SecurityAggregator()

        findings = []
        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        assert recommendation.action == "approve"
        assert recommendation.severity_level == "none"
        assert "APPROVE" in recommendation.message
        assert recommendation.total_issues == 0

    def test_aggregate_full_flow(self, sample_security_findings):
        """Test full aggregation flow."""
        aggregator = SecurityAggregator(confidence_threshold=0.7)

        prioritized, summary, recommendation = aggregator.aggregate(
            security_findings=sample_security_findings,
            context_metadata={},
            verification_findings=None
        )

        # Verify deduplication and filtering occurred
        assert len(prioritized) < len(sample_security_findings)

        # Verify summary is accurate
        assert summary.total_findings == len(prioritized)
        assert summary.total_findings > 0

        # Verify recommendation makes sense
        assert recommendation.action in ["block", "caution", "warning", "approve"]
        assert recommendation.message != ""

    def test_convert_to_comments(self):
        """Test conversion of findings to ReviewComment objects."""
        aggregator = SecurityAggregator()

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id="python/security/sql-injection",
                severity="critical",
                category="security",
                file="src/api.py",
                line=42,
                message="SQL injection vulnerability",
                code_snippet='query = f"SELECT * FROM users WHERE id={user_id}"',
                suggestion="Use parameterized queries",
                cwe_id="CWE-89",
                confidence=0.95
            )
        ]

        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        comments = aggregator.convert_to_comments(findings, recommendation)

        # Should have summary comment + finding comment
        assert len(comments) >= 2

        # Check summary comment
        summary_comment = comments[0]
        assert summary_comment.file_path == "SECURITY_SUMMARY"
        assert "BLOCK" in summary_comment.message

        # Check finding comment
        finding_comment = comments[1]
        assert finding_comment.file_path == "src/api.py"
        assert finding_comment.line_number == 42
        assert "SQL injection" in finding_comment.message
        assert "CWE-89" in finding_comment.message
        assert finding_comment.severity == "critical"

    def test_convert_to_comments_with_approve(self):
        """Test that APPROVE recommendation doesn't add summary comment."""
        aggregator = SecurityAggregator()

        findings = []  # No findings
        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        comments = aggregator.convert_to_comments(findings, recommendation)

        # Should have no comments (approve doesn't add summary)
        assert len(comments) == 0

    def test_high_severity_threshold_blocking(self):
        """Test blocking when high-severity count exceeds threshold."""
        aggregator = SecurityAggregator(
            block_on_critical=True,
            max_high_severity=2
        )

        findings = [
            SecurityFinding(
                tool="ast-grep",
                rule_id=f"test{i}",
                severity="high",
                category="security",
                file="test.py",
                line=i*10,
                message=f"High issue {i}",
                confidence=0.9
            )
            for i in range(3)  # 3 high-severity issues (exceeds threshold of 2)
        ]

        summary = aggregator._generate_summary(findings)
        recommendation = aggregator._generate_recommendation(findings, summary)

        assert recommendation.action == "block"
        assert recommendation.severity_level == "high"
        assert "3 high-severity" in recommendation.message


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    from coderabbit_ai.models import Repository, Platform

    return Repository(
        id="repo123",
        name="test-repo",
        owner="test-owner",
        platform=Platform.GITHUB,
        clone_url="https://github.com/test-owner/test-repo",
        default_branch="main"
    )


@pytest.fixture
def mock_file_changes_with_security_issues():
    """Create mock file changes with security issues."""
    from coderabbit_ai.models import FileChange, ChangeType

    file1 = FileChange(
        path="src/api.py",
        change_type=ChangeType.MODIFIED,
        content='''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id={user_id}"
    cursor.execute(query)
    return cursor.fetchone()
''',
        diff="+    query = f\"SELECT * FROM users WHERE id={user_id}\"",
        language="python"
    )

    file2 = FileChange(
        path="src/views.py",
        change_type=ChangeType.MODIFIED,
        content='return render_template("page.html", content=user_input)',
        diff="+return render_template(\"page.html\", content=user_input)",
        language="python"
    )

    return [file1, file2]


@pytest.mark.integration
class TestPipelinePhase3Integration:
    """Integration tests for Phase 3 in the pipeline."""

    def test_run_static_analysis_returns_tuple(
        self,
        mock_file_changes_with_security_issues
    ):
        """Test that _run_static_analysis returns a tuple of (linter_results, security_findings)."""
        from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline

        pipeline = CodeRabbitMultiAgentPipeline({})

        # Call _run_static_analysis
        result = pipeline._run_static_analysis(
            mock_file_changes_with_security_issues,
            project_root="/test/repo"
        )

        # Verify it returns a tuple
        assert isinstance(result, tuple)
        assert len(result) == 2

        linter_results, security_findings = result

        # Verify types
        assert isinstance(linter_results, list)
        assert isinstance(security_findings, list)

    @patch('coderabbit_ai.pipeline.CodeRabbitMultiAgentPipeline._run_static_analysis')
    @patch('coderabbit_ai.pipeline.CodeRabbitMultiAgentPipeline._gather_historical_data')
    @patch('coderabbit_ai.pipeline.CodeRabbitMultiAgentPipeline._format_code_changes')
    def test_prepare_context_data_includes_security_findings(
        self,
        mock_format_changes,
        mock_gather_history,
        mock_run_static,
        mock_repository,
        mock_file_changes_with_security_issues
    ):
        """Test that _prepare_context_data includes security findings."""
        from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline
        from coderabbit_ai.models import ReviewRequest, PullRequest, User, AISettings, ReviewRules, OrganizationConfig

        # Setup mocks
        mock_format_changes.return_value = "Code changes..."
        mock_gather_history.return_value = "Historical data..."
        mock_run_static.return_value = (
            [{"tool": "flake8", "issues": []}],
            [
                SecurityFinding(
                    tool="ast-grep",
                    rule_id="python/security/sql-injection",
                    severity="critical",
                    category="security",
                    file="src/api.py",
                    line=42,
                    message="SQL injection vulnerability",
                    confidence=0.95
                )
            ]
        )

        # Create request
        user = User(id="user1", username="testuser")
        pr = PullRequest(
            id="pr1",
            number=123,
            title="Test PR",
            description="Test description",
            author=user,
            base_branch="main",
            head_branch="feature",
            files_changed=mock_file_changes_with_security_issues
        )

        ai_settings = AISettings(
            primary_model="gpt-4",
            fallback_models=["gpt-3.5"],
            temperature=0.7,
            max_tokens=4000
        )
        review_rules = ReviewRules(
            enabled_checks=["security"],
            severity_thresholds={"critical": "critical"},
            custom_rules=[]
        )
        org_config = OrganizationConfig(
            id="org1",
            name="Test Org",
            review_rules=review_rules,
            ai_settings=ai_settings,
            integrations=[]
        )

        request = ReviewRequest(
            repository=mock_repository,
            pull_request=pr,
            config=org_config
        )

        pipeline = CodeRabbitMultiAgentPipeline({})
        context_data = pipeline._prepare_context_data(request)

        # Verify security findings are included
        assert hasattr(context_data, 'security_findings')
        assert len(context_data.security_findings) > 0
        assert context_data.security_findings[0].severity == "critical"
