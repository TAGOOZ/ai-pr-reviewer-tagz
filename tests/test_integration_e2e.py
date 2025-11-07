"""End-to-end integration tests for complete review pipeline with hybrid context."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from coderabbit_ai.models import (
    ContextData,
    GraphContextData,
    DeepWikiContextData,
    HybridContextData
)
from coderabbit_ai.agents import ContextEngineeringAgent, ReviewAgent
from coderabbit_ai.integrations.context_adapter import ContextAdapter


@pytest.fixture
def temp_python_project():
    """Create a temporary Python project for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)

        # Create src directory
        src_dir = project_root / "src"
        src_dir.mkdir()

        # Create Python files
        (src_dir / "auth.py").write_text("""
import hashlib
from database import User

def authenticate_user(email, password):
    user = User.get_by_email(email)
    if user and check_password(user, password):
        return user
    return None

def check_password(user, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    return user.password_hash == hashed
""")

        (src_dir / "database.py").write_text("""
class User:
    def __init__(self, email, password_hash):
        self.email = email
        self.password_hash = password_hash

    @classmethod
    def get_by_email(cls, email):
        # Simplified for testing
        return None
""")

        (src_dir / "api.py").write_text("""
from auth import authenticate_user

def login_endpoint(email, password):
    user = authenticate_user(email, password)
    if user:
        return {"status": "success", "user_id": user.email}
    return {"status": "error", "message": "Invalid credentials"}
""")

        yield str(project_root)


@pytest.fixture
def sample_context_data_with_project(temp_python_project):
    """Create context data with project root."""
    return ContextData(
        repo_structure="Repository: test-repo\nOwner: test-owner\nFiles: 3",
        code_changes="""
File: src/auth.py
Language: python
Content:
+++ b/src/auth.py
@@ -1,5 +1,8 @@
 import hashlib
+import secrets
 from database import User

 def authenticate_user(email, password):
+    # Added rate limiting
+    check_rate_limit(email)
     user = User.get_by_email(email)
""",
        historical_data="PR #123: Security improvements\nPR #124: Authentication fixes",
        static_analysis_results=[
            {
                "tool": "bandit",
                "issues": [
                    {
                        "severity": "medium",
                        "message": "Use of weak cryptographic hash",
                        "file": "src/auth.py"
                    }
                ]
            }
        ],
        project_root=temp_python_project,
        repository_name="test-org/test-repo"
    )


