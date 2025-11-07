"""Tests for individual AI agents."""

import pytest
from unittest.mock import Mock, patch

from coderabbit_ai.agents import ContextEngineeringAgent, ReviewAgent, VerificationAgent
from coderabbit_ai.models import ContextData, ContextEngineeringResponse, ReviewAgentResponse


@pytest.fixture
def sample_context_data():
    """Create sample context data for testing."""
    return ContextData(
        repo_structure="Repository: test-repo\nOwner: test-owner",
        code_changes="File: src/main.py\nLanguage: python\nContent: print('Hello')",
        historical_data="No historical data available",
        static_analysis_results=[
            {
                "tool": "flake8",
                "issues": [
                    {
                        "severity": "warning",
                        "message": "Line too long",
                        "file": "src/main.py"
                    }
                ]
            }
        ]
    )


def test_context_engineering_agent_initialization():
    """Test Context Engineering Agent initialization."""
    agent = ContextEngineeringAgent()
    assert agent is not None
    assert agent.context_generator is not None


@patch('dspy.ChainOfThought')
def test_context_engineering_agent_forward(mock_chain, sample_context_data):
    """Test Context Engineering Agent forward method."""
    # Mock the DSPy chain
    mock_result = Mock()
    mock_result.enriched_context = "Enriched context"
    mock_result.code_relationships = "Code relationships"
    mock_result.relevant_patterns = "Relevant patterns"
    
    mock_chain.return_value.return_value = mock_result
    
    agent = ContextEngineeringAgent()
    response = agent.forward(sample_context_data)
    
    assert isinstance(response, ContextEngineeringResponse)
    assert response.agent_id == "context_engineering"
    assert response.enriched_context == "Enriched context"
    assert response.code_relationships == "Code relationships"
    assert response.relevant_patterns == "Relevant patterns"


def test_context_engineering_static_analysis_formatting():
    """Test static analysis results formatting."""
    agent = ContextEngineeringAgent()

    results = [
        {
            "tool": "pylint",
            "issues": [
                {"severity": "error", "message": "Syntax error", "file": "test.py"},
                {"severity": "warning", "message": "Unused variable", "file": "test.py"}
            ]
        }
    ]

    formatted = agent._format_static_analysis(results)

    # Check for summary information
    assert "pylint: 2 issues" in formatted
    assert "error" in formatted.lower()
    assert "warning" in formatted.lower()
    # Check that it's not empty and has the tool name
    assert len(formatted) > 0
    assert "pylint" in formatted


def test_review_agent_initialization():
    """Test Review Agent initialization."""
    agent = ReviewAgent()
    assert agent is not None
    assert agent.reviewer is not None
    assert agent.model_router is not None


def test_review_agent_complexity_calculation():
    """Test complexity calculation."""
    agent = ReviewAgent()

    simple_code = "print('hello')"
    complex_code = """
    def complex_function():
        if condition:
            for item in items:
                while item.valid():
                    try:
                        process(item)
                    except Exception:
                        handle_error()
    """

    # Create a mock context response
    mock_context_response = Mock()
    mock_context_response.metadata = {"risk_assessment": {"complexity": "low"}}

    simple_complexity = agent._calculate_enhanced_complexity(simple_code, mock_context_response)
    complex_complexity = agent._calculate_enhanced_complexity(complex_code, mock_context_response)

    assert simple_complexity < complex_complexity
    assert 0 <= simple_complexity <= 1
    assert 0 <= complex_complexity <= 1


def test_verification_agent_initialization():
    """Test Verification Agent initialization."""
    agent = VerificationAgent("security")
    assert agent is not None
    assert agent.specialization == "security"
    assert agent.verifier is not None


def test_verification_agent_invalid_specialization():
    """Test Verification Agent with invalid specialization."""
    with pytest.raises(ValueError):
        VerificationAgent("invalid_specialization")


def test_verification_agent_specialization_context():
    """Test specialization context generation."""
    security_agent = VerificationAgent("security")
    performance_agent = VerificationAgent("performance")

    security_context = security_agent._generate_specialization_context()
    performance_context = performance_agent._generate_specialization_context()

    assert "security" in security_context.lower()
    assert "vulnerabilities" in security_context.lower()
    assert "performance" in performance_context.lower()
    assert "bottleneck" in performance_context.lower()


@pytest.mark.parametrize("specialization", [
    "security", "performance", "style", "logic", "testing",
    "documentation", "accessibility", "maintainability", "architecture", "dependencies",
    "requirements_validation"
])
def test_all_verification_specializations(specialization):
    """Test all verification agent specializations."""
    agent = VerificationAgent(specialization)
    assert agent.specialization == specialization

    context = agent._generate_specialization_context()
    # Just verify that each specialization generates meaningful context
    assert len(context) > 50  # Should be a substantial context, not just empty
    assert "focus on" in context.lower()  # All contexts start with "Focus on"


