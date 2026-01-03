"""Unit tests for hybrid_context_provider.py."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Optional

from coderabbit_ai.integrations.hybrid_context_provider import (
    HybridContext,
    HybridContextProvider,
    get_hybrid_context_provider
)
from coderabbit_ai.integrations.deepwiki_client import DeepWikiContext


class TestHybridContext:
    """Test HybridContext dataclass."""

    def test_get_context_sources_graph_only(self):
        """Test getting context sources with only graph layer."""
        ctx = HybridContext(
            graph_context={'impact_analysis': {'risk_level': 'LOW', 'impact_score': 0.0, 'affected_files_count': 0, 'critical_files': [], 'component_breakdown': {}}},
            deepwiki_context=None,
            deepwiki_available=False,
            on_demand_context=None,
            repo='test/repo',
            changed_files=['src/api.py'],
            timestamp=datetime.now()
        )

        sources = ctx.get_context_sources()
        assert sources == ['graph']

    def test_get_context_sources_graph_and_deepwiki(self):
        """Test getting context sources with graph and deepwiki."""
        dw_ctx = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )

        ctx = HybridContext(
            graph_context={'impact_analysis': {'risk_level': 'LOW', 'impact_score': 0.0, 'affected_files_count': 0, 'critical_files': [], 'component_breakdown': {}}},
            deepwiki_context=dw_ctx,
            deepwiki_available=True,
            on_demand_context=None,
            repo='test/repo',
            changed_files=[],
            timestamp=datetime.now()
        )

        sources = ctx.get_context_sources()
        assert 'graph' in sources
        assert 'deepwiki' in sources
        assert len(sources) == 2

    def test_get_context_sources_all_layers(self):
        """Test getting context sources with all layers."""
        dw_ctx = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )

        ctx = HybridContext(
            graph_context={'impact_analysis': {'risk_level': 'LOW', 'impact_score': 0.0, 'affected_files_count': 0, 'critical_files': [], 'component_breakdown': {}}},
            deepwiki_context=dw_ctx,
            deepwiki_available=True,
            on_demand_context={'generated': 'content'},
            repo='test/repo',
            changed_files=[],
            timestamp=datetime.now()
        )

        sources = ctx.get_context_sources()
        assert 'graph' in sources
        assert 'deepwiki' in sources
        assert 'on_demand' in sources
        assert len(sources) == 3


class TestHybridContextProviderInit:
    """Test HybridContextProvider initialization."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_init_with_deepwiki_enabled(self, mock_graph_provider):
        """Test initialization with DeepWiki enabled."""
        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        assert provider.project_root == '/test'
        assert provider.repo_name == 'test/repo'
        assert provider.enable_deepwiki == True
        assert provider.enable_on_demand == False
        assert provider.graph_provider is not None

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_init_deepwiki_disabled(self, mock_graph_provider):
        """Test initialization with DeepWiki disabled."""
        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=False
        )

        assert provider.enable_deepwiki == False
        assert provider.deepwiki_client is None

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_init_custom_cache_ttl(self, mock_graph_provider):
        """Test initialization with custom cache TTL."""
        provider = HybridContextProvider(
            project_root='/test',
            cache_ttl=7200
        )

        assert provider.cache_ttl == 7200


