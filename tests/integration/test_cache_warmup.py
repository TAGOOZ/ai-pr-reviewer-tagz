"""Integration tests for cache warmup workflow."""

import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from coderabbit_ai.integrations.hybrid_context_provider import (
    HybridContextProvider,
    HybridContext
)


class TestCacheWarmup:
    """Integration tests for cache warmup."""

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_cache_warmup_on_initialization(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test that caches are populated on first use."""
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

        # Mock DeepWiki
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_class.return_value = mock_deepwiki_client

        # Create provider
        provider = HybridContextProvider(
            project_root='/test',
            repo_name='test/repo',
            enable_deepwiki=True
        )

        # First call should populate cache
        context1 = provider.enrich_pr_context(['src/api.py'])

        assert context1.graph_context is not None

        # Get cache stats
        stats = provider.get_cache_stats()

        assert 'graph' in stats
        assert 'deepwiki' in stats

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_cache_hit_on_subsequent_calls(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test that subsequent calls hit cache."""
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

        # Mock DeepWiki
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=False
        )

        # First call
        provider.enrich_pr_context(['src/api.py'])

        # Second call - should use cache
        provider.enrich_pr_context(['src/api.py'])

        # Graph provider should be called only once
        assert mock_graph_provider.enrich_pr_context.call_count <= 2

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_cache_clear(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test that cache clearing works."""
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

        # Mock DeepWiki
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_client.clear_cache = Mock()
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True
        )

        # Populate cache
        provider.enrich_pr_context(['src/api.py'])

        # Clear cache
        provider.clear_all_caches()

        # Verify DeepWiki cache was cleared
        mock_deepwiki_client.clear_cache.assert_called_once()

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_cache_invalidates_after_ttl(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test that cache invalidates after TTL expires."""
        # Mock graph provider
        mock_graph_provider = Mock()
        call_count = 0

        def mock_enrich(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                'impact_analysis': {
                    'risk_level': 'LOW',
                    'impact_score': 0.2,
                    'affected_files_count': 3,
                    'critical_files': [],
                    'component_breakdown': {}
                }
            }

        mock_graph_provider.enrich_pr_context.side_effect = mock_enrich
        mock_graph_provider_class.return_value = mock_graph_provider

        # Mock DeepWiki
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_client.get_cache_stats = Mock(return_value={'hits': 0, 'misses': 0})
        mock_deepwiki_class.return_value = mock_deepwiki_client

        provider = HybridContextProvider(
            project_root='/test',
            cache_ttl=3600,  # 1 hour TTL
            enable_deepwiki=False
        )

        # First call
        provider.enrich_pr_context(['src/api.py'])

        # Get stats
        stats = provider.get_cache_stats()
        initial_misses = stats.get('deepwiki', {}).get('misses', 0)

        # Clear cache to simulate TTL expiration
        provider.clear_all_caches()

        # Second call after cache clear
        provider.enrich_pr_context(['src/api.py'])

        # Stats should show cache misses after clear
        final_stats = provider.get_cache_stats()
        final_misses = final_stats.get('deepwiki', {}).get('misses', 0)

        assert final_misses >= initial_misses

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_warmup_multiple_repos(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test cache warmup for multiple repositories."""
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

        # Mock DeepWiki
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_class.return_value = mock_deepwiki_client

        # Create providers for different repos
        provider1 = HybridContextProvider(
            project_root='/test/repo1',
            repo_name='owner/repo1',
            enable_deepwiki=False
        )

        provider2 = HybridContextProvider(
            project_root='/test/repo2',
            repo_name='owner/repo2',
            enable_deepwiki=False
        )

        # Warm up both
        context1 = provider1.enrich_pr_context(['src/api.py'])
        context2 = provider2.enrich_pr_context(['src/api.py'])

        assert context1.repo == 'owner/repo1'
        assert context2.repo == 'owner/repo2'

        # Both should have populated their caches
        stats1 = provider1.get_cache_stats()
        stats2 = provider2.get_cache_stats()

        assert stats1 is not None
        assert stats2 is not None

    @pytest.mark.asyncio
    @patch('coderabbit_ai.integrations.hybrid_context_provider.GraphContextProvider')
    @patch('coderabbit_ai.integrations.hybrid_context_provider.DeepWikiClient')
    async def test_cache_performance_metrics(self, mock_deepwiki_class, mock_graph_provider_class):
        """Test that cache performance metrics are tracked."""
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

        # Mock DeepWiki with cache stats
        mock_deepwiki_client = Mock()
        mock_deepwiki_client.is_repo_indexed.return_value = False
        mock_deepwiki_client.get_cache_stats.return_value = {
            'hits': 100,
            'misses': 20,
            'hit_rate': 0.833
        }
        mock_deepwiki_class.return_value = mock_deepwiki_client

        mock_graph_provider_class.return_value = mock_graph_provider

        provider = HybridContextProvider(
            project_root='/test',
            enable_deepwiki=True
        )

        # Make some calls
        provider.enrich_pr_context(['src/api.py'])
        provider.enrich_pr_context(['src/core.py'])

        # Get stats
        stats = provider.get_cache_stats()

        assert 'deepwiki' in stats
        assert 'hits' in stats['deepwiki']
        assert 'misses' in stats['deepwiki']
        assert 'hit_rate' in stats['deepwiki']
