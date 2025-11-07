"""Adapter for converting between integration context and agent context formats."""

import logging
from typing import List, Optional
from pathlib import Path

from .hybrid_context_provider import HybridContext
from ..models import (
    GraphContextData,
    DeepWikiContextData,
    HybridContextData
)

logger = logging.getLogger(__name__)


class ContextAdapter:
    """
    Adapter for converting between HybridContext (integration layer)
    and Pydantic models (agent layer).

    This decouples the integration implementation from the agent interface,
    allowing either to evolve independently.
    """

    @staticmethod
    def hybrid_to_graph_context(hybrid_context: HybridContext) -> GraphContextData:
        """
        Convert HybridContext to GraphContextData.

        Args:
            hybrid_context: Context from HybridContextProvider

        Returns:
            GraphContextData for agents
        """
        graph_ctx = hybrid_context.graph_context
        impact = graph_ctx['impact_analysis']

        return GraphContextData(
            risk_level=impact['risk_level'],
            impact_score=impact['impact_score'],
            affected_files_count=impact['affected_files_count'],
            directly_affected=graph_ctx.get('dependency_info', {}).keys(),
            transitively_affected=[],  # Not directly exposed in current format
            critical_files=impact['critical_files'],
            component_breakdown=impact['component_breakdown'],
            recommendations=graph_ctx.get('recommendations', []),
            dependency_info=graph_ctx.get('dependency_info', {})
        )

    @staticmethod
    def hybrid_to_deepwiki_context(
        hybrid_context: HybridContext
    ) -> Optional[DeepWikiContextData]:
        """
        Convert HybridContext to DeepWikiContextData.

        Args:
            hybrid_context: Context from HybridContextProvider

        Returns:
            DeepWikiContextData if available, None otherwise
        """
        if not hybrid_context.deepwiki_context:
            return None

        dw_ctx = hybrid_context.deepwiki_context

        return DeepWikiContextData(
            repo=dw_ctx.repo,
            architectural_overview=dw_ctx.architectural_overview,
            component_relationships=dw_ctx.component_relationships,
            relevant_documentation=dw_ctx.relevant_documentation,
            patterns_and_conventions=dw_ctx.patterns_and_conventions,
            available=hybrid_context.deepwiki_available
        )

    @staticmethod
    def hybrid_to_hybrid_context_data(
        hybrid_context: HybridContext
    ) -> HybridContextData:
        """
        Convert HybridContext to HybridContextData.

        Args:
            hybrid_context: Context from HybridContextProvider

        Returns:
            HybridContextData for agents
        """
        return HybridContextData(
            graph_context=ContextAdapter.hybrid_to_graph_context(hybrid_context),
            deepwiki_context=ContextAdapter.hybrid_to_deepwiki_context(hybrid_context),
            context_sources=hybrid_context.get_context_sources()
        )

    @staticmethod
    def format_graph_context_for_llm(graph_context: GraphContextData) -> str:
        """
        Format graph context for LLM consumption.

        Args:
            graph_context: GraphContextData

        Returns:
            Formatted markdown string
        """
        lines = [
            "## Dependency Graph Analysis",
            "",
            f"**Risk Level**: {graph_context.risk_level}",
            f"**Impact Score**: {graph_context.impact_score:.1%}",
            f"**Affected Files**: {graph_context.affected_files_count}",
            "",
        ]

        # Critical files
        if graph_context.critical_files:
            lines.append("**Critical Files**:")
            for cf in graph_context.critical_files[:3]:
                file_name = Path(cf['file']).name
                lines.append(
                    f"  - `{file_name}`: "
                    f"{cf['direct_dependents']} direct dependents"
                )
            lines.append("")

        # Component breakdown
        if graph_context.component_breakdown:
            lines.append("**Impact by Component**:")
            for component, count in list(
                sorted(
                    graph_context.component_breakdown.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
            )[:5]:
                lines.append(f"  - {component}: {count} files")
            lines.append("")

        # Per-file dependency info
        if graph_context.dependency_info:
            lines.append("**File Dependencies**:")
            for file_path, info in list(graph_context.dependency_info.items())[:5]:
                file_name = Path(file_path).name
                metrics = info.get('metrics', {})
                lines.append(
                    f"  - `{file_name}`: "
                    f"fan-in={metrics.get('fan_in', 0)}, "
                    f"fan-out={metrics.get('fan_out', 0)}"
                    f"{' [HUB]' if metrics.get('is_hub') else ''}"
                )
            lines.append("")

        # Recommendations
        if graph_context.recommendations:
            lines.append("**Recommendations**:")
            for rec in graph_context.recommendations[:5]:
                lines.append(f"  {rec}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_deepwiki_context_for_llm(
        deepwiki_context: Optional[DeepWikiContextData]
    ) -> str:
        """
        Format DeepWiki context for LLM consumption.

        Args:
            deepwiki_context: DeepWikiContextData or None

        Returns:
            Formatted markdown string
        """
        if not deepwiki_context or not deepwiki_context.available:
            return ""

        lines = [
            "## DeepWiki Semantic Context",
            "",
            f"**Repository**: {deepwiki_context.repo}",
            "",
        ]

        # Architectural overview
        if deepwiki_context.architectural_overview:
            lines.append("**Architectural Overview**:")
            lines.append(deepwiki_context.architectural_overview)
            lines.append("")

        # Component relationships
        if deepwiki_context.component_relationships:
            lines.append("**Component Relationships**:")
            for file_path, rels in list(
                deepwiki_context.component_relationships.items()
            )[:3]:
                file_name = Path(file_path).name
                lines.append(f"  - `{file_name}`:")
                raw_answer = rels.get('raw_answer', '')
                # Truncate to first 200 chars
                lines.append(f"    {raw_answer[:200]}...")
            lines.append("")

        # Patterns and conventions
        if deepwiki_context.patterns_and_conventions:
            lines.append("**Patterns & Conventions**:")
            for pattern in deepwiki_context.patterns_and_conventions[:3]:
                lines.append(f"  - {pattern[:150]}")
            lines.append("")

        # Relevant documentation
        if deepwiki_context.relevant_documentation:
            lines.append("**Relevant Documentation**:")
            for doc in deepwiki_context.relevant_documentation[:5]:
                lines.append(f"  - {doc}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_hybrid_context_for_llm(hybrid_context_data: HybridContextData) -> str:
        """
        Format complete hybrid context for LLM consumption.

        Args:
            hybrid_context_data: HybridContextData

        Returns:
            Formatted markdown string combining all layers
        """
        sections = [
            "# Multi-Layer Context Analysis",
            "",
            f"**Context Sources**: {', '.join(hybrid_context_data.context_sources)}",
            "",
            "---",
            "",
        ]

        # Layer 1: Graph
        sections.append(
            ContextAdapter.format_graph_context_for_llm(
                hybrid_context_data.graph_context
            )
        )
        sections.append("---")
        sections.append("")

        # Layer 2: DeepWiki (if available)
        if hybrid_context_data.deepwiki_context:
            sections.append(
                ContextAdapter.format_deepwiki_context_for_llm(
                    hybrid_context_data.deepwiki_context
                )
            )
            sections.append("---")
            sections.append("")

        return "\n".join(sections)

    @staticmethod
    def extract_changed_files_from_pr(file_changes: List) -> List[str]:
        """
        Extract file paths from PR file changes.

        Args:
            file_changes: List of FileChange objects or dicts

        Returns:
            List of file paths
        """
        changed_files = []

        for change in file_changes:
            # Handle both dict and object access
            if hasattr(change, 'path'):
                changed_files.append(change.path)
            elif isinstance(change, dict):
                changed_files.append(change.get('path', ''))
            else:
                logger.warning(f"Unknown file change format: {type(change)}")

        return [f for f in changed_files if f]  # Filter empty strings

    @staticmethod
    def get_risk_level_weight(risk_level: str) -> float:
        """
        Convert risk level to numeric weight for scoring.

        Args:
            risk_level: Risk level string (LOW, MEDIUM, HIGH, CRITICAL)

        Returns:
            Numeric weight (0.0 - 1.0)
        """
        weights = {
            'LOW': 0.2,
            'MEDIUM': 0.5,
            'HIGH': 0.8,
            'CRITICAL': 1.0
        }
        return weights.get(risk_level.upper(), 0.5)

    @staticmethod
    def should_apply_extra_scrutiny(hybrid_context_data: HybridContextData) -> bool:
        """
        Determine if PR requires extra scrutiny based on context.

        Args:
            hybrid_context_data: HybridContextData

        Returns:
            True if extra scrutiny recommended
        """
        graph_ctx = hybrid_context_data.graph_context

        # High/Critical risk
        if graph_ctx.risk_level in ['HIGH', 'CRITICAL']:
            return True

        # Large impact
        if graph_ctx.impact_score > 0.3:
            return True

        # Modifying critical files
        if len(graph_ctx.critical_files) > 0:
            return True

        # Many files affected
        if graph_ctx.affected_files_count > 20:
            return True

        return False

    @staticmethod
    def get_context_quality_score(hybrid_context_data: HybridContextData) -> float:
        """
        Calculate quality score based on available context sources.

        Args:
            hybrid_context_data: HybridContextData

        Returns:
            Quality score (0.0 - 1.0)
        """
        # Base score from graph (always available)
        score = 0.6

        # Bonus for DeepWiki
        if hybrid_context_data.deepwiki_context and hybrid_context_data.deepwiki_context.available:
            score += 0.3

            # Additional bonus for rich DeepWiki content
            if hybrid_context_data.deepwiki_context.architectural_overview:
                score += 0.05
            if hybrid_context_data.deepwiki_context.patterns_and_conventions:
                score += 0.05

        return min(score, 1.0)