# Hybrid context integration tests
@pytest.fixture
def sample_context_data_with_hybrid():
    """Create sample context data with hybrid context for testing."""
    from coderabbit_ai.models import GraphContextData, HybridContextData

    graph_context = GraphContextData(
        risk_level="HIGH",
        impact_score=0.85,
        affected_files_count=5,
        directly_affected=["src/core.py", "src/utils.py"],
        transitively_affected=["src/main.py", "tests/test_core.py"],
        critical_files=[{"file": "src/core.py", "importance": 0.9}],
        component_breakdown={"core": 3, "utils": 2},
        recommendations=["Add more tests for core functionality"],
        dependency_info={"src/core.py": {"imports": ["src/utils.py"]}}
    )

    hybrid_context = HybridContextData(
        graph_context=graph_context,
        deepwiki_context=None,
        context_sources=["graph"]
    )

    return ContextData(
        repo_structure="Repository: test-repo\nOwner: test-owner",
        code_changes="File: src/core.py\nLanguage: python\nContent: def critical_function(): pass",
        historical_data="No historical data available",
        static_analysis_results=[],
        hybrid_context=hybrid_context,
        repository_name="test-repo",
        project_root="/tmp/test-repo"
    )


def test_context_data_with_hybrid_context(sample_context_data_with_hybrid):
    """Test that ContextData properly stores hybrid context."""
    assert sample_context_data_with_hybrid.hybrid_context is not None
    assert sample_context_data_with_hybrid.hybrid_context.graph_context.risk_level == "HIGH"
    assert sample_context_data_with_hybrid.hybrid_context.graph_context.impact_score == 0.85
    assert "graph" in sample_context_data_with_hybrid.hybrid_context.context_sources
    assert sample_context_data_with_hybrid.project_root == "/tmp/test-repo"
    assert sample_context_data_with_hybrid.repository_name == "test-repo"


def test_review_agent_uses_graph_risk_in_complexity():
    """Test that ReviewAgent factors in graph-based risk for complexity calculation."""
    agent = ReviewAgent()

    code = """
    def function():
        if condition:
            for item in items:
                process(item)
    """

    # Mock context response without graph risk
    mock_context_no_graph = Mock()
    mock_context_no_graph.metadata = {"risk_assessment": {"complexity": "medium"}}

    # Mock context response with HIGH graph risk
    mock_context_with_graph = Mock()
    mock_context_with_graph.metadata = {
        "risk_assessment": {"complexity": "medium"},
        "graph_risk_level": "HIGH"
    }

    complexity_no_graph = agent._calculate_enhanced_complexity(code, mock_context_no_graph)
    complexity_with_graph = agent._calculate_enhanced_complexity(code, mock_context_with_graph)

    # Complexity should be higher when graph risk is HIGH
    assert complexity_with_graph > complexity_no_graph
    assert 0 <= complexity_no_graph <= 1
    assert 0 <= complexity_with_graph <= 1


@patch('dspy.ChainOfThought')
def test_context_engineering_preserves_hybrid_metadata(mock_cot, sample_context_data_with_hybrid):
    """Test that ContextEngineeringAgent preserves hybrid context metadata in response."""
    # Mock DSPy response
    mock_result = Mock()
    mock_result.enriched_context = "Base enriched context"
    mock_result.code_relationships = "Code relationships"
    mock_result.relevant_patterns = "Relevant patterns"

    mock_generator = Mock(return_value=mock_result)
    mock_cot.return_value = mock_generator

    agent = ContextEngineeringAgent()

    # Mock the enrichment to preserve the existing hybrid context
    from coderabbit_ai.integrations.context_adapter import ContextAdapter
    original_enrich = agent._enrich_with_hybrid_context

    def mock_enrich(context_data):
        # Just format the existing hybrid context instead of rebuilding
        if context_data.hybrid_context:
            return ContextAdapter.format_hybrid_context_for_llm(context_data.hybrid_context)
        return ""

    agent._enrich_with_hybrid_context = mock_enrich
    response = agent.forward(sample_context_data_with_hybrid)

    # Check that hybrid metadata is preserved
    assert response.metadata is not None
    assert response.metadata.get("hybrid_context_enabled") == True
    assert "graph" in response.metadata.get("context_sources", [])
    assert response.metadata.get("graph_risk_level") == "HIGH"