class TestEnrichPrContext:
    """Test enrich_pr_context method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_enrich_with_graph_only(self, mock_graph_provider_class):
        """Test enriching PR context with only graph layer."""
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'MEDIUM',
                'impact_score': 0.5,
                'affected_files_count': 5,
                'critical_files': [],
                'component_breakdown': {}
            },
            'recommendations': []
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            repo_name=None,
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(
            changed_files=['src/api.py'],
            pr_description='Test PR'
        )

        assert context.repo == 'local'
        assert context.changed_files == ['src/api.py']
        assert context.deepwiki_available == False
        assert context.deepwiki_context is None
        assert context.on_demand_context is None
        assert 'impact_analysis' in context.graph_context

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_enrich_with_graph_and_deepwiki(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test enriching PR context with graph and DeepWiki."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'HIGH',
                'impact_score': 0.75,
                'affected_files_count': 10,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki client
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = True
        mock_deepwiki_client.enrich_pr_context.return_value = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test architecture',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        context = provider.enrich_pr_context(
            changed_files=['src/api.py', 'src/core.py']
        )

        assert context.repo == 'test/repo'
        assert context.deepwiki_available == True
        assert context.deepwiki_context is not None
        assert context.deepwiki_context.architectural_overview == 'Test architecture'

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_enrich_deepwiki_not_indexed(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test enriching when repo is not indexed in DeepWiki."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'LOW',
                'impact_score': 0.2,
                'affected_files_count': 3,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki client
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        context = provider.enrich_pr_context(
            changed_files=['src/api.py']
        )

        assert context.deepwiki_available == False
        assert context.deepwiki_context is None

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_enrich_deepwiki_error(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test handling DeepWiki enrichment errors."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'MEDIUM',
                'impact_score': 0.5,
                'affected_files_count': 5,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki client
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = True
        mock_deepwiki_client.enrich_pr_context.side_effect = Exception("API error")
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        context = provider.enrich_pr_context(
            changed_files=['src/api.py']
        )

        # Should still return context, just without DeepWiki
        assert context.deepwiki_available == True
        assert context.deepwiki_context is None


class TestFormatForLLM:
    """Test format_for_llm method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_format_graph_only(self, mock_graph_provider_class):
        """Test formatting context with only graph layer."""
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'LOW',
                'impact_score': 0.2,
                'affected_files_count': 3,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider.format_for_llm.return_value = "Graph context content"
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/api.py'])
        formatted = provider.format_for_llm(context)

        assert '# Context for PR Review' in formatted
        assert '**Repository**: test/repo' in formatted
        assert '**Context Sources**: graph' in formatted
        assert 'Graph context content' in formatted

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_format_graph_and_deepwiki(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test formatting context with graph and DeepWiki."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'MEDIUM',
                'impact_score': 0.5,
                'affected_files_count': 5,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider.format_for_llm.return_value = "Graph content"
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki client
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = True
        mock_deepwiki_client.enrich_pr_context.return_value = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=[],
            timestamp=datetime.now()
        )
        mock_deepwiki_client.format_for_llm.return_value = "DeepWiki content"
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        context = provider.enrich_pr_context(['src/api.py'])
        formatted = provider.format_for_llm(context)

        assert '# Context for PR Review' in formatted
        assert '**Context Sources**: graph, deepwiki' in formatted
        assert 'Graph content' in formatted
        assert 'DeepWiki content' in formatted


class TestGetRiskSummary:
    """Test get_risk_summary method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_get_risk_summary(self, mock_graph_provider_class):
        """Test extracting risk summary."""
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'HIGH',
                'impact_score': 0.75,
                'affected_files_count': 10,
                'critical_files': [
                    {'file': 'src/core.py', 'direct_dependents': 5}
                ]
            },
            'recommendations': []
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/api.py'])
        summary = provider.get_risk_summary(context)

        assert summary['risk_level'] == 'HIGH'
        assert summary['impact_score'] == 0.75
        assert summary['affected_files'] == 10
        assert summary['critical_files'] == 1
        assert summary['has_semantic_context'] == False
        assert 'graph' in summary['context_sources']


class TestShouldFlagForReview:
    """Test should_flag_for_review method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_should_flag(self, mock_graph_provider_class):
        """Test flagging PR for review."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'HIGH',
                'impact_score': 0.8,
                'affected_files_count': 15,
                'critical_files': [],
                'component_breakdown': {}
            }
        }

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.should_flag_for_review.return_value = True
        mock_graph_provider.get_analyzer.return_value = mock_analyzer

        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/core.py'])
        should_flag = provider.should_flag_for_review(context, threshold='high')

        assert should_flag == True
        mock_analyzer.should_flag_for_review.assert_called_once_with(
            ['src/core.py'],
            'high'
        )

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_should_not_flag(self, mock_graph_provider_class):
        """Test not flagging PR for review."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'LOW',
                'impact_score': 0.2,
                'affected_files_count': 3,
                'critical_files': [],
                'component_breakdown': {}
            }
        }

        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.should_flag_for_review.return_value = False
        mock_graph_provider.get_analyzer.return_value = mock_analyzer

        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/api.py'])
        should_flag = provider.should_flag_for_review(context, threshold='critical')

        assert should_flag == False


