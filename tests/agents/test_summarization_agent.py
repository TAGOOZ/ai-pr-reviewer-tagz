"""Unit tests for Summarization Agent."""

import pytest
from unittest.mock import Mock, patch
from dspy import Retriever

from coderabbit_ai.agents.summarization_agent import SummarizationAgent


@pytest.fixture
def summarization_agent():
    """Create a SummarizationAgent instance for testing."""
    agent = SummarizationAgent()
    return agent


class TestSummarizationAgentInitialization:
    """Test suite for SummarizationAgent initialization."""

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_initialization_with_dspy_chain(self, mock_chain):
        """Test initialization with DSPy ChainOfThought."""
        mock_chain.return_value = Mock()
        
        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

            agent = SummarizationAgent()
            assert agent.summarize is not None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True)
    def test_initialization_with_openai_key(self):
        """Test initialization with OpenAI key."""
        agent = SummarizationAgent()
        assert agent.summarize is not None

    @patch.dict(os.environ, {}, clear=True)
    def test_initialization_without_keys(self):
        """Test initialization without API keys."""
        agent = SummarizationAgent()
        assert agent.summarize is not None


class TestForward:
    """Test suite for SummarizationAgent.forward() method."""

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_basic_summary(self, mock_chain):
        """Test forward method with basic summary."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        result = agent.forward(
            pr_title="Test PR",
            pr_description="This is a test PR",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=[],
            diff_stats={"additions": 10, "deletions": 5}
        )

        assert result is not None
        assert isinstance(result, dict)
        assert "high_level_summary" in result
        assert "technical_walkthrough" in result
        assert "risk_level" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_with_file_changes(self, mock_chain):
        """Test forward method with file changes."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        file_changes = [
            {
                "filename": "test.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "changes": "Added test function",
                "patch": "diff --git a b"
            }
        ]

        result = agent.forward(
            pr_title="Test PR with changes",
            pr_description="Test PR with file changes",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=file_changes,
            diff_stats={"additions": 10, "deletions": 5}
        )

        assert result is not None
        assert "file_changes_summary" in result
        assert "change_categories" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_with_linked_issues(self, mock_chain):
        """Test forward method with linked issues."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        linked_issues = [
            "Issue #1: Bug in test function",
            "Issue #2: Vulnerability in dependency"
            "Issue #3: Performance issue"
        ]

        result = agent.forward(
            pr_title="Test PR with issues",
            pr_description="Test PR with security vulnerabilities",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            linked_issues=linked_issues,
            files_changed=[]
        )

        assert result is not None
        assert "affected_components" in result
        assert "security_findings" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_with_static_analysis(self, mock_chain):
        """Test forward method with static analysis results."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        static_analysis = {
            "linting_issues": 5,
            "security_issues": 2,
            "complexity_metrics": {"cyclomatic_complexity": 15}
        }

        result = agent.forward(
            pr_title="Test PR with analysis",
            pr_description="Test PR with static analysis",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=[],
            static_analysis=static_analysis
        )

        assert result is not None
        assert "static_analysis_summary" in result
        assert "code_quality_issues" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_with_historical_context(self, mock_chain):
        """Test forward method with historical context."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        historical_prs = [
            {"number": 42, "title": "Related PR #42", "summary": "Fixed similar bug"},
            {"number": 123, "title": "Related PR #123", "summary": "Performance improvement"}
        ]

        result = agent.forward(
            pr_title="Test PR with context",
            pr_description="Test PR with historical context",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=[],
            historical_prs=historical_prs
        )

        assert result is not None
        assert "historical_context" in result
        assert "related_prs" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_forward_success(self, mock_chain):
        """Test successful summary generation."""
        mock_chain.return_value = Mock()

        with patch('coderabbit_ai.agents.summarization_agent.dspy.Retriver'):
            mock_retriever = Mock()
            mock_retriever.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
            agent.retriever = mock_retriever

        # Mock successful DSPy invocation
        mock_predict = Mock()
        mock_predict.return_value = "Successfully generated summary"

        mock_chain.return_value.__enter__ = Mock()
        mock_chain.return_value.__exit__ = Mock(return_value=mock_predict)

        result = agent.forward(
            pr_title="Test PR",
            pr_description="Test PR for summarization",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=[]
        )

        assert result is not None
        assert isinstance(result, dict)
        assert "summary" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    @patch('coderabbit_ai.agents.summarization_agent.dspy.Retriever')
    def test_forward_missing_openai_key(self, mock_chain):
        """Test forward without OpenAI key."""
        mock_chain.return_value = Mock()

        with patch.dict(os.environ, {}, clear=True):
            agent = SummarizationAgent()
            agent.summarize = mock_chain
            agent.retriever = Mock()

        result = agent.forward(
            pr_title="Test PR",
            pr_description="Test PR",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            files_changed=[]
        )

        # Should handle missing API key gracefully
        assert result is not None


class TestHelperMethods:
    """Test suite for helper methods."""

    @patch('coderabbit_ai.agents.summarization_agent.SummarizationAgent.dspy')
    def test_build_pr_metadata_basic(self, mock_chain):
        """Test basic PR metadata building."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        metadata = agent._build_pr_metadata(
            pr_title="Test PR",
            pr_description="Test PR description",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature"
        )

        assert isinstance(metadata, str)
        assert "Test PR" in metadata
        assert "test-user" in metadata
        assert "main" in metadata

    @patch('coderabbit_ai.agents.summarization_agent.SummarizationAgent.dspy')
    def test_build_pr_metadata_with_issues(self, mock_chain):
        """Test PR metadata with linked issues."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        linked_issues = ["Issue #1", "Issue #2", "Issue #3"]

        metadata = agent._build_pr_metadata(
            pr_title="Test PR with issues",
            pr_description="Test PR description",
            pr_author="test-user",
            base_branch="main",
            head_branch="feature",
            linked_issues=linked_issues
        )

        assert isinstance(metadata, str)
        assert "Test PR with issues" in metadata

    @patch('coderabbit_ai.agents.summarization_agent.SummarizationAgent.dspy')
    def test_build_file_changes_summary_empty(self, mock_chain):
        """Test file changes summary with empty list."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        result = agent._build_file_changes_summary([])

        assert result is not None
        assert isinstance(result, str)
        assert "No files changed" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_build_file_changes_summary_with_changes(self, mock_chain):
        """Test file changes summary with changes."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        file_changes = [
            {"filename": "test_file.py", "status": "modified", "additions": 5, "deletions": 2}
        ]

        result = agent._build_file_changes_summary(file_changes)

        assert result is not None
        assert isinstance(result, str)
        assert "1 file modified, 5 additions, 2 deletions" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_build_diff_stats_basic(self, mock_chain):
        """Test basic diff stats."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain

        diff_stats = {"additions": 10, "deletions": 5}
        result = agent._build_diff_stats_string(diff_stats)

        assert isinstance(result, str)
        assert "10 additions, 5 deletions" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_build_diff_stats_empty(self, mock_chain):
        """Test diff stats with empty changes."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        result = agent._build_diff_stats_string({"additions": 0, "deletions": 0})

        assert isinstance(result, str)
        assert "No changes" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_build_static_analysis_summary(self, mock_chain):
        """Test static analysis summary building."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        static_analysis = {
            "linting_issues": 3,
            "security_issues": 1,
            "complexity_metrics": {"cyclomatic_complexity": 12}
        }

        result = agent._build_static_analysis_summary(static_analysis)

        assert result is not None
        assert isinstance(result, str)
        assert "3 linting issues, 1 security issue" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_build_historical_context_string_empty(self, mock_chain):
        """Test historical context with empty list."""
        mock_chain.return_value = Mock()

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        result = agent._build_historical_context_string([])

        assert isinstance(result, str)
        assert "No historical context available" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_parse_summary_result(self, mock_chain):
        """Test parsing DSPy summary result."""
        mock_chain.return_value = Mock()
        mock_chain.__enter__ = Mock()
        mock_chain.__exit__ = Mock(return_value=Mock(
            raw_output="Summary: Test PR\n\nHigh-level overview...",
            structured_output={...}
        ))

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        result = agent._parse_summary_result(Mock())

        assert result is not None
        assert isinstance(result, dict)
        assert "summary" in result
        assert "high_level_summary" in result


