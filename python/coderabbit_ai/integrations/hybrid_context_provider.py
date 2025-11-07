"""Hybrid context provider combining graph analysis, DeepWiki, and on-demand generation."""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from ..graph.cag_integration import GraphContextProvider
from .deepwiki_client import DeepWikiClient, DeepWikiContext

logger = logging.getLogger(__name__)


@dataclass
class HybridContext:
    """
    Unified context combining all three layers:
    - Layer 1: Local dependency graph (structure)
    - Layer 2: DeepWiki semantic docs (if available)
    - Layer 3: On-demand LLM generation (fallback)
    """

    # Layer 1: Always available
    graph_context: Dict[str, Any]

    # Layer 2: Optional DeepWiki context
    deepwiki_context: Optional[DeepWikiContext]
    deepwiki_available: bool

    # Layer 3: On-demand context (future implementation)
    on_demand_context: Optional[Dict[str, Any]]

    # Metadata
    repo: str
    changed_files: List[str]
    timestamp: datetime

    def get_context_sources(self) -> List[str]:
        """Get list of active context sources."""
        sources = ["graph"]  # Always have graph
        if self.deepwiki_available and self.deepwiki_context:
            sources.append("deepwiki")
        if self.on_demand_context:
            sources.append("on_demand")
        return sources


