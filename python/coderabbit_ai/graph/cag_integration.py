"""Integration between dependency graph and CAG (Context-Augmented Generation)."""

import logging
from typing import Dict, List, Optional, Any
from pathlib import Path

from .dependency_graph import DependencyGraph
from .impact_analyzer import ImpactAnalyzer, ImpactAnalysis

logger = logging.getLogger(__name__)


class GraphContextProvider:
    """Provides graph-based context for CAG pipeline."""

    def __init__(self, project_root: str, cache_ttl: int = 3600):
        """
        Initialize graph context provider.

        Args:
            project_root: Root directory of repository
            cache_ttl: Cache time-to-live in seconds
        """
        self.project_root = project_root
        self.cache_ttl = cache_ttl
        self._graph_cache: Optional[DependencyGraph] = None
        self._analyzer_cache: Optional[ImpactAnalyzer] = None

    def get_graph(self, force_rebuild: bool = False) -> DependencyGraph:
        """Get or build dependency graph."""
        if self._graph_cache is None or force_rebuild:
            logger.info(f"Building dependency graph for {self.project_root}")
            graph = DependencyGraph(self.project_root)
            graph.build_graph()
            self._graph_cache = graph
            self._analyzer_cache = ImpactAnalyzer(graph)

        return self._graph_cache

    def get_analyzer(self) -> ImpactAnalyzer:
        """Get impact analyzer."""
        if self._analyzer_cache is None:
            self.get_graph()  # Builds analyzer too

        return self._analyzer_cache

    def enrich_pr_context(
        self,
        changed_files: List[str],
        pr_description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich PR context with graph-based analysis.

        Args:
            changed_files: List of files modified in PR
            pr_description: Optional PR description

        Returns:
            Dict containing graph-based context:
                - impact_analysis: Full impact assessment
                - dependency_info: Per-file dependency details
                - risk_indicators: Risk flags and warnings
                - recommendations: Actionable suggestions
        """
        analyzer = self.get_analyzer()
        graph = self.get_graph()

        # Analyze impact
        impact = analyzer.analyze_changes(changed_files)

        # Get per-file dependency info
        dependency_info = {}
        for file in changed_files:
            metrics = graph.get_metrics(file)
            if metrics:
                dependency_info[file] = {
                    'dependencies': graph.get_dependencies(file),
                    'dependents': graph.get_dependents(file),
                    'metrics': {
                        'fan_in': metrics.fan_in,
                        'fan_out': metrics.fan_out,
                        'is_hub': metrics.is_hub,
                        'is_leaf': metrics.is_leaf,
                        'depth': metrics.depth,
                    }
                }

        # Generate risk indicators
        risk_indicators = self._generate_risk_indicators(impact, dependency_info)

        return {
            'impact_analysis': {
                'risk_level': impact.risk_level,
                'impact_score': impact.impact_score,
                'affected_files_count': len(impact.directly_affected) + len(impact.transitively_affected),
                'critical_files': impact.critical_files,
                'component_breakdown': impact.component_breakdown,
            },
            'dependency_info': dependency_info,
            'risk_indicators': risk_indicators,
            'recommendations': impact.recommendations,
            'graph_summary': analyzer.get_change_summary(changed_files),
        }

    def _generate_risk_indicators(
        self,
        impact: ImpactAnalysis,
        dependency_info: Dict
    ) -> List[Dict[str, str]]:
        """Generate risk indicators for review."""
        indicators = []

        # High impact risk
        if impact.risk_level in ['HIGH', 'CRITICAL']:
            indicators.append({
                'type': 'high_impact',
                'severity': impact.risk_level.lower(),
                'message': f"{impact.risk_level} impact: Affects {impact.impact_score:.1%} of codebase"
            })

        # Critical file risk
        if impact.critical_files:
            indicators.append({
                'type': 'critical_files',
                'severity': 'high',
                'message': f"Modifying {len(impact.critical_files)} high-traffic file(s)"
            })

        # Hub file risk
        hub_files = [
            file for file, info in dependency_info.items()
            if info.get('metrics', {}).get('is_hub', False)
        ]
        if hub_files:
            indicators.append({
                'type': 'hub_modification',
                'severity': 'medium',
                'message': f"Modifying {len(hub_files)} hub file(s) with many dependents"
            })

        return indicators

    def get_related_context(
        self,
        changed_files: List[str],
        max_distance: int = 1
    ) -> Dict[str, List[str]]:
        """
        Get related files that might need attention.

        Args:
            changed_files: Files being modified
            max_distance: Maximum dependency distance

        Returns:
            Dict mapping distance level to related files
        """
        analyzer = self.get_analyzer()
        return analyzer.find_related_changes(changed_files, max_distance)

    def format_for_llm(self, context: Dict[str, Any]) -> str:
        """
        Format graph context for LLM consumption.

        Args:
            context: Graph context from enrich_pr_context()

        Returns:
            Formatted string for LLM prompt
        """
        lines = ["## Dependency & Impact Analysis\n"]

        # Risk summary
        impact = context['impact_analysis']
        lines.append(f"**Risk Level**: {impact['risk_level']}")
        lines.append(f"**Impact Score**: {impact['impact_score']:.1%}\n")

        # Affected files
        lines.append(f"**Affected Files**: {impact['affected_files_count']} total\n")

        # Critical files
        if impact['critical_files']:
            lines.append("**Critical Files Being Modified**:")
            for cf in impact['critical_files'][:3]:
                file_name = Path(cf['file']).name
                lines.append(f"  - `{file_name}`: {cf['direct_dependents']} direct dependents")
            lines.append("")

        # Component breakdown
        if impact['component_breakdown']:
            lines.append("**Impact by Component**:")
            for component, count in list(impact['component_breakdown'].items())[:5]:
                lines.append(f"  - {component}: {count} files")
            lines.append("")

        # Recommendations
        if context['recommendations']:
            lines.append("**Recommendations**:")
            for rec in context['recommendations'][:5]:
                lines.append(f"  {rec}")

        return "\n".join(lines)


# Singleton instance
_graph_context_provider: Optional[GraphContextProvider] = None


def get_graph_context_provider(project_root: str) -> GraphContextProvider:
    """Get or create graph context provider singleton."""
    global _graph_context_provider

    if _graph_context_provider is None:
        _graph_context_provider = GraphContextProvider(project_root)

    return _graph_context_provider
