"""Phase 2 Integration Tests: Security findings through agent pipeline."""

import pytest
from unittest.mock import Mock, patch

from coderabbit_ai.agents import ContextEngineeringAgent, ReviewAgent
from coderabbit_ai.models import ContextData, SecurityFinding


@pytest.fixture
def context_data_with_security():
    """Create context data with security findings."""
    security_findings = [
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
            rule_id="python/security/xss",
            severity="high",
            category="security",
            file="src/views.py",
            line=28,
            message="Cross-site scripting vulnerability",
            confidence=0.88
        )
    ]

    return ContextData(
        repo_structure="Repository: test-repo\nOwner: test-owner",
        code_changes="File: src/api.py\nLanguage: python\nContent: def get_user(): ...",
        historical_data="No historical data",
        static_analysis_results=[],
        security_findings=security_findings
    )


@patch('dspy.ChainOfThought')
def test_context_engineering_formats_security_findings(mock_cot, context_data_with_security):
    """Test that ContextEngineeringAgent formats security findings for LLM."""
    # Mock DSPy response
    mock_result = Mock()
    mock_result.enriched_context = "Base context"
    mock_result.code_relationships = "No relationships"
    mock_result.relevant_patterns = "No patterns"
    mock_result.risk_assessment = "medium"

    mock_generator = Mock(return_value=mock_result)
    mock_cot.return_value = mock_generator

    agent = ContextEngineeringAgent()
    response = agent.forward(context_data_with_security)

    # Verify security findings were formatted and included
    assert "🔒 SECURITY ANALYSIS" in response.enriched_context
    assert "CRITICAL SEVERITY" in response.enriched_context
    assert "sql-injection" in response.enriched_context
    assert "CWE-89" in response.enriched_context

    # Verify metadata includes security stats
    assert response.metadata.get("security_findings_count") == 2
    assert response.metadata.get("critical_security_issues") == 1
    assert response.metadata.get("high_security_issues") == 1
    assert "ast-grep" in response.metadata.get("security_tools_used", [])


@patch('dspy.ChainOfThought')
def test_review_agent_factors_security_in_complexity(mock_cot, context_data_with_security):
    """Test that ReviewAgent factors security findings into complexity score."""
    # Mock ContextEngineeringAgent response
    context_response = Mock()
    context_response.enriched_context = "Security analysis context"
    context_response.code_relationships = "Relationships"
    context_response.relevant_patterns = "Patterns"
    context_response.metadata = {
        "risk_assessment": {"complexity": "medium"},
        "security_findings_count": 2,
        "critical_security_issues": 1,  # This should max out security risk
        "high_security_issues": 1,
        "security_tools_used": ["ast-grep"]
    }

    # Mock DSPy reviewer
    mock_review_result = Mock()
    mock_review_result.review_findings = "Critical security issues found"
    mock_review_result.confidence_scores = "high: 0.9, medium: 0.7"
    mock_review_result.suggested_improvements = "Fix SQL injection"

    mock_reviewer = Mock(return_value=mock_review_result)
    mock_cot.return_value = mock_reviewer

    agent = ReviewAgent()
    response = agent.forward(
        code_changes="def get_user(): ...",
        context_response=context_response,
        org_config={"ai_settings": {}}  # Minimal config for test
    )

    # Verify security metadata is included
    assert response.metadata.get("security") is not None
    security_meta = response.metadata["security"]
    assert security_meta["total_findings"] == 2
    assert security_meta["critical_issues"] == 1
    assert security_meta["security_risk_weight"] == 1.0  # Critical = max risk

    # Verify complexity score factors in security
    complexity = response.metadata.get("complexity_score")
    assert complexity is not None
    # With critical security issues, complexity should be elevated
    # (Note: base code is simple, so even with security weight it's not huge)
    assert complexity > 0.1  # Should be higher than 0 due to security risk
    # The important part is that security_risk_weight is set correctly (verified above)


def test_security_risk_weight_calculation():
    """Test ReviewAgent's security risk weight calculation logic."""
    agent = ReviewAgent()

    # Test critical issue = max risk
    context_critical = Mock()
    context_critical.metadata = {
        "critical_security_issues": 1,
        "high_security_issues": 0,
        "security_findings_count": 1
    }
    assert agent._calculate_security_risk_weight(context_critical) == 1.0

    # Test multiple high issues = very high risk
    context_high = Mock()
    context_high.metadata = {
        "critical_security_issues": 0,
        "high_security_issues": 5,
        "security_findings_count": 5
    }
    assert agent._calculate_security_risk_weight(context_high) == 0.9

    # Test moderate high issues = high risk
    context_moderate = Mock()
    context_moderate.metadata = {
        "critical_security_issues": 0,
        "high_security_issues": 3,
        "security_findings_count": 3
    }
    assert agent._calculate_security_risk_weight(context_moderate) == 0.7

    # Test no security findings = no risk
    context_none = Mock()
    context_none.metadata = {
        "critical_security_issues": 0,
        "high_security_issues": 0,
        "security_findings_count": 0
    }
    assert agent._calculate_security_risk_weight(context_none) == 0.0


@patch('dspy.ChainOfThought')
def test_full_security_pipeline_integration(mock_cot, context_data_with_security):
    """Test security findings flow through entire agent pipeline."""
    # Mock ContextEngineeringAgent
    mock_context_result = Mock()
    mock_context_result.enriched_context = "Context with security"
    mock_context_result.code_relationships = "Relationships"
    mock_context_result.relevant_patterns = "Patterns"
    mock_context_result.risk_assessment = "high"

    # Mock ReviewAgent
    mock_review_result = Mock()
    mock_review_result.review_findings = "Security issues detected"
    mock_review_result.confidence_scores = "high: 0.9"
    mock_review_result.suggested_improvements = "Fix vulnerabilities"

    mock_generator = Mock(side_effect=[mock_context_result, mock_review_result])
    mock_cot.return_value = mock_generator

    # Step 1: ContextEngineeringAgent enriches with security
    context_agent = ContextEngineeringAgent()
    context_response = context_agent.forward(context_data_with_security)

    assert context_response.metadata["security_findings_count"] == 2
    assert context_response.metadata["critical_security_issues"] == 1
    assert "🔒 SECURITY ANALYSIS" in context_response.enriched_context

    # Step 2: ReviewAgent uses security for complexity
    review_agent = ReviewAgent()
    review_response = review_agent.forward(
        code_changes="def get_user(): ...",
        context_response=context_response,
        org_config={"ai_settings": {}}  # Minimal config for test
    )

    # Verify security propagated through pipeline
    assert review_response.metadata["security"] is not None
    assert review_response.metadata["security"]["critical_issues"] == 1
    assert review_response.metadata["security"]["security_risk_weight"] == 1.0

    # Verify complexity elevated due to security
    assert review_response.metadata["complexity_score"] > 0.0
