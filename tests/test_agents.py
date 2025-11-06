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
    
    assert "pylint: 2 issues found" in formatted
    assert "error: Syntax error" in formatted
    assert "warning: Unused variable" in formatted


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
    
    simple_complexity = agent._calculate_complexity(simple_code)
    complex_complexity = agent._calculate_complexity(complex_code)
    
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
    assert "vulnerability" in security_context.lower()
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
    assert len(context) > 0
    assert specialization in context.lower() or specialization.replace("_", " ") in context.lower()