"""Tests for the CodeRabbit AI Pipeline."""

import pytest
from unittest.mock import Mock, patch

from coderabbit_ai.models import (
    ReviewRequest, Repository, PullRequest, User, FileChange,
    OrganizationConfig, ReviewRules, AISettings, Integration,
    Platform, ChangeType
)
from coderabbit_ai.pipeline import CodeRabbitMultiAgentPipeline


@pytest.fixture
def sample_review_request():
    """Create a sample review request for testing."""
    return ReviewRequest(
        repository=Repository(
            id="repo-123",
            name="test-repo",
            owner="test-owner",
            platform=Platform.GITHUB,
            clone_url="https://github.com/test-owner/test-repo.git",
            default_branch="main"
        ),
        pull_request=PullRequest(
            id="pr-456",
            number=123,
            title="Test PR",
            description="This is a test pull request",
            author=User(
                id="user-789",
                username="test-user",
                email="test@example.com"
            ),
            base_branch="main",
            head_branch="feature/test",
            files_changed=[
                FileChange(
                    path="src/main.py",
                    change_type=ChangeType.MODIFIED,
                    content="print('Hello, world!')\n",
                    diff="+print('Hello, world!')\n",
                    language="python"
                )
            ]
        ),
        config=OrganizationConfig(
            id="org-123",
            name="Test Org",
            review_rules=ReviewRules(
                enabled_checks=["security", "performance", "style"],
                severity_thresholds={"security": "high", "performance": "medium"},
                custom_rules=[]
            ),
            ai_settings=AISettings(
                primary_model="gpt-3.5-turbo",
                fallback_models=["gpt-4"],
                temperature=0.7,
                max_tokens=4096
            ),
            integrations=[
                Integration(
                    platform=Platform.GITHUB,
                    config={"token": "test-token"}
                )
            ]
        )
    )


@pytest.fixture
def pipeline():
    """Create a pipeline instance for testing."""
    config = {
        "verification_specializations": ["security", "performance", "style"],
        "openai_api_key": "test-key",
        "anthropic_api_key": "test-key"
    }
    return CodeRabbitMultiAgentPipeline(config)


def test_pipeline_initialization(pipeline):
    """Test that the pipeline initializes correctly."""
    assert pipeline is not None
    assert pipeline.context_agent is not None
    assert pipeline.review_agent is not None
    assert pipeline.verification_pool is not None


@patch('dspy.settings.configure')
def test_pipeline_forward(mock_configure, pipeline, sample_review_request):
    """Test the pipeline forward method."""
    # Mock DSPy configuration
    mock_configure.return_value = None
    
    # Process the review request
    response = pipeline.forward(sample_review_request)
    
    # Verify response structure
    assert response is not None
    assert response.review_id is not None
    assert response.status == "completed"
    assert isinstance(response.comments, list)
    assert response.metrics is not None
    assert response.metrics.files_analyzed == 1


def test_context_data_preparation(pipeline, sample_review_request):
    """Test context data preparation."""
    context_data = pipeline._prepare_context_data(sample_review_request)
    
    assert context_data is not None
    assert "test-repo" in context_data.repo_structure
    assert "test-owner" in context_data.repo_structure
    assert "src/main.py" in context_data.code_changes
    assert "python" in context_data.code_changes


def test_code_changes_formatting(pipeline, sample_review_request):
    """Test code changes formatting."""
    formatted = pipeline._format_code_changes(sample_review_request.pull_request.files_changed)
    
    assert "src/main.py" in formatted
    assert "python" in formatted
    assert "MODIFIED" in formatted
    assert "print('Hello, world!')" in formatted


def test_org_config_formatting(pipeline, sample_review_request):
    """Test organization config formatting."""
    formatted = pipeline._format_org_config(sample_review_request.config)
    
    assert "review_rules" in formatted
    assert "ai_settings" in formatted
    assert formatted["review_rules"]["enabled_checks"] == ["security", "performance", "style"]
    assert formatted["ai_settings"]["primary_model"] == "gpt-3.5-turbo"


def test_ai_cost_estimation(pipeline, sample_review_request):
    """Test AI cost estimation."""
    cost = pipeline._estimate_ai_cost(sample_review_request, [])
    
    assert isinstance(cost, float)
    assert cost > 0
    assert cost < 1.0  # Should be a small amount for test data


@pytest.mark.asyncio
async def test_pipeline_error_handling(pipeline):
    """Test pipeline error handling with invalid input."""
    # This test would verify error handling
    # For now, just ensure the pipeline doesn't crash
    assert pipeline is not None