class TestEndToEndIntegration:
    """Test complete pipeline with hybrid context."""

    @patch('dspy.ChainOfThought')
    def test_context_engineering_with_graph_context(self, mock_cot, sample_context_data_with_project):
        """Test ContextEngineeringAgent enriches with graph context."""
        # Mock DSPy ChainOfThought
        mock_result = Mock()
        mock_result.enriched_context = "Security concerns detected in authentication flow"
        mock_result.code_relationships = "auth.py -> database.py -> api.py"
        mock_result.relevant_patterns = "Password hashing pattern detected"
        mock_result.risk_assessment = "medium"

        mock_generator = Mock(return_value=mock_result)
        mock_cot.return_value = mock_generator

        agent = ContextEngineeringAgent()
        response = agent.forward(sample_context_data_with_project)

        # Verify response
        assert response.agent_id == "context_engineering"
        assert response.confidence_score > 0.7

        # Verify hybrid context was enriched
        assert sample_context_data_with_project.hybrid_context is not None
        assert isinstance(sample_context_data_with_project.hybrid_context, HybridContextData)

        # Verify graph context
        graph_ctx = sample_context_data_with_project.hybrid_context.graph_context
        assert isinstance(graph_ctx, GraphContextData)
        assert graph_ctx.risk_level in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        assert 0.0 <= graph_ctx.impact_score <= 1.0

        # Verify context sources include graph
        assert 'graph' in sample_context_data_with_project.hybrid_context.context_sources

        # Verify metadata
        assert response.metadata['hybrid_context_enabled'] is True
        assert response.metadata['graph_risk_level'] in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

        # Verify enriched context includes graph analysis
        assert "Dependency Graph Analysis" in response.enriched_context or \
               "Multi-Layer Context" in response.enriched_context

    @patch('dspy.ChainOfThought')
    @patch('coderabbit_ai.integrations.deepwiki_client.DeepWikiClient.is_repo_indexed')
    @patch('coderabbit_ai.integrations.deepwiki_client.DeepWikiClient.enrich_pr_context')
    def test_context_engineering_with_deepwiki(
        self,
        mock_enrich,
        mock_is_indexed,
        mock_cot,
        sample_context_data_with_project
    ):
        """Test ContextEngineeringAgent enriches with DeepWiki when available."""
        # Setup mocks
        mock_is_indexed.return_value = True

        from datetime import datetime
        from coderabbit_ai.integrations.deepwiki_client import DeepWikiContext

        mock_enrich.return_value = DeepWikiContext(
            repo="test-org/test-repo",
            architectural_overview="Authentication module handles user verification",
            component_relationships={"src/auth.py": {"raw_answer": "Core authentication logic"}},
            relevant_documentation=["authentication", "security"],
            patterns_and_conventions=["Use bcrypt for password hashing"],
            timestamp=datetime.now()
        )

        # Mock DSPy result
        mock_result = Mock()
        mock_result.enriched_context = "Security review"
        mock_result.code_relationships = "Dependencies mapped"
        mock_result.relevant_patterns = "Security patterns"
        mock_result.risk_assessment = "medium"

        mock_generator = Mock(return_value=mock_result)
        mock_cot.return_value = mock_generator

        agent = ContextEngineeringAgent()
        response = agent.forward(sample_context_data_with_project)

        # Verify DeepWiki context
        hybrid_ctx = sample_context_data_with_project.hybrid_context
        assert hybrid_ctx is not None
        assert hybrid_ctx.deepwiki_context is not None
        assert hybrid_ctx.deepwiki_context.available is True
        assert 'deepwiki' in hybrid_ctx.context_sources

        # Verify metadata
        assert response.metadata['deepwiki_available'] is True

    @patch('dspy.ChainOfThought')
    def test_review_agent_uses_graph_complexity(self, mock_cot, sample_context_data_with_project):
        """Test ReviewAgent incorporates graph-based complexity."""
        # Mock DSPy for context agent
        mock_ctx_result = Mock()
        mock_ctx_result.enriched_context = "Context"
        mock_ctx_result.code_relationships = "Relationships"
        mock_ctx_result.relevant_patterns = "Patterns"
        mock_ctx_result.risk_assessment = "high"

        mock_ctx_gen = Mock(return_value=mock_ctx_result)
        mock_cot.return_value = mock_ctx_gen

        # Setup context engineering
        context_agent = ContextEngineeringAgent()
        context_response = context_agent.forward(sample_context_data_with_project)

        # Setup review agent with mock DSPy reviewer
        mock_review_result = Mock()
        mock_review_result.review_findings = "Security issues found"
        mock_review_result.confidence_scores = "security: 0.9"
        mock_review_result.suggested_improvements = "Use bcrypt"

        mock_reviewer_gen = Mock(return_value=mock_review_result)
        # Mock_cot is reused for reviewer too
        mock_cot.return_value = mock_reviewer_gen

        review_agent = ReviewAgent()

        org_config = {
            "ai_settings": {
                "quality_threshold": 0.8
            }
        }

        review_response = review_agent.forward(
            context_response,
            sample_context_data_with_project.code_changes,
            org_config
        )

        # Verify review response
        assert review_response.agent_id == "review_agent"
        assert review_response.confidence_score > 0

        # Verify hybrid context metadata is present
        assert review_response.metadata is not None
        if context_response.metadata.get('hybrid_context_enabled'):
            assert review_response.metadata.get('hybrid_context') is not None
            hybrid_meta = review_response.metadata['hybrid_context']
            assert 'graph_risk_level' in hybrid_meta
            assert 'context_sources' in hybrid_meta

    @patch('dspy.ChainOfThought')
    def test_full_pipeline_graph_only(self, mock_cot, sample_context_data_with_project):
        """Test complete pipeline with graph context only (no DeepWiki)."""
        # Mock for context agent
        mock_ctx_result = Mock()
        mock_ctx_result.enriched_context = "Enriched context"
        mock_ctx_result.code_relationships = "Code relationships"
        mock_ctx_result.relevant_patterns = "Patterns"
        mock_ctx_result.risk_assessment = "medium"
        mock_ctx_gen = Mock(return_value=mock_ctx_result)

        # Mock for review agent
        mock_review_result = Mock()
        mock_review_result.review_findings = "Issues found"
        mock_review_result.confidence_scores = "overall: 0.85"
        mock_review_result.suggested_improvements = "Improvements"
        mock_review_gen = Mock(return_value=mock_review_result)

        # Context Engineering
        mock_cot.return_value = mock_ctx_gen
        context_agent = ContextEngineeringAgent()
        context_response = context_agent.forward(sample_context_data_with_project)

        # Review
        mock_cot.return_value = mock_review_gen
        review_agent = ReviewAgent()
        review_response = review_agent.forward(
            context_response,
            sample_context_data_with_project.code_changes,
            {"ai_settings": {}}
        )

        # Verify end-to-end flow
        assert context_response is not None
        assert review_response is not None

        # Verify graph context was used
        assert sample_context_data_with_project.hybrid_context is not None
        assert 'graph' in sample_context_data_with_project.hybrid_context.context_sources

        # Verify metadata flow
        assert context_response.metadata['hybrid_context_enabled'] is True
        assert review_response.metadata['complexity_score'] >= 0

    def test_context_adapter_formatting(self, temp_python_project):
        """Test ContextAdapter properly formats hybrid context for LLM."""
        # Create mock hybrid context data
        graph_ctx = GraphContextData(
            risk_level="HIGH",
            impact_score=0.75,
            affected_files_count=10,
            directly_affected=["src/auth.py"],
            transitively_affected=["src/api.py", "src/database.py"],
            critical_files=[{"file": "src/auth.py", "direct_dependents": 5}],
            component_breakdown={"src": 8, "tests": 2},
            recommendations=["Extra review needed"],
            dependency_info={}
        )

        deepwiki_ctx = DeepWikiContextData(
            repo="test/repo",
            architectural_overview="Test architecture",
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=["Use type hints"],
            available=True
        )

        hybrid_ctx = HybridContextData(
            graph_context=graph_ctx,
            deepwiki_context=deepwiki_ctx,
            context_sources=['graph', 'deepwiki']
        )

        # Format for LLM
        formatted = ContextAdapter.format_hybrid_context_for_llm(hybrid_ctx)

        # Verify formatting
        assert "Multi-Layer Context Analysis" in formatted
        assert "graph, deepwiki" in formatted
        assert "HIGH" in formatted
        assert "75" in formatted  # Impact score
        assert "Test architecture" in formatted

    def test_context_quality_score(self):
        """Test context quality scoring."""
        # Graph only
        graph_only = HybridContextData(
            graph_context=GraphContextData(
                risk_level="LOW",
                impact_score=0.1,
                affected_files_count=2,
                directly_affected=[],
                transitively_affected=[],
                critical_files=[],
                component_breakdown={},
                recommendations=[]
            ),
            deepwiki_context=None,
            context_sources=['graph']
        )

        score_graph_only = ContextAdapter.get_context_quality_score(graph_only)
        assert 0.6 <= score_graph_only < 0.7

        # Graph + DeepWiki
        graph_deepwiki = HybridContextData(
            graph_context=GraphContextData(
                risk_level="MEDIUM",
                impact_score=0.3,
                affected_files_count=5,
                directly_affected=[],
                transitively_affected=[],
                critical_files=[],
                component_breakdown={},
                recommendations=[]
            ),
            deepwiki_context=DeepWikiContextData(
                repo="test/repo",
                architectural_overview="Overview",
                component_relationships={},
                relevant_documentation=[],
                patterns_and_conventions=["Pattern 1"],
                available=True
            ),
            context_sources=['graph', 'deepwiki']
        )

        score_hybrid = ContextAdapter.get_context_quality_score(graph_deepwiki)
        assert score_hybrid > score_graph_only
        assert score_hybrid >= 0.95  # Should have high score with rich context


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
