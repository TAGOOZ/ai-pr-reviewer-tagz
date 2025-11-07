"""Tests for DeepWiki integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

from coderabbit_ai.integrations.deepwiki_client import (
    DeepWikiClient,
    DeepWikiContext
)
from coderabbit_ai.integrations.hybrid_context_provider import (
    HybridContextProvider,
    HybridContext
)


class TestDeepWikiClient:
    """Test DeepWiki MCP client."""

    @pytest.fixture
    def client(self):
        """Create DeepWiki client for testing."""
        return DeepWikiClient(
            mcp_url="https://test.deepwiki.com/mcp",
            timeout=10,
            cache_ttl=60
        )

    def test_client_initialization(self, client):
        """Test client initializes correctly."""
        assert client.mcp_url == "https://test.deepwiki.com/mcp"
        assert client.timeout == 10
        assert client.cache_ttl == 60
        assert client._cache == {}

    @patch('requests.Session.post')
    def test_is_repo_indexed_success(self, mock_post, client):
        """Test checking if repo is indexed."""
        # Mock successful structure response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "structure": {
                "sections": ["Overview", "Architecture"],
                "pages": ["intro", "components"]
            }
        }
        mock_post.return_value = mock_response

        result = client.is_repo_indexed("facebook/react")

        assert result is True
        assert mock_post.called

    @patch('requests.Session.post')
    def test_is_repo_indexed_not_found(self, mock_post, client):
        """Test repo not indexed."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response

        result = client.is_repo_indexed("unknown/repo")

        assert result is False

    @patch('requests.Session.post')
    def test_ask_question_success(self, mock_post, client):
        """Test asking question successfully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "React uses a virtual DOM for efficient updates."
        }
        mock_post.return_value = mock_response

        answer = client.ask_question(
            "facebook/react",
            "What is the virtual DOM?"
        )

        assert answer == "React uses a virtual DOM for efficient updates."
        assert mock_post.called

        # Check request payload
        call_args = mock_post.call_args
        assert call_args[1]['json']['repository'] == "facebook/react"
        assert "virtual DOM" in call_args[1]['json']['question']

    @patch('requests.Session.post')
    def test_ask_question_uses_cache(self, mock_post, client):
        """Test caching of question answers."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"answer": "Cached answer"}
        mock_post.return_value = mock_response

        # First call - should hit API
        answer1 = client.ask_question("facebook/react", "Test question")
        assert mock_post.call_count == 1

        # Second call - should use cache
        answer2 = client.ask_question("facebook/react", "Test question")
        assert mock_post.call_count == 1  # No additional call
        assert answer1 == answer2

    @patch('requests.Session.post')
    def test_ask_question_timeout(self, mock_post, client):
        """Test question timeout handling."""
        mock_post.side_effect = requests.exceptions.Timeout()

        answer = client.ask_question("facebook/react", "Test question")

        assert answer is None

    @patch('requests.Session.post')
    def test_read_wiki_structure(self, mock_post, client):
        """Test reading wiki structure."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "structure": {
                "sections": ["Getting Started", "API Reference"],
                "pages": ["intro", "hooks", "components"]
            }
        }
        mock_post.return_value = mock_response

        structure = client.read_wiki_structure("facebook/react")

        assert structure is not None
        assert "sections" in structure
        assert "pages" in structure
        assert len(structure["sections"]) == 2

    @patch('requests.Session.post')
    def test_read_wiki_contents(self, mock_post, client):
        """Test reading wiki page contents."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": "# React Hooks\n\nHooks are a new feature..."
        }
        mock_post.return_value = mock_response

        content = client.read_wiki_contents("facebook/react", "hooks")

        assert content is not None
        assert "React Hooks" in content
        assert "new feature" in content

    @patch('requests.Session.post')
    def test_get_component_relationships(self, mock_post, client):
        """Test getting component relationships."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "ReactDOM depends on the reconciler and scheduler."
        }
        mock_post.return_value = mock_response

        rels = client.get_component_relationships(
            "facebook/react",
            "packages/react-dom/src/client/ReactDOM.js"
        )

        assert rels is not None
        assert "file_path" in rels
        assert "raw_answer" in rels
        assert "reconciler" in rels["raw_answer"]

    @patch('requests.Session.post')
    def test_enrich_pr_context(self, mock_post, client):
        """Test enriching PR context."""
        # Mock multiple API calls
        mock_responses = [
            # architectural_overview
            Mock(
                status_code=200,
                json=Mock(return_value={
                    "answer": "React is a component-based library..."
                })
            ),
            # component_relationships for file 1
            Mock(
                status_code=200,
                json=Mock(return_value={
                    "answer": "This file handles rendering..."
                })
            ),
            # patterns_and_conventions
            Mock(
                status_code=200,
                json=Mock(return_value={
                    "answer": "React uses functional components..."
                })
            ),
            # wiki_structure
            Mock(
                status_code=200,
                json=Mock(return_value={
                    "structure": {"pages": ["intro", "hooks"]}
                })
            ),
        ]
        mock_post.side_effect = mock_responses

        context = client.enrich_pr_context(
            "facebook/react",
            ["src/React.js"],
            "Add new hook API"
        )

        assert isinstance(context, DeepWikiContext)
        assert context.repo == "facebook/react"
        assert context.architectural_overview is not None
        assert len(context.component_relationships) > 0
        assert len(context.patterns_and_conventions) > 0

    def test_format_for_llm(self, client):
        """Test formatting context for LLM."""
        context = DeepWikiContext(
            repo="facebook/react",
            architectural_overview="React is component-based",
            component_relationships={
                "src/React.js": {
                    "raw_answer": "Core React exports"
                }
            },
            relevant_documentation=["intro", "hooks"],
            patterns_and_conventions=["Use functional components"],
            timestamp=datetime.now()
        )

        formatted = client.format_for_llm(context)

        assert "## DeepWiki Semantic Context" in formatted
        assert "facebook/react" in formatted
        assert "React is component-based" in formatted
        assert "src/React.js" in formatted

    def test_cache_stats(self, client):
        """Test cache statistics."""
        # Add some cached items
        client._set_cached("key1", "value1")
        client._set_cached("key2", "value2")

        stats = client.get_cache_stats()

        assert stats["total_items"] == 2
        assert stats["fresh_items"] == 2
        assert stats["expired_items"] == 0

    def test_clear_cache(self, client):
        """Test clearing cache."""
        client._set_cached("key1", "value1")
        assert len(client._cache) == 1

        client.clear_cache()

        assert len(client._cache) == 0


class TestHybridContextProvider:
    """Test hybrid context provider."""

    @pytest.fixture
    def temp_project_root(self, tmp_path):
        """Create temporary project structure."""
        # Create minimal Python project
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "module_a.py").write_text(
            "import module_b\n\ndef function_a():\n    pass"
        )
        (src_dir / "module_b.py").write_text(
            "def function_b():\n    pass"
        )

        return str(tmp_path)

    @pytest.fixture
    def provider(self, temp_project_root):
        """Create hybrid context provider for testing."""
        return HybridContextProvider(
            project_root=temp_project_root,
            repo_name="test/repo",
            enable_deepwiki=False,  # Disable for basic tests
            cache_ttl=60
        )

    def test_provider_initialization(self, provider):
        """Test provider initializes correctly."""
        assert provider.project_root is not None
        assert provider.repo_name == "test/repo"
        assert provider.graph_provider is not None

    def test_enrich_pr_context_graph_only(self, provider):
        """Test enriching context with graph only (no DeepWiki)."""
        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        assert isinstance(context, HybridContext)
        assert context.graph_context is not None
        assert context.deepwiki_context is None
        assert context.deepwiki_available is False
        assert "graph" in context.get_context_sources()

    @patch.object(DeepWikiClient, 'is_repo_indexed')
    @patch.object(DeepWikiClient, 'enrich_pr_context')
    def test_enrich_pr_context_with_deepwiki(
        self,
        mock_enrich,
        mock_is_indexed,
        temp_project_root
    ):
        """Test enriching context with DeepWiki."""
        # Setup mocks
        mock_is_indexed.return_value = True
        mock_enrich.return_value = DeepWikiContext(
            repo="test/repo",
            architectural_overview="Test architecture",
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )

        # Create provider with DeepWiki enabled
        provider = HybridContextProvider(
            project_root=temp_project_root,
            repo_name="test/repo",
            enable_deepwiki=True,
            cache_ttl=60
        )

        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        assert context.deepwiki_context is not None
        assert context.deepwiki_available is True
        assert "deepwiki" in context.get_context_sources()

    def test_format_for_llm(self, provider):
        """Test formatting hybrid context for LLM."""
        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        formatted = provider.format_for_llm(context)

        assert "# Context for PR Review" in formatted
        assert "test/repo" in formatted
        assert "Dependency & Impact Analysis" in formatted

    def test_get_risk_summary(self, provider):
        """Test extracting risk summary."""
        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        summary = provider.get_risk_summary(context)

        assert "risk_level" in summary
        assert "impact_score" in summary
        assert "affected_files" in summary
        assert "context_sources" in summary

    def test_should_flag_for_review(self, provider):
        """Test review flagging logic."""
        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        # Small change should not be flagged
        flagged = provider.should_flag_for_review(context, threshold='high')

        assert isinstance(flagged, bool)

    def test_get_recommendations(self, provider):
        """Test getting recommendations."""
        context = provider.enrich_pr_context(
            changed_files=["src/module_a.py"]
        )

        recommendations = provider.get_recommendations(context)

        assert isinstance(recommendations, list)

    def test_clear_all_caches(self, provider):
        """Test clearing all caches."""
        # Trigger graph build
        provider.enrich_pr_context(changed_files=["src/module_a.py"])

        # Clear caches
        provider.clear_all_caches()

        # Graph cache should be cleared
        assert provider.graph_provider._graph_cache is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