class TestGetRecommendations:
    """Test get_recommendations method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_get_graph_recommendations(self, mock_graph_provider_class):
        """Test getting recommendations from graph layer."""
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'MEDIUM',
                'impact_score': 0.5,
                'affected_files_count': 5,
                'critical_files': [],
                'component_breakdown': {}
            },
            'recommendations': ['Add tests', 'Update documentation']
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/api.py'])
        recommendations = provider.get_recommendations(context)

        assert len(recommendations) == 2
        assert 'Add tests' in recommendations
        assert 'Update documentation' in recommendations

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_get_graph_and_deepwiki_recommendations(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test getting recommendations from graph and DeepWiki layers."""
        # Mock graph provider
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'HIGH',
                'impact_score': 0.75,
                'affected_files_count': 10,
                'critical_files': [],
                'component_breakdown': {}
            },
            'recommendations': ['Add tests']
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki client
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = True
        mock_deepwiki_client.enrich_pr_context.return_value = DeepWikiContext(
            repo='test/repo',
            architectural_overview='Test',
            component_relationships={},
            relevant_documentation=[],
            patterns_and_conventions=['Use type hints', 'PEP 8'],
            timestamp=datetime.now()
        )
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        context = provider.enrich_pr_context(['src/api.py'])
        recommendations = provider.get_recommendations(context)

        assert len(recommendations) == 2
        assert 'Add tests' in recommendations
        assert 'DeepWiki' in recommendations[1]

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_get_no_recommendations(self, mock_graph_provider_class):
        """Test getting recommendations when none available."""
        mock_graph_provider = Mock()
        mock_graph_provider.enrich_pr_context.return_value = {
            'impact_analysis': {
                'risk_level': 'LOW',
                'impact_score': 0.1,
                'affected_files_count': 2,
                'critical_files': [],
                'component_breakdown': {}
            }
        }
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        context = provider.enrich_pr_context(['src/api.py'])
        recommendations = provider.get_recommendations(context)

        assert len(recommendations) == 0


class TestGetEnabledLayers:
    """Test _get_enabled_layers method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_enabled_layers_graph_only(self, mock_graph_provider_class):
        """Test enabled layers with only graph."""
        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False,
            enable_on_demand=False
        )

        layers = provider._get_enabled_layers()
        assert layers == "Layer 1 (Graph)"

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_enabled_layers_graph_and_deepwiki(self, mock_graph_provider_class):
        """Test enabled layers with graph and DeepWiki."""
        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True,
            enable_on_demand=False
        )

        layers = provider._get_enabled_layers()
        assert "Layer 1 (Graph)" in layers
        assert "Layer 2 (DeepWiki)" in layers

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_enabled_layers_all(self, mock_graph_provider_class):
        """Test enabled layers with all layers."""
        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True,
            enable_on_demand=True
        )

        layers = provider._get_enabled_layers()
        assert "Layer 1 (Graph)" in layers
        assert "Layer 2 (DeepWiki)" in layers
        assert "Layer 3 (On-Demand)" in layers


class TestGetCacheStats:
    """Test get_cache_stats method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_cache_stats_without_deepwiki(self, mock_graph_provider_class):
        """Test cache stats without DeepWiki."""
        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        stats = provider.get_cache_stats()
        assert 'graph' in stats
        assert 'deepwiki' not in stats

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_cache_stats_with_deepwiki(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test cache stats with DeepWiki."""
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.get_cache_stats.return_value = {'hits': 10, 'misses': 2}
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True
        )

        stats = provider.get_cache_stats()
        assert 'graph' in stats
        assert 'deepwiki' in stats
        assert stats['deepwiki'] == {'hits': 10, 'misses': 2}


class TestClearAllCaches:
    """Test clear_all_caches method."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_clear_caches_without_deepwiki(self, mock_graph_provider_class):
        """Test clearing caches without DeepWiki."""
        mock_graph_provider = Mock()
        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        provider.clear_all_caches()

        assert mock_graph_provider._graph_cache is None
        assert mock_graph_provider._analyzer_cache is None

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    def test_clear_caches_with_deepwiki(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test clearing caches with DeepWiki."""
        mock_graph_provider = Mock()
        mock_graph_provider_class.return_value = mock_graph_provider

        mock_deepwiki_client = Mock()
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True
        )

        provider.clear_all_caches()

        assert mock_graph_provider._graph_cache is None
        assert mock_graph_provider._analyzer_cache is None
        mock_deepwiki_client.clear_cache.assert_called_once()


class TestGetHybridContextProvider:
    """Test get_hybrid_context_provider singleton function."""

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_singleton_creation(self, mock_graph_provider_class):
        """Test creating singleton instance."""
        provider1 = get_hybrid_context_provider('/test', 'test/repo')
        provider2 = get_hybrid_context_provider('/test', 'test/repo')

        assert provider1 is provider2

    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    def test_singleton_with_kwargs(self, mock_graph_provider_class):
        """Test singleton with additional kwargs."""
        provider = get_hybrid_context_provider(
            '/test',
            'test/repo',
            enable_deepwiki=True,
            cache_ttl=7200
        )

        assert provider.enable_deepwiki == True
        assert provider.cache_ttl == 7200