class HybridContextProvider:
    """
    Provides unified context using three-layer fallback strategy.

    Layer Strategy:
    1. Local Graph (ALWAYS): Fast, structure-based dependency analysis
    2. DeepWiki (IF AVAILABLE): Semantic docs for 50k+ public repos
    3. On-Demand LLM (FALLBACK): Generate docs for non-indexed repos

    Benefits:
    - 100% coverage: Works for all repos
    - Optimal performance: Use best available source
    - Graceful degradation: Fall back when services unavailable
    """

    def __init__(
        self,
        project_root: str,
        repo_name: Optional[str] = None,
        enable_deepwiki: bool = True,
        enable_on_demand: bool = False,  # Not implemented yet
        deepwiki_timeout: int = 30,
        cache_ttl: int = 3600,
    ):
        """
        Initialize hybrid context provider.

        Args:
            project_root: Root directory of repository
            repo_name: Repository name in "owner/repo" format (for DeepWiki)
            enable_deepwiki: Enable DeepWiki integration (Layer 2)
            enable_on_demand: Enable on-demand generation (Layer 3)
            deepwiki_timeout: DeepWiki request timeout
            cache_ttl: Cache time-to-live in seconds
        """
        self.project_root = project_root
        self.repo_name = repo_name
        self.cache_ttl = cache_ttl

        # Layer 1: Local graph (always enabled)
        self.graph_provider = GraphContextProvider(project_root, cache_ttl)
        logger.info("Layer 1 (Graph) initialized")

        # Layer 2: DeepWiki (optional)
        self.enable_deepwiki = enable_deepwiki
        self.deepwiki_client: Optional[DeepWikiClient] = None
        if enable_deepwiki:
            try:
                self.deepwiki_client = DeepWikiClient(
                    timeout=deepwiki_timeout,
                    cache_ttl=cache_ttl
                )
                logger.info("Layer 2 (DeepWiki) initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize DeepWiki client: {e}")
                self.deepwiki_client = None

        # Layer 3: On-demand generation (future)
        self.enable_on_demand = enable_on_demand
        if enable_on_demand:
            logger.warning("Layer 3 (On-Demand) not yet implemented")

    def enrich_pr_context(
        self,
        changed_files: List[str],
        pr_description: Optional[str] = None,
        force_graph_rebuild: bool = False
    ) -> HybridContext:
        """
        Enrich PR context with all available layers.

        This is the main entry point for getting comprehensive context
        about a PR. It automatically uses the best available sources.

        Args:
            changed_files: List of files modified in PR
            pr_description: Optional PR description
            force_graph_rebuild: Force rebuild of dependency graph

        Returns:
            HybridContext with all available information

        Example:
            >>> provider = HybridContextProvider("/repo", "facebook/react")
            >>> context = provider.enrich_pr_context(
            ...     ["src/React.js"],
            ...     "Add new hook"
            ... )
            >>> print(context.get_context_sources())
            ['graph', 'deepwiki']
        """
        logger.info(
            f"Enriching context for {len(changed_files)} files "
            f"using {self._get_enabled_layers()}"
        )

        # Layer 1: Local graph analysis (ALWAYS)
        logger.info("Fetching Layer 1 (Graph) context...")
        graph_context = self.graph_provider.enrich_pr_context(
            changed_files,
            pr_description
        )
        logger.info(f"Layer 1 complete: {graph_context['impact_analysis']['risk_level']} risk")

        # Layer 2: DeepWiki semantic context (IF AVAILABLE)
        deepwiki_context = None
        deepwiki_available = False

        if self.enable_deepwiki and self.deepwiki_client and self.repo_name:
            logger.info("Checking Layer 2 (DeepWiki) availability...")

            # Check if repo is indexed
            if self.deepwiki_client.is_repo_indexed(self.repo_name):
                logger.info(f"Repository {self.repo_name} is indexed in DeepWiki")
                deepwiki_available = True

                try:
                    deepwiki_context = self.deepwiki_client.enrich_pr_context(
                        self.repo_name,
                        changed_files,
                        pr_description
                    )
                    logger.info("Layer 2 complete: DeepWiki context retrieved")
                except Exception as e:
                    logger.error(f"Layer 2 failed: {e}")
                    deepwiki_context = None
            else:
                logger.info(
                    f"Repository {self.repo_name} not found in DeepWiki's 50k index"
                )

        # Layer 3: On-demand generation (FUTURE)
        on_demand_context = None
        if self.enable_on_demand and not deepwiki_available:
            logger.info("Layer 3 (On-Demand) would activate here (not implemented)")
            # TODO: Implement on-demand LLM documentation generation

        return HybridContext(
            graph_context=graph_context,
            deepwiki_context=deepwiki_context,
            deepwiki_available=deepwiki_available,
            on_demand_context=on_demand_context,
            repo=self.repo_name or "local",
            changed_files=changed_files,
            timestamp=datetime.now()
        )

    def format_for_llm(self, context: HybridContext) -> str:
        """
        Format hybrid context for LLM consumption.

        Combines all available context layers into a unified,
        well-formatted string suitable for LLM prompts.

        Args:
            context: HybridContext to format

        Returns:
            Formatted markdown string

        Example:
            >>> formatted = provider.format_for_llm(context)
            >>> print(formatted[:100])
            # Context for PR Review

            **Repository**: facebook/react
            **Changed Files**: 3
        """
        lines = [
            "# Context for PR Review",
            "",
            f"**Repository**: {context.repo}",
            f"**Changed Files**: {len(context.changed_files)}",
            f"**Context Sources**: {', '.join(context.get_context_sources())}",
            "",
        ]

        # Layer 1: Graph context (always present)
        lines.append("---")
        lines.append("")
        lines.append(self.graph_provider.format_for_llm(context.graph_context))
        lines.append("")

        # Layer 2: DeepWiki context (if available)
        if context.deepwiki_context and self.deepwiki_client:
            lines.append("---")
            lines.append("")
            lines.append(self.deepwiki_client.format_for_llm(context.deepwiki_context))
            lines.append("")

        # Layer 3: On-demand context (future)
        if context.on_demand_context:
            lines.append("---")
            lines.append("")
            lines.append("## On-Demand Generated Context")
            lines.append("")
            # TODO: Format on-demand context

        lines.append("---")
        lines.append(f"*Context generated: {context.timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def get_risk_summary(self, context: HybridContext) -> Dict[str, Any]:
        """
        Extract risk summary from hybrid context.

        Args:
            context: HybridContext

        Returns:
            Dict with risk level, impact score, and flags
        """
        impact = context.graph_context['impact_analysis']

        return {
            'risk_level': impact['risk_level'],
            'impact_score': impact['impact_score'],
            'affected_files': impact['affected_files_count'],
            'critical_files': len(impact['critical_files']),
            'has_semantic_context': context.deepwiki_available,
            'context_sources': context.get_context_sources()
        }

    def should_flag_for_review(
        self,
        context: HybridContext,
        threshold: str = 'high'
    ) -> bool:
        """
        Determine if PR should be flagged for extra review.

        Args:
            context: HybridContext
            threshold: Minimum risk level ('medium', 'high', 'critical')

        Returns:
            True if should be flagged
        """
        analyzer = self.graph_provider.get_analyzer()
        return analyzer.should_flag_for_review(
            context.changed_files,
            threshold
        )

    def get_recommendations(self, context: HybridContext) -> List[str]:
        """
        Get all recommendations from all context layers.

        Args:
            context: HybridContext

        Returns:
            Combined list of recommendations
        """
        recommendations = []

        # Graph recommendations (Layer 1)
        recommendations.extend(context.graph_context.get('recommendations', []))

        # DeepWiki recommendations (Layer 2)
        if context.deepwiki_context:
            # Could extract recommendations from DeepWiki patterns
            if context.deepwiki_context.patterns_and_conventions:
                recommendations.append(
                    "📚 Consider documented patterns from DeepWiki"
                )

        return recommendations

    def _get_enabled_layers(self) -> str:
        """Get description of enabled layers."""
        layers = ["Layer 1 (Graph)"]
        if self.enable_deepwiki:
            layers.append("Layer 2 (DeepWiki)")
        if self.enable_on_demand:
            layers.append("Layer 3 (On-Demand)")
        return ", ".join(layers)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics from all layers."""
        stats = {
            'graph': "N/A",  # GraphContextProvider doesn't expose stats yet
        }

        if self.deepwiki_client:
            stats['deepwiki'] = self.deepwiki_client.get_cache_stats()

        return stats

    def clear_all_caches(self) -> None:
        """Clear caches from all layers."""
        logger.info("Clearing all caches")

        # Force graph rebuild on next call
        self.graph_provider._graph_cache = None
        self.graph_provider._analyzer_cache = None

        # Clear DeepWiki cache
        if self.deepwiki_client:
            self.deepwiki_client.clear_cache()

        logger.info("All caches cleared")


# Singleton instance
_hybrid_context_provider: Optional[HybridContextProvider] = None


def get_hybrid_context_provider(
    project_root: str,
    repo_name: Optional[str] = None,
    **kwargs
) -> HybridContextProvider:
    """
    Get or create hybrid context provider singleton.

    Args:
        project_root: Root directory of repository
        repo_name: Repository name in "owner/repo" format
        **kwargs: Additional arguments for HybridContextProvider

    Returns:
        HybridContextProvider instance
    """
    global _hybrid_context_provider

    if _hybrid_context_provider is None:
        _hybrid_context_provider = HybridContextProvider(
            project_root,
            repo_name,
            **kwargs
        )

    return _hybrid_context_provider