class TestErrorHandling:
    """Test suite for error handling in SummarizationAgent."""

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_missing_openai_key_graceful_handling(self, mock_chain):
        """Test graceful handling when OpenAI key missing."""
        mock_chain.return_value = Mock()

        with patch.dict(os.environ, {}, clear=True):
            agent = SummarizationAgent()
            agent.summarize = mock_chain
            agent.retriever = Mock()

        result = agent.forward(
                pr_title="Test PR",
                pr_description="Test PR",
                pr_author="test-user",
                base_branch="main",
                head_branch="feature",
                files_changed=[]
            )

        # Should not raise error, return a basic result
        assert result is not None
        assert "summary" in result

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_dspy_call_fails(self, mock_chain):
        """Test handling of DSPy API call failure."""
        mock_chain.return_value = Mock()
        mock_chain.__enter__ = Mock()
        mock_chain.__exit__ = Mock(side_effect=Exception("DSPy API error"))

        agent = SummarizationAgent()
        agent.summarize = mock_chain
        agent.retriever = Mock()

        with pytest.raises(Exception):
            agent.forward(
                pr_title="Test PR",
                pr_description="Test PR",
                pr_author="test-user",
                base_branch="main",
                head_branch="feature",
                files_changed=[]
            )

    @patch('coderabbit_ai.agents.summarization_agent.dspy.ChainOfThought')
    def test_empty_pr_description(self, mock_chain):
        """Test handling of empty PR description."""
        mock_chain.return_value = Mock()

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
            agent = SummarizationAgent()
            agent.summarize = mock_chain
            agent.retriever = Mock()

        result = agent.forward(
                pr_title="Test PR",
                pr_description="",
                pr_author="test-user",
                base_branch="main",
                head_branch="feature",
                files_changed=[]
            )

        # Should generate default description when empty
        assert result is not None
        assert "summary" